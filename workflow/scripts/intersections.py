import os
import logging
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.interpolate import interp1d

from utils import points
from utils import linestrings
from utils import polygons
from utils import naming


ASSET_COLS = ["id", "asset_type", "geometry"]


def make_damage_function(df:pd.DataFrame, suffix="mean"):
    hazard_intensity, damage_fraction = (
        df["intensity"],
        df["damage_fraction" + "_" + suffix],
    )
    # assuming damage_fraction is sorted by intensity
    lower = damage_fraction.iloc[0]
    upper = damage_fraction.iloc[-1]
    return interp1d(
        hazard_intensity,
        damage_fraction,
        kind="linear",
        fill_value=(lower, upper),
        bounds_error=False,
    )


def check_geoms(vector:gpd.GeoDataFrame):
    if vector.empty:
        raise ValueError("Input vector file is empty, cannot proceed.")
    geom_type = vector.geometry.geom_type.unique()
    if len(geom_type) > 1:
        raise ValueError("Input vector has multiple geometry types: %s", geom_type)
    assert vector.crs.to_epsg() == 4326, f"Input vector must be in EPSG:4326, not EPSG:{vector.crs.to_epsg()}"
    logging.debug(f"Invalid geometries: {(~vector.geometry.is_valid).sum()}")
    logging.debug(f"Empty geometries: {vector.geometry.is_empty.sum()}")
    logging.debug(f"Null geometries: {vector.geometry.isna().sum()}")
    return geom_type[0]


def make_dummy_damage_df(hazard, asset_type):
    logging.warning(f"No damage curve found for hazard {hazard} and asset type {asset_type}. Assuming zero damage.")
    return pd.DataFrame({
        "intensity": [0.0, 1.0],
        "damage_fraction_min": [0.0, float("nan")],
        "damage_fraction_mean": [0.0, float("nan")],
        "damage_fraction_max": [0.0, float("nan")],
    }, dtype=float)


def prepare_damage_curves(damage_curve_dir, hazards, asset_types) -> dict:
    damage_curves = {}
    for hazard in hazards:
        damage_curve_hazard_dir = os.path.join(damage_curve_dir, hazard)
        for asset_type in asset_types:
            damage_curve_path = os.path.join(damage_curve_hazard_dir, f"{asset_type}.csv")
            if not os.path.exists(damage_curve_path):
                logging.warning(f"No damage curve found for hazard: {hazard} and asset type: {asset_type}.")
                print(f"WARNING: No damage curve found for hazard: {hazard} and asset type: {asset_type}.")
                damage_df = make_dummy_damage_df(hazard, asset_type)
            else:
                damage_df = pd.read_csv(damage_curve_path, comment='#')
            
            damage_curves[(hazard, asset_type)] = {
                suffix: make_damage_function(damage_df, suffix=suffix)
                for suffix in ["min", "mean", "max"]
            }
    return damage_curves


def prepare_rehab_costs(rehab_cost_dir, hazards) -> dict:
    rehab_costs = {}
    for hazard in hazards:
        rehab_cost_file = os.path.join(rehab_cost_dir, f"{hazard}.csv")
        rehab_cost_df = pd.read_csv(rehab_cost_file, comment='#')
        rehab_cost_df = rehab_cost_df.set_index("asset_type", drop=True)
        rehab_costs[hazard] = rehab_cost_df
    return rehab_costs


def prepare_design_standards(protection_dir, hazards) -> dict:
    design_standards = {}
    for hazard in hazards:
        logging.info(f"\nLoading design standards for hazard: {hazard}")
        design_standards[hazard] = pd.read_csv(
            os.path.join(protection_dir, f"{hazard}.csv"), comment='#'
        ).set_index("asset_type", drop=True)
        logging.info(f"Loaded: {os.path.join(protection_dir, f'{hazard}.csv')}")
    return design_standards


def get_rasters(hazard_dir:list[str]) -> list[str]:
    """Filter out non-tif files from the input raster list"""
    rasters = os.listdir(hazard_dir)
    filtered_rasters = [r for r in rasters if r.endswith('.tif')]
    filtered_rasters = [os.path.join(hazard_dir, r) for r in filtered_rasters]
    if not filtered_rasters:
        raise ValueError("No valid .tif raster files found in input.")
    logging.info(f"Found {len(filtered_rasters)} valid raster files.")
    return filtered_rasters


def separate_hazards(vector: gpd.GeoDataFrame) -> dict[str, gpd.GeoDataFrame]:
    base_cols = ['id', 'asset_type', 'unit', 'unit_type', 'geometry']
    prefixes = ('hazard-', 'damage-', 'cost-')
    
    hazard_cols = [col for col in vector.columns if col.startswith(prefixes)]
    hazards = {naming.get_hazard_from_colname(col) for col in hazard_cols}
    
    hazard_vectors = {}
    for hazard in hazards:
        cols = base_cols + [col for col in hazard_cols if naming.get_hazard_from_colname(col) == hazard]
        hazard_vectors[hazard] = vector[cols].copy()
    
    return hazard_vectors


def main(input, output, params):
    asset_file = os.path.join(input.asset_dir, f"{params.subregion}.geoparquet")
    vector = gpd.read_parquet(asset_file, columns=ASSET_COLS)

    if vector.empty:
        vector.to_parquet(output.vector)
        logging.info("Input asset file is empty, saved empty output.")
        return

    geom_type = check_geoms(vector)

    rasters = get_rasters(input.hazard_dir)
    rasters = [r for r in rasters if naming.get_hazard_from_filename(r) in params.hazard]

    if len(rasters) == 0:
        raise ValueError(f"No aligned rasters found for hazard '{params.hazard}'.")

    _ = linestrings.process_raster_grid(rasters, vector, verify_consistency=True)

    asset_types = list(vector["asset_type"].unique())
    hazards = [naming.get_hazard_from_filename(r) for r in rasters]

    damage_curves = prepare_damage_curves(params.damage_curve_dir, hazards, asset_types)
    rehab_costs = prepare_rehab_costs(params.rehab_cost_dir, hazards)
    design_standards = prepare_design_standards(params.protection_dir, hazards)

    if geom_type in ["Point", "MultiPoint"]:
        vector = points.intersect(
            vector, rasters, damage_curves, rehab_costs, design_standards,
            splits_path=params.splits_path
        )
    elif geom_type in ["LineString", "MultiLineString"]:
        vector = linestrings.intersect(
            vector, rasters, damage_curves, rehab_costs, design_standards,
            splits_path=params.splits_path
        )
    elif geom_type in ["Polygon", "MultiPolygon"]:
        vector = polygons.intersect(
            vector, rasters, damage_curves, rehab_costs, design_standards,
            splits_path=params.splits_path)
    else:
        raise ValueError(f"Unknown geometry type {geom_type}.")
        
    vector.to_parquet(output.vector)

    logging.info("Done.")


if __name__ == "__main__":

    logging.basicConfig(
        filename=snakemake.log.file,
        format="%(asctime)s %(process)d %(filename)s %(message)s",
        level=logging.INFO
    )

    input = snakemake.input
    output = snakemake.output
    params = snakemake.params

    result = main(input, output, params)