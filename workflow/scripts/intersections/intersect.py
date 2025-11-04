"""Generic script to intersect a vector file with multiple rasters and get the max value"""
import os
from pathlib import Path
import logging
import rasterio
import pandas as pd
import geopandas as gpd
from tqdm import tqdm

import snail.intersection as snint
from pyproj import Geod


def check_geom_type(vector:gpd.GeoDataFrame):
    if vector.empty:
        raise ValueError("Input vector file is empty, cannot proceed.")
    geom_type = vector.geometry.geom_type.unique()
    if len(geom_type) > 1:
        raise ValueError("Input vector has multiple geometry types: %s", geom_type)
    assert vector.crs.to_epsg() == 4326, f"Input vector must be in EPSG:4326, not EPSG:{vector.crs.to_epsg()}"
    return geom_type[0]


def process_raster_grid(raster_files):
    grid = snint.GridDefinition.from_raster(raster_files[0])
    logging.info(f"{grid=}")

    if len(raster_files) > 1:
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


def process_point_data():
    raise NotImplementedError("Point data processing not implemented yet.")


def process_linesting_data(vector:gpd.GeoDataFrame, grid:snint.GridDefinition):
    logging.info("Split edges")
    vector_splits = snint.split_linestrings(
        vector.reset_index(drop=True), grid
    )

    logging.info("Split %d edges into %d pieces", len(vector), len(vector_splits))

    logging.info("Find indices")
    vector_splits = snint.apply_indices(
        vector_splits, grid, index_i="raster_i", index_j="raster_j"
    )

    logging.info("Calculate split segment lengths")
    geod = Geod(ellps="WGS84")
    vector_splits["length_km"] = (
        vector_splits.geometry.progress_apply(geod.geometry_length) / 1e3
    )
    return vector_splits


def process_polygon_data():
    raise NotImplementedError("Polygon data processing not implemented yet.")


def make_raster_basenames(raster_files):
    raster_basenames = []
    for raster_path in raster_files:
        basename = Path(raster_path).stem  # Gets filename without extension
        raster_basenames.append(basename)
    return raster_basenames


def copy_raster_values(vector_splits, raster_files):
    """
    N.B. this loop is the heavy lifting of this script
    it reads hazard intensity values len(raster_files) * len(vector_splits) times
    """
    raster_basenames = make_raster_basenames(raster_files)
    logging.info("Adding raster values to split geometries")

    # to prevent a fragmented dataframe (and a memory explosion), add series to a dict
    # and then concat afterwards -- do not append to an existing dataframe
    raster_data: dict[str, pd.Series] = {}

    for i in tqdm(range(len(raster_files))):
        colname = f"hazard-{raster_basenames[i]}"
        with rasterio.open(raster_files[i]) as src:
            data = src.read(1)
            raster_data[colname] = snint.get_raster_values_for_splits(
                vector_splits, data, index_i="raster_i", index_j="raster_j"
            )

    raster_data = pd.DataFrame(raster_data)
    vector_splits = pd.concat([vector_splits, raster_data], axis="columns")
    assert len(raster_data) == len(vector_splits)
    return vector_splits


def main(input, output, params):

    tqdm.pandas()

    vector = gpd.read_parquet(input.vector)
    geom_type = check_geom_type(vector)
    grid = process_raster_grid(input.rasters)

    if geom_type in ["LineString", "MultiLineString"]:
        vector_splits = process_linesting_data(vector, grid)
    elif geom_type in ["Point", "MultiPoint"]:
        vector_splits = process_point_data(vector, grid)
    elif geom_type in ["Polygon", "MultiPolygon"]:
        vector_splits = process_polygon_data(vector, grid)
    else:
        raise ValueError(f"Unknown geometry type {geom_type}.")
    
    if params.copy_raster_values:
        vector_splits = copy_raster_values(vector_splits, input.rasters)

    logging.info(f"Write data {vector_splits.shape=} {vector_splits.columns=}")
    vector_splits.to_parquet(output.vector)

    logging.info("Done.")


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(process)d %(filename)s %(message)s", level=logging.INFO
    )

    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)