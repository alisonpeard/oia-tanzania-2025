"""
Note: this is pretty different to the usual snail intersections method. exactextract is 
really fast but needs a very different setup. The splits cannot be saved here.
"""
import os
import tempfile
from pathlib import Path
import rasterio
import numpy as np
import pandas as pd
import geopandas as gpd
from pyproj import Geod
import rasterio
from exactextract import exact_extract
from tqdm import tqdm
from osgeo import gdal
import logging

from utils import naming


def make_window(vector:gpd.GeoDataFrame, raster:str) -> rasterio.windows.Window:
    with rasterio.open(raster) as src:
        bounds = vector.total_bounds  # (minx, miny, maxx, maxy)
        window = rasterio.windows.from_bounds(
            bounds[0], bounds[1], bounds[2], bounds[3],
            transform=src.transform
        ).round()
    return window


def calculate_raster_cell_areas(raster_path, window=None) -> np.ndarray:
    """Calculate the area of each cell in a raster."""
    logging.info(f"Calculating raster cell areas for {raster_path}")
    with rasterio.open(raster_path) as src:
        if window is not None:
            transform = rasterio.windows.transform(window, src.transform)
            height = window.height
            width = window.width
            row_offset = int(window.row_off)
        else:
            transform = src.transform
            height = src.height
            width = src.width
            row_offset = 0
        
        geod = Geod(ellps="WGS84")
        
        areas_col = np.zeros(height)
        for row in range(height):
            actual_row = row_offset + row
            x_min, y_max = transform * (0, row)
            x_max, y_min = transform * (1, row + 1)
            area, _ = geod.polygon_area_perimeter(
                [x_min, x_max, x_max, x_min],
                [y_min, y_min, y_max, y_max]
            )
            areas_col[row] = abs(area)
        
        return np.tile(areas_col[:, np.newaxis], (1, width))
    

def get_design_standard_raster_path(design_standard:str, rasters:list[str]) -> str | None:
    """Check raster list for design standard raster matching the design_standard stem."""
    for r in rasters:
        if Path(r).stem == design_standard:
            return r
    return None


def prepare_hazard(hazard, design_hazard, window=None):
    """Create a two-band raster with original hazard and residual
    hazard (hazard - design standard)."""
    if design_hazard is not None:
        with rasterio.open(design_hazard) as design_src:
            with rasterio.open(hazard) as hazard_src:
                design_data = design_src.read(1, window=window, masked=True)
                hazard_data = hazard_src.read(1, window=window, masked=True)
                residual = hazard_data - design_data
                residual = np.ma.masked_where(residual < 0, residual)
    else:
        with rasterio.open(hazard) as hazard_src:
            hazard_data = hazard_src.read(1, window=window, masked=True)
            residual = hazard_data.copy()

    return hazard_data, residual


def create_mega_raster(
        rasters: list[str],
        asset_type: str,
        design_standards: dict,
        output_dir: str = None,
        window: rasterio.windows.Window = None
    ):
    logging.info(f"Creating multi-band VRT for asset type: {asset_type}")
    if output_dir is None:
        logging.warning("No output directory specified, using current directory.")
        output_dir = "."
    
    output_tif = Path(output_dir) / f"hazards_{asset_type}.tif"

    # prepate profile using first raster
    with rasterio.open(rasters[0]) as src:
        profile = src.profile.copy()
        if window:
            profile.update({
                "height": window.height,
                "width": window.width,
                "transform": rasterio.windows.transform(window, src.transform),
                "count": len(rasters) * 2
            })

    counter = 1
    band_keys = {}

    with rasterio.open(output_tif, 'w', **profile) as dst:
        for raster in (pbar := tqdm(rasters, desc="Creating mega raster")): # ! ballooning memory
            pbar.set_postfix({"raster": raster})
            # extract hazard and hazard column name from raster file path
            hazard_col = f"hazard-{Path(raster).stem}"
            defended_col = f"defended-{Path(raster).stem}"
            hazard = naming.get_hazard_from_colname(hazard_col)

            # check if design standards specified for this (hazard, asset_type)
            design_standard_df = design_standards[hazard]
            design_standard: str = design_standard_df.loc[asset_type, "design_hazard"]
            design_hazard: str = get_design_standard_raster_path(design_standard, rasters)

            # load hazard and calculate defended hazard
            hazard_tmp, defended_tmp = prepare_hazard(
                raster, design_hazard=design_hazard, window=window
            )

            # store bands and mapping
            band_keys[hazard_col] = counter
            band_keys[defended_col] = counter + 1

            # write to multi-band tif
            dst.write(hazard_tmp, counter)
            dst.write(defended_tmp, counter + 1)

            counter += 2

    logging.info(f"Created multi-band VRT with {counter - 1} bands at {output_tif}")

    return str(output_tif), band_keys


def check_single_hazard_type(rasters: list[str]):
    hazard_types = set()
    for r in rasters:
        hazard = naming.get_hazard_from_filename(r)
        hazard_types.add(hazard)
    if len(hazard_types) != 1:
        raise ValueError(
            f"intersections.py should filter to one hazard type. "
            f"Received: {hazard_types}"
    )
    return hazard_types.pop()


