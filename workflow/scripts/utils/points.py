import logging
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
import numpy as np
import tempfile
import rasterio
from osgeo import gdal
from pathlib import Path

import snail.intersection as snint
from utils import naming


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
        raster_files: list[str],
        vector: gpd.GeoDataFrame,
        verify_consistency: bool=False
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


def make_raster_basenames(raster_files:list[str]) -> list[str]:
    raster_basenames = []
    for raster_path in raster_files:
        basename = Path(raster_path).stem  # Gets filename without extension
        raster_basenames.append(basename)
    return raster_basenames


def copy_raster_values(vector_splits:gpd.GeoDataFrame, raster_files:list[str]) -> gpd.GeoDataFrame:
    """
    N.B. this loop is the heavy lifting of this script
    it reads hazard intensity values len(raster_files) * len(vector_splits) times
    """
    raster_basenames = make_raster_basenames(raster_files)
    logging.info("Adding raster values to split geometries")

    # to prevent a fragmented dataframe (and a memory explosion), add series to a dict
    # and then concat afterwards -- do not append to an existing dataframe
    raster_data: dict[str, pd.Series] = {}

    for i in (pbar := tqdm(range(len(raster_files)))):
        pbar.set_postfix({'Processing raster': raster_basenames[i]})
        colname = f"hazard-{raster_basenames[i]}"
        with rasterio.open(raster_files[i]) as src:
            data = src.read(1, masked=True)
            raster_data[colname] = snint.get_raster_values_for_splits(
                vector_splits, data, index_i="raster_i", index_j="raster_j"
            )

    raster_data = pd.DataFrame(raster_data)
    vector_splits = pd.concat([vector_splits, raster_data], axis="columns")
    assert len(raster_data) == len(vector_splits)

    return vector_splits


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
    
    logging.info(
        f"Created multi-band VRT with {len(raster_files)} bands at {output_vrt}"
    )
    return str(output_vrt)


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


def vectorised_damage_calculation(
    defended_values: np.ndarray,
    damage_function: callable,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns:
        damage_units: damaged units (binary: damaged area)
        damage_fraction: damage fraction for cost calculation
    """
    damage_frac = np.vectorize(damage_function)(defended_values)
    return damage_frac


def intersect(
        vector:gpd.GeoDataFrame,
        rasters:list[str],
        damage_curves:dict,
        rehab_costs:dict,
        design_standards:dict,
        splits_path: str = None,
    ) -> gpd.GeoDataFrame:
    """Main intersection function for point geometries."""

    assert len(rasters) > 0, "No rasters provided for intersection."

    logging.info("Constructing grid from rasters...")
    grid, window = process_raster_grid(rasters, vector)
    raster_basenames = make_raster_basenames(rasters)

    logging.info("Processing point geometries...")
    vector = vector.reset_index(drop=True)
    vector_splits = vector.copy()  # No splitting needed for points

    logging.info("Finding indices...")
    vector_splits = snint.apply_indices(
        vector_splits, grid, index_i="raster_i", index_j="raster_j"
    )

    logging.info("Setting all measurements to 1 unit...")
    vector_splits["unit"] = 1
    vector_splits["unit_type"] = "unit"

    # make a temporary multi-band VRT to do all raster reads in one go
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

    for asset_type in (pbar_asset := tqdm(asset_types)):
        pbar_asset.set_postfix({'Processing asset type': asset_type})
        vector_asset = vector_splits[vector_splits["asset_type"] == asset_type].copy()
        
        new_columns = {}
        
        for hazard_col in (pbar_haz := tqdm(hazard_cols)):
            pbar_haz.set_postfix({'Processing hazard column': hazard_col})
            hazard = naming.get_hazard_from_colname(hazard_col)

            design_standard_df = design_standards[hazard]
            design_hazard: str = design_standard_df.loc[asset_type, "design_hazard"]

            defended_col = hazard_col.replace("hazard-", "defended-")
            if design_hazard is None or pd.isna(design_hazard):
                logging.warning(
                    f"\nNo design standard provided for asset type '{asset_type}' from hazard '{hazard}'. "
                    "Skipping subtraction.\n")
                new_columns[defended_col] = vector_asset[hazard_col]
            else:
                design_standard_col = "hazard-" + design_hazard
                if design_standard_col not in vector_asset.columns:
                    raise ValueError(
                        f"\nDesign standard hazard column '{design_standard_col}' not found "
                        f"for asset type '{asset_type}'.\n"
                    )
                thresholds = vector_asset[design_standard_col].values
                defended_values = (
                    vector_asset[hazard_col].values - thresholds
                ).clip(min=0.0)
                new_columns[defended_col] = defended_values
                logging.info(
                    f"\nDesign standards: subtracted '{design_standard_col}' from '{hazard_col}' "
                    f"for '{asset_type}'.\n")
                
            # start vectorized damage and cost calculations
            defended_array = new_columns[defended_col]
            
            for suffix in ["mean", "min", "max"]:
                damage_function = damage_curves[(hazard, asset_type)][suffix]
                damage_col = defended_col.replace("defended-", "damage-") + "_" + suffix
                
                damage_frac = vectorised_damage_calculation(
                    defended_array, damage_function
                )
                
                new_columns[damage_col] = damage_frac
                damage_cols.add(damage_col)
                
                cost = rehab_costs[hazard].loc[asset_type, f"{suffix}_cost_usd"]
                cost_col = damage_col.replace("damage-", "cost-") + "_" + suffix
                new_columns[cost_col] = cost * damage_frac
                cost_cols.add(cost_col)
        
        new_columns_df = pd.DataFrame(new_columns, index=vector_asset.index)
        vector_asset = pd.concat([vector_asset, new_columns_df], axis=1)
        asset_type_damages.append(vector_asset)
    
    vector = pd.concat(asset_type_damages, axis=0).set_index("id")

    if splits_path is not None:
        logging.warning(f"Splits saving not relevant for point geometries, ignoring {splits_path}")

    return vector
