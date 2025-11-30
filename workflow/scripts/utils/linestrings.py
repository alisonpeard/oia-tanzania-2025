"""Intersect linestrings with rasters and calculate risk metrics.

Potential bottlenecks:
- Looping through asset_types
"""
import logging
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
import snail.intersection as snint
from pyproj import Geod
import rasterio
from pathlib import Path
from osgeo import gdal
import numpy as np
import tempfile


def get_hazard_from_colname(hazcol):
    return hazcol.split("_")[0].split('-')[1]


def make_raster_basenames(raster_files):
    raster_basenames = []
    for raster_path in raster_files:
        basename = Path(raster_path).stem
        raster_basenames.append(basename)
    return raster_basenames


def create_multiband_vrt(raster_files: list[str], output_dir: str = None):
    """
    Create a multi-band VRT from a list of raster files.
    """
    if output_dir is None:
        logging.warning("No output directory specified, using current directory.")
        output_dir = "."

    output_vrt = Path(output_dir) / "hazard_stack.vrt"
    vrt_options = gdal.BuildVRTOptions(separate=True)

    _vrt = gdal.BuildVRT(str(output_vrt), raster_files, options=vrt_options)
    _vrt = None
    
    logging.info(f"Created multi-band VRT with {len(raster_files)} bands at {output_vrt}")
    return str(output_vrt)


def grid_from_window(raster_file, bounds, verbose=False) -> snint.GridDefinition:
    """Create a snint.GridDefinition.from_raster for window defined by bounds."""
    with rasterio.open(raster_file) as src:
        window = rasterio.windows.from_bounds(
            bounds[0], bounds[1], bounds[2], bounds[3],
            transform=src.transform
        ).round()
        logging.info(f"Computed window from bounds: {window}")
        window_transform = rasterio.windows.transform(window, src.transform)

    grid = snint.GridDefinition(
        width=int(window.width),
        height=int(window.height),
        transform=window_transform,
        crs=src.crs.to_string()
    )
    return grid, window


def process_raster_grid(
        raster_files:list[str], vector:gpd.GeoDataFrame, verify_consistency=False
        ) -> snint.GridDefinition:
    """Make a grid for list of rasters, based on vector bounds."""
    bounds = vector.total_bounds
    grid, window = grid_from_window(raster_files[0], bounds)
    logging.info(f"{grid=}")

    if len(raster_files) > 1 and verify_consistency:
        logging.info("Checking raster grid consistency")
        for raster_path in raster_files[1:]:
            other_grid, _ = grid_from_window(raster_path, bounds)
            if other_grid != grid:
                raise AttributeError(
                    (
                        f"Raster attribute mismatch in file {raster_path}:\n"
                        f"Height: expected={grid.height}; actual={other_grid.height}\n"
                        f"Width: expected={grid.width}; actual={other_grid.width}\n"
                        f"Transform equal? {other_grid.transform == grid.transform}\n"
                        f"Transform expected= {grid.transform}\n"
                        f"Transform actual= {other_grid.transform}\n"
                        f"CRS equal? {other_grid.crs == grid.crs}"
                    )
                )
    
    return grid, window



def copy_raster_values_multiband(
    vector_splits: gpd.GeoDataFrame, 
    vrt_path: str,
    raster_basenames: list[str],
    window: rasterio.windows.Window = None
) -> gpd.GeoDataFrame:
    """Copy windowed raster values from multi-band VRT to split geometries."""

    logging.info("Reading all raster values from multi-band VRT")
    
    raster_data: dict[str, np.ndarray] = {}
    
    with rasterio.open(vrt_path) as src:
        if window is not None:
            logging.info(f"Reading windowed area: {window}")
            data = src.read(window=window, masked=True)
        else:
            logging.info(f"Reading full raster: {src.height}x{src.width}")
            data = src.read(masked=True)
        
        logging.info(f"Read {data.shape[0]} bands from VRT")

        window_transform = rasterio.windows.transform(window, src.transform)
        
        for band_idx, basename in enumerate(tqdm(raster_basenames, desc="Extracting values")):
            colname = f"hazard-{basename}"
            band_data = data[band_idx]
            raster_data[colname] = snint.get_raster_values_for_splits(
                vector_splits, band_data, index_i="raster_i", index_j="raster_j"
            )
    
    raster_data = pd.DataFrame(raster_data)
    vector_splits = pd.concat([vector_splits, raster_data], axis="columns")
    assert len(raster_data) == len(vector_splits)
    return vector_splits


