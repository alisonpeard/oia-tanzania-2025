import os
import logging
from pathlib import Path
import pandas as pd
import geopandas as gpd
from scipy.interpolate import interp1d

from utils import points
from utils import linestrings
from utils import polygons


ASSET_COLS = ["id", "asset_type", "geometry"]


def get_hazard_from_filename(raster_path):
    return Path(raster_path).stem.split('_')[0]


def make_damage_function(df:pd.DataFrame, suffix="mean"):
    hazard_intensity, damage_fraction = (
        df["intensity"],
        df["damage_fraction" + "_" + suffix],
    )
    bounds = tuple(f(damage_fraction) for f in (min, max))
    return interp1d(
        hazard_intensity,
        damage_fraction,
        kind="linear",
        fill_value=bounds,
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


def prepare_damage_curves(damage_curve_dir, hazards, asset_types) -> dict:
    damage_curves = {}
    for hazard in hazards:
        damage_curve_hazard_dir = os.path.join(damage_curve_dir, hazard)
        for asset_type in asset_types:
            damage_curve_path = os.path.join(damage_curve_hazard_dir, f"{asset_type}.csv")
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


def get_rasters(hazard_dir:list[str]) -> list[str]:
    """Filter out non-tif files from the input raster list"""
    rasters = os.listdir(hazard_dir)
    filtered_rasters = [r for r in rasters if r.endswith('.tif')]
    filtered_rasters = [os.path.join(hazard_dir, r) for r in filtered_rasters]
    if not filtered_rasters:
        raise ValueError("No valid .tif raster files found in input.")
    logging.info(f"Found {len(filtered_rasters)} valid raster files.")
    return filtered_rasters


def main(input, output, params):

    vector = gpd.read_parquet(input.vector, columns=ASSET_COLS)
    geom_type = check_geoms(vector)

    rasters = get_rasters(input.hazard_dir)
    _ = linestrings.process_raster_grid(rasters, verify_consistency=True)

    asset_types = list(vector["asset_type"].unique())
    hazards = [get_hazard_from_filename(r) for r in rasters]

    damage_curves = prepare_damage_curves(params.damage_curve_dir, hazards, asset_types)
    rehab_costs = prepare_rehab_costs(params.rehab_cost_dir, hazards)

    if geom_type in ["Point", "MultiPoint"]:
        vector = points.intersect(vector, rasters, damage_curves, rehab_costs)
    elif geom_type in ["LineString", "MultiLineString"]:
        vector = linestrings.intersect(vector, rasters, damage_curves, rehab_costs)
    elif geom_type in ["Polygon", "MultiPolygon"]:
        vector = polygons.intersect(vector, rasters, damage_curves, rehab_costs)
    else:
        raise ValueError(f"Unknown geometry type {geom_type}.")
    
    vector.to_parquet(output.vector)

    logging.info("Done.")


if __name__ == "__main__":

    logging.basicConfig(
        format="%(asctime)s %(process)d %(filename)s %(message)s", level=logging.INFO
    )

    input = snakemake.input
    output = snakemake.output
    params = snakemake.params

    result = main(input, output, params)