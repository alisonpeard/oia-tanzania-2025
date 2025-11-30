import logging
import os
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
import snail.intersection as snint
from pyproj import Geod
import rasterio
from pathlib import Path


def get_hazard_from_colname(hazcol):
    return hazcol.split("_")[0].split('-')[1]


def process_raster_grid(raster_files:list[str], verify_consistency=False) -> snint.GridDefinition:
    grid = snint.GridDefinition.from_raster(raster_files[0])
    logging.info(f"{grid=}")

    if len(raster_files) > 1 & verify_consistency:
        # Check all raster files use the same grid
        logging.info("Checking raster grid consistency")
        for raster_path in raster_files[1:]:
            other_grid = snint.GridDefinition.from_raster(raster_path)
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
    
    return grid


def make_raster_basenames(raster_files):
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


def intersect(
        vector:gpd.GeoDataFrame, rasters:list[str],
        damage_curves:dict, rehab_costs:dict,
        design_standards:dict
    ) -> gpd.GeoDataFrame:

    grid = process_raster_grid(rasters)

    logging.info("Splitting edges...")
    vector = vector.reset_index(drop=True)
    logging.info("Processing point geometries...")
    vector = vector.reset_index(drop=True)
    vector_splits = vector.copy()  # No splitting needed for points

    logging.info("Finding indices...")
    vector_splits = snint.apply_indices(
        vector_splits, grid, index_i="raster_i", index_j="raster_j"
    )

    vector_splits["unit"] = 1
    vector_splits["unit_type"] = "unit"
    vector_splits = copy_raster_values(vector_splits, rasters)

    asset_types = list(vector_splits["asset_type"].unique())
    hazard_cols = [f"hazard-{Path(r).stem}" for r in rasters]

    asset_type_damages = []
    damage_cols = set()
    cost_cols = set()

    for asset_type in (pbar_asset := tqdm(asset_types)):
        pbar_asset.set_postfix({'Processing asset type': asset_type})
        vector_asset = vector_splits[vector_splits["asset_type"] == asset_type].copy()
        for hazard_col in (pbar := tqdm(hazard_cols)):
            pbar.set_postfix({'Processing hazard column': hazard_col})
            hazard = get_hazard_from_colname(hazard_col)

            design_standard_df = design_standards[hazard]
            design_hazard: str = design_standard_df.loc[asset_type, "design_hazard"]

            defended_col = hazard_col.replace("hazard-", "defended-")
            if design_hazard is None or pd.isna(design_hazard):
                vector_asset[defended_col] = vector_asset[hazard_col]
                logging.warning(f"\nNo design standard provided for asset type '{asset_type}' from hazard '{hazard}'. Skipping subtraction.\n")
            else:
                design_standard_col = "hazard-" + design_hazard
                if design_standard_col not in vector_asset.columns:
                    raise ValueError(
                        f"\nDesign standard hazard column '{design_standard_col}' not found in asset exposure data for asset type '{asset_type}'.\n"
                    )
                thresholds = vector_asset[design_standard_col]
                vector_asset[defended_col] = (vector_asset[hazard_col] - thresholds).clip(lower=0.0)
                logging.info(f"\nDesign standards: subtracted '{design_standard_col}' from '{hazard_col}' for asset type '{asset_type}'.\n")
            
            for suffix in ["mean", "min", "max"]:
                damage_function = damage_curves[(hazard, asset_type)][suffix]
                damage_col = defended_col.replace("defended-", "damage-") + "_" + suffix
                vector_asset[damage_col] = vector_asset[defended_col].apply(damage_function)

                damage_cols.add(damage_col)

                # for suffix in ["min", "mean", "max"]:
                # NOTE: add later if we want all 9 options
                cost = rehab_costs[hazard].loc[asset_type, f"{suffix}_cost_usd"]
                cost_col = damage_col.replace("damage-", "cost-") + "_" + suffix
                vector_asset[cost_col] = cost * vector_asset[damage_col] * vector_asset["unit"]

                cost_cols.add(cost_col)

                vector_asset[damage_col] = (vector_asset[damage_col] > 0).astype(float)
        
        asset_type_damages.append(vector_asset)
    
    vector_splits = pd.concat(asset_type_damages, axis=0)

    return vector_splits.set_index("id")