def vectorized_damage_calculation(
    defended_values: np.ndarray,
    damage_function: callable,
    unit_values: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns:
        damage_units: damaged units (binary: damaged area)
        damage_fraction: damage fraction for cost calculation
    """
    damage_frac = np.vectorize(damage_function)(defended_values)
    damage_binary = (damage_frac > 0).astype(float) * unit_values
    return damage_binary, damage_frac


def unsplit(vector, vector_ref, hazard_cols, damage_cols, cost_cols):
    """Dissolve split geometries back to original geometries."""
    risk_cols = hazard_cols + damage_cols + cost_cols
    meta_cols = ["asset_type", "unit", "unit_type"]

    agg_func = {col: "max" for col in hazard_cols} | \
                {col: "sum" for col in damage_cols} | \
                {col: "sum" for col in cost_cols}
    meta_agg = {"unit": "sum", 'unit_type': "first", "asset_type": "first"}
    agg_func.update(meta_agg)

    vector = vector[["id"] + meta_cols + risk_cols].copy()
    vector_grouped = vector.groupby("id").agg(agg_func).sort_index()

    vector_ref = vector_ref.set_index("id").sort_index()

    assert vector_ref.index.is_unique
    assert vector_grouped.index.equals(vector_ref.index)

    vector_grouped = vector_grouped.join(vector_ref[["geometry"]])
    vector_grouped = gpd.GeoDataFrame(
        vector_grouped, geometry="geometry", crs="EPSG:4326"
    )
    return vector_grouped


def intersect(
        vector: gpd.GeoDataFrame, 
        rasters: list[str],
        damage_curves: dict, 
        rehab_costs: dict,
        design_standards: dict,
        splits_path: str = None,
    ) -> gpd.GeoDataFrame:
    """Main intersection function for linestrings."""

    assert len(rasters) > 0, "No rasters provided for intersection."

    grid, window = process_raster_grid(rasters, vector)
    raster_basenames = make_raster_basenames(rasters)

    logging.info("Splitting edges...")
    vector = vector.reset_index(drop=True)
    vector_splits = snint.split_linestrings(vector, grid)
    logging.info("Split %d edges into %d pieces", len(vector), len(vector_splits))

    logging.info("Finding indices...")
    vector_splits = snint.apply_indices(
        vector_splits, grid, index_i="raster_i", index_j="raster_j"
    )

    logging.info("Calculating lengths of split segments...")
    geod = Geod(ellps="WGS84")
    vector_splits["unit"] = vector_splits.geometry.apply(geod.geometry_length)
    vector_splits["unit_type"] = "m"
    
    # make a temporary muli-band VRT
    with tempfile.TemporaryDirectory() as temp_dir:
        vrt_path = create_multiband_vrt(rasters, output_dir=temp_dir)
        vector_splits = copy_raster_values_multiband(
            vector_splits, vrt_path, raster_basenames, window
        )

    asset_types = list(vector_splits["asset_type"].unique())
    hazard_cols = [f"hazard-{Path(r).stem}" for r in rasters]

    asset_type_damages = []
    damage_cols = set()
    cost_cols = set()

    # potential bottleneck: process each asset type separately
    for asset_type in (pbar_asset := tqdm(asset_types)):
        pbar_asset.set_postfix({'Processing asset_type': asset_type})
        vector_asset = vector_splits[vector_splits["asset_type"] == asset_type].copy()

        new_columns = {}

        for hazard_col in (pbar_haz := tqdm(hazard_cols, leave=False)):
            pbar_haz.set_postfix({'Processing hazard_col': hazard_col})
            hazard = get_hazard_from_colname(hazard_col)

            design_standard_df = design_standards[hazard]
            design_hazard: str = design_standard_df.loc[asset_type, "design_hazard"]

            defended_col = hazard_col.replace("hazard-", "defended-")
            if design_hazard is None or pd.isna(design_hazard):
                logging.warning(
                    f"\nNo design standard for '{asset_type}' from '{hazard}'. "
                    "Skipping subtraction.\n"
                )
                new_columns[defended_col] = vector_asset[hazard_col]
            else:
                design_standard_col = "hazard-" + design_hazard
                if design_standard_col not in vector_asset.columns:
                    raise ValueError(
                        f"\nDesign standard column '{design_standard_col}' not found "
                        f"for '{asset_type}'.\n"
                    )
                thresholds = vector_asset[design_standard_col].values
                defended_values = (
                    vector_asset[hazard_col].values - thresholds
                ).clip(min=0.0)
                new_columns[defended_col] = defended_values
                logging.info(
                    f"\nSubtracted '{design_standard_col}' from '{hazard_col}' "
                    f"for '{asset_type}'.\n"
                )
            
            defended_array = new_columns[defended_col]
            unit_array = vector_asset["unit"].values
            
            for suffix in ["mean", "min", "max"]:
                damage_function = damage_curves[(hazard, asset_type)][suffix]
                damage_col = defended_col.replace("defended-", "damage-") + "_" + suffix
                
                damage_binary, damage_frac = vectorized_damage_calculation(
                    defended_array, damage_function, unit_array
                )
                
                new_columns[damage_col] = damage_binary
                damage_cols.add(damage_col)

                cost = rehab_costs[hazard].loc[asset_type, f"{suffix}_cost_usd"]
                cost_col = damage_col.replace("damage-", "cost-") + "_" + suffix
                new_columns[cost_col] = cost * damage_frac * unit_array
                cost_cols.add(cost_col)
        
        new_columns_df = pd.DataFrame(new_columns, index=vector_asset.index)
        vector_asset = pd.concat([vector_asset, new_columns_df], axis=1)
        asset_type_damages.append(vector_asset)
    
    vector_splits = pd.concat(asset_type_damages, axis=0)

    if splits_path is not None:
        logging.info(f"Saving split geometries to {splits_path}...")
        vector_splits.to_parquet(splits_path, index=True)

    logging.info("Dissolving split geometries back to original...")
    defended_cols = [hc.replace("hazard-", "defended-") for hc in hazard_cols]
    hazard_cols += defended_cols
    vector = unsplit(
        vector_splits, vector,
        hazard_cols, list(damage_cols), list(cost_cols)
    )
    return vector