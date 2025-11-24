"""
Note: this is pretty different to the usual snail intersections method. exactextract is 
really fast but needs a very different setup. The splits are made and deleted on the fly.

To do
- make one mega-raster so I don't have to loop through hazards. Should make it way faster.
- need to map all rasters to band numbers
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
import logging


def get_hazard_from_colname(hazcol):
    return hazcol.split("_")[0].split('-')[1]


def write_raster(w:np.ndarray, src:rasterio.DatasetReader, outpath:str):
    with rasterio.open(
        outpath, 'w',
        driver='GTiff',
        height=w.shape[0],
        width=w.shape[1],
        count=1,
        dtype=w.dtype,
        crs=src.crs,
        transform=src.transform,
    ) as dst:
        dst.write(w, 1)



def calculate_raster_cell_areas(raster_path):
    """Calculate the area of each cell in a raster."""
    with rasterio.open(raster_path) as src:
        transform = src.transform
        height = src.height
        geod = Geod(ellps="WGS84")
        
        areas_col = np.zeros(height)
        for row in range(height):
            x_min, y_max = transform * (0, row)
            x_max, y_min = transform * (1, row + 1)
            area, _ = geod.polygon_area_perimeter(
                [x_min, x_max, x_max, x_min],
                [y_min, y_min, y_max, y_max]
            )
            areas_col[row] = abs(area)
        
        return np.tile(areas_col[:, np.newaxis], (1, src.width))


def get_design_standard_raster_path(design_standard, rasters):
    """Check raster list for design standard raster matching the design_standard stem."""
    for r in rasters:
        if Path(r).stem == design_standard:
            return r
    return None


def prepare_hazard(outfile, hazard, design_hazard=None) -> None:
    """Create a two-band raster with original hazard and residual
    hazard (hazard - design standard)."""
    if design_hazard is not None:
        with rasterio.open(design_hazard) as design_src:
            with rasterio.open(hazard) as hazard_src:
                design_data = design_src.read(1, masked=True)
                hazard_data = hazard_src.read(1, masked=True)
                residual = hazard_data - design_data
                residual = np.ma.masked_where(residual < 0, residual)
    else:
        with rasterio.open(hazard) as hazard_src:
            hazard_data = hazard_src.read(1, masked=True)
            residual = hazard_data.copy()

    with rasterio.open(hazard) as src:
        with rasterio.open(
            outfile, 'w',
            driver='GTiff',
            height=hazard_data.shape[0],
            width=hazard_data.shape[1],
            count=2,
            dtype=hazard_data.dtype,
            crs=src.crs,
            transform=src.transform,
        ) as dst:
            dst.write(hazard_data, 1)
            dst.write(residual, 2)
    
    return None


def prepare_hazards(outfile:str, hazards:list, design_hazards:list) -> None:
    """Create a two-band raster with original hazard and residual
    hazard (hazard - design standard)."""
    hazard_datas = []
    residuals = []
    band_mapping = {}
    i = 1
    for hazard, design_hazard in zip(hazards, design_hazards):
        logging.info(f"Preparing hazard raster: {hazard} with design standard: {design_hazard}")
        if design_hazard is not None:
            with rasterio.open(design_hazard) as design_src:
                with rasterio.open(hazard) as hazard_src:
                    design_data = design_src.read(1, masked=True)
                    hazard_data = hazard_src.read(1, masked=True)
                    residual = hazard_data - design_data
                    residual = np.ma.masked_where(residual < 0, residual)
        else:
            with rasterio.open(hazard) as hazard_src:
                hazard_data = hazard_src.read(1, masked=True)
                residual = hazard_data.copy()

        hazard_datas.append(hazard_data)
        residuals.append(residual)
        band_mapping[hazard] = (i, i+1)
        i += 2



    # if design_hazard is not None:
    #     with rasterio.open(design_hazard) as design_src:
    #         with rasterio.open(hazard) as hazard_src:
    #             design_data = design_src.read(1, masked=True)
    #             hazard_data = hazard_src.read(1, masked=True)
    #             residual = hazard_data - design_data
    #             residual = np.ma.masked_where(residual < 0, residual)
    # else:
    #     with rasterio.open(hazard) as hazard_src:
    #         hazard_data = hazard_src.read(1, masked=True)
    #         residual = hazard_data.copy()

    with rasterio.open(hazards[0]) as src:
        with rasterio.open(
            outfile, 'w',
            driver='GTiff',
            height=hazard_data.shape[0],
            width=hazard_data.shape[1],
            count=2,
            dtype=hazard_data.dtype,
            crs=src.crs,
            transform=src.transform,
        ) as dst:
            for hazard, design_hazard in zip(hazards, design_hazards):


            
            # dst.write(hazard_data, 1)
            # dst.write(residual, 2)
    
    return None


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
    damage_binary = (damage_frac > 0).astype(float)
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


def make_damage_op(damage_function, damage_col):
    """Factory function to create damage function for exact_extract."""
    def damage(x, c, w):
        return _damaged_units(x, c, w, damage_function=damage_function)
    damage.__name__ = damage_col
    return damage


def make_rehab_cost_op(damage_function, cost, cost_col):
    """Factory function to create rehab cost function for exact_extract."""
    def rehab_cost(x, c, w):
        return _rehab_cost(x, c, w, damage_function=damage_function, cost=cost)
    rehab_cost.__name__ = cost_col
    return rehab_cost


def intersect(vector, rasters, damage_curves, rehab_costs, design_standards) -> gpd.GeoDataFrame:

    areas = calculate_raster_cell_areas(rasters[0])
    asset_types = list(vector["asset_type"].unique())
    asset_type_damages = []

    for asset_type in asset_types:
        vector_asset = vector[vector["asset_type"] == asset_type].copy()
        for raster in rasters:
            # extract hazard and hazard column name from raster file path
            hazard_col = f"hazard-{Path(raster).stem}"
            defended_col = f"defended-{Path(raster).stem}"
            hazard = get_hazard_from_colname(hazard_col)

            # check if design standards specified for this (hazard, asset_type)
            design_standard_df = design_standards[hazard]
            design_standard:str = design_standard_df.loc[asset_type, "design_hazard"]
            design_hazard:str = get_design_standard_raster_path(design_standard, rasters)

            with tempfile.TemporaryDirectory() as tmpdir:

                hazard_tmp = os.path.join(tmpdir, "hazard.tif")
                asset_tmp = os.path.join(tmpdir, "asset.shp")
                weight_tmp = os.path.join(tmpdir, "weights.tif")

                # save asset shapefile and weights raster
                vector_asset[['id', 'geometry']].to_file(asset_tmp)
                with rasterio.open(raster) as src:
                    write_raster(areas, src, weight_tmp)

                # save a 2-band raster with protected and unprotected hazard
                prepare_hazard(hazard_tmp, raster, design_hazard=design_hazard)

                # loop through damage functions and rehab costs
                ops = ["max"]
                damage_cols = []
                cost_cols = []

                for prefix in ["min", "mean", "max"]:
                    damage_function = damage_curves[(hazard, asset_type)][prefix]
                    damage_col = hazard_col.replace("hazard-", "damage-") + "_" + prefix

                    # for prefix in ["min", "mean", "max"]:
                    # NOTE: option to have 9 combinations but 3 should be enough
                    cost = rehab_costs[hazard].loc[asset_type, f"{prefix}_cost_usd"]
                    cost_col = damage_col.replace("damage-", "cost-") + "_" + prefix

                    damage = make_damage_op(damage_function, damage_col)
                    rehab_cost = make_rehab_cost_op(damage_function, cost, cost_col)

                    ops.extend([damage, rehab_cost])

                    damage_cols.append(damage_col)
                    cost_cols.append(cost_col)
                        
                hazard_stats = exact_extract(
                    hazard_tmp, asset_tmp, ops,
                    weights=weight_tmp,
                    progress=True, output="pandas"
                )

                vector_asset[hazard_col] = hazard_stats["band_1_max"].astype(float).values
                vector_asset[defended_col] = hazard_stats["band_2_max"].astype(float).values

                defended_prefix = "band_2_weight_"
                for damage_col, cost_col in zip(damage_cols, cost_cols):
                    vector_asset[damage_col] = hazard_stats[defended_prefix + damage_col].astype(float).values
                    vector_asset[cost_col] = hazard_stats[defended_prefix + cost_col].astype(float).values
                    
        asset_type_damages.append(vector_asset)
    
    vector = pd.concat(asset_type_damages, axis=0)
    
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