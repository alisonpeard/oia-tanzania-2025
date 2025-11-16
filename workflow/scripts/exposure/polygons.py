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
import snail.intersection as snint
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

def _damage_fraction(x, c, damage_function):
    """Wrapper function."""
    x = np.ma.filled(x, 0)
    damage = damage_function(x) # nonlinear / pwl
    return np.mean(damage * c)


def _rehab_cost(x, c, w, damage_function, cost):
    """Wrapper function."""
    x = np.ma.filled(x, 0)
    damage = damage_function(x) # nonlinear / pwl
    damage_units = damage * c * w
    damage_cost = damage_units * cost
    return np.sum(damage_cost)


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


def intersect(vector, rasters, damage_curves, rehab_costs):

    areas = calculate_raster_cell_areas(rasters[0])
    asset_types = list(vector["asset_type"].unique())
    asset_type_damages = []

    for asset_type in asset_types:
        vector_asset = vector[vector["asset_type"] == asset_type].copy()
        for raster in rasters:
            hazard_col = f"hazard-{Path(raster).stem}"
            hazard = get_hazard_from_colname(hazard_col)

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpfile = os.path.join(tmpdir, "asset.shp")
                tmpwts = os.path.join(tmpdir, "weights.tif")
                vector_asset[['id', 'geometry']].to_file(tmpfile)
                with rasterio.open(raster) as src:
                    write_raster(areas, src, tmpwts)

                for prefix in ["min", "mean", "max"]:
                    damage_function = damage_curves[(hazard, asset_type)][prefix]
                    damage_col = hazard_col.replace("hazard-", "damage-") + "_" + prefix

                    for prefix in ["min", "mean", "max"]:
                        cost = rehab_costs[hazard].loc[asset_type, f"{prefix}_cost_usd"]
                        cost_col = damage_col.replace("damage-", "cost-") + "_" + prefix

                        def damage(x, c, w): 
                            return _damage_fraction(x, c, damage_function=damage_function)

                        def rehab_cost(x, c, w): 
                            return _rehab_cost(x, c, w, damage_function=damage_function, cost=cost)

                        hazard_stats = exact_extract(
                            raster, tmpfile, ["max", damage, rehab_cost], 
                            weights=tmpwts,
                            progress=True, output="pandas"
                        )

                        vector_asset[hazard_col] = hazard_stats["max"].astype(float).values
                        vector_asset[damage_col] = hazard_stats["damage"].astype(float).values
                        vector_asset[cost_col] = hazard_stats["rehab_cost"].astype(float).values
        
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