def _damaged_units(x, c, w, damage_function):
    """
    Args:
    - x: raster values
    - c: cell coverage fractions
    - w: cell areas (sqm)
    """
    # NEW: this is binary so we measure it in units / area sqm
    x = np.ma.filled(x, 0)
    damage_frac = damage_function(x) # nonlinear / pwl
    # propagate nans properly
    damage_binary = np.where(
        damage_frac > 0,
        1.0,
        np.where(np.isnan(damage_frac), np.nan, 0.0)
    )
    damage_units = damage_binary * c * w
    return np.sum(damage_units)


def _rehab_cost(x, c, w, damage_function, cost):
    """
    Args:
    - x: raster values
    - c: cell coverage fractions
    - w: cell areas (sqm)
    """
    x = np.ma.filled(x, 0)
    damage_frac = damage_function(x) # nonlinear / pwl
    damage_units = damage_frac * c * w
    damage_cost = damage_units * cost
    return np.sum(damage_cost)


def make_damage_op(damage_function, suffix):
    """Factory function to create damage function for exact_extract."""
    def damage(x, c, w):
        return _damaged_units(x, c, w, damage_function=damage_function)
    damage.__name__ = "damage_" + suffix
    return damage


def make_rehab_cost_op(damage_function, cost, suffix):
    """Factory function to create rehab cost function for exact_extract."""
    def rehab_cost(x, c, w):
        return _rehab_cost(x, c, w, damage_function=damage_function, cost=cost)
    rehab_cost.__name__ = "cost_" + suffix
    return rehab_cost


def write_raster(
        w:np.ndarray, src:rasterio.DatasetReader, outpath:str,
        window:rasterio.windows.Window=None
    ):
    """Write a single-band raster from array w, using src for profile."""
    profile = src.profile.copy()
    if window:
        profile.update({
            "height": window.height,
            "width": window.width,
            "transform": rasterio.windows.transform(window, src.transform),
            "count": 1
        })
    with rasterio.open(outpath, 'w', **profile) as dst:
        dst.write(w, 1)


def intersect(
        vector, rasters, damage_curves, rehab_costs, design_standards,
        splits_path: str = None) -> gpd.GeoDataFrame:
    hazard = check_single_hazard_type(rasters)
    window = make_window(vector, rasters[0])

    areas = calculate_raster_cell_areas(rasters[0])
    asset_types = list(vector["asset_type"].unique())
    asset_type_damages = [] # gather results for each asset type

    for asset_type in asset_types:
        vector_asset = vector[vector["asset_type"] == asset_type].copy()
        new_columns = {} # gather new columns in dict for performance

        ops = ["max"]
        # create damage and cost operations
        for suffix in ["min", "mean", "max"]:
            damage_function = damage_curves[(hazard, asset_type)][suffix]
            rehab_cost = rehab_costs[hazard].loc[asset_type, f"{suffix}_cost_usd"]

            damage = make_damage_op(damage_function, suffix)
            cost = make_rehab_cost_op(damage_function, rehab_cost, suffix)
            ops.extend([damage, cost])

        with tempfile.TemporaryDirectory() as tmpdir:
            logging.info(f"Using temporary directory: {tmpdir}")
            # make mega-raster
            hazard_tmp, band_keys = create_mega_raster(
                rasters, asset_type, design_standards,
                output_dir=tmpdir, window=window
            )

            # save assets and weights to tempdir
            asset_tmp = os.path.join(tmpdir, "asset.shp")
            weight_tmp = os.path.join(tmpdir, "weights.tif")
            vector_asset[['id', 'geometry']].to_file(asset_tmp)
            with rasterio.open(rasters[0]) as src:
                write_raster(areas, src, weight_tmp)

            hazard_stats = exact_extract(
                hazard_tmp, asset_tmp, ops,
                weights=weight_tmp,
                progress=True, output="pandas"
            )

            for column, band in band_keys.items():
                new_columns[column] = hazard_stats[f"band_{band}_max"].astype(float).values
                if column.startswith("hazard-"):
                    continue
                elif column.startswith("defended-"):
                    for suffix in ["min", "mean", "max"]:
                        damage_col = column.replace("defended-", "damage-") + "_" + suffix
                        cost_col = damage_col.replace("damage-", "cost-") + "_" + suffix
                        damage_band = "band_" + str(band) + "_weight_damage_" + suffix
                        cost_band = "band_" + str(band) + "_weight_cost_" + suffix
                        new_columns[damage_col] = hazard_stats[damage_band].astype(float).values
                        new_columns[cost_col] = hazard_stats[cost_band].astype(float).values

            new_columns_df = pd.DataFrame(new_columns, index=vector_asset.index)
            vector_asset = pd.concat([vector_asset, new_columns_df], axis=1)
            asset_type_damages.append(vector_asset)

    logging.info("Deleted temporary directory and files.")
    # pull it all together
    vector = pd.concat(asset_type_damages, axis=0)
    
    # calculate polygon areas
    geod = Geod(ellps="WGS84")
    def calculate_area(geom):
        area, _ = geod.geometry_area_perimeter(geom)
        return abs(area)
    tqdm.pandas(desc="Calculating polygon areas")
    vector["unit"] = (
        vector.geometry.progress_apply(calculate_area)
    )
    vector["unit_type"] = "sqm"
    vector = vector.set_index("id")

    return vector
