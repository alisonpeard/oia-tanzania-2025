"""
Prepare admin data for snakemake direct damage analysis.
Needs to have "subregion" field and be all lowe case with underscores.
"""
# %%
import os
import geopandas as gpd
from pathlib import Path

from oi_risk import config


REDO = False


def format_subregion_name(subregion:str) -> str:
    subregion = subregion.lower()
    subregion = subregion.replace(" ", "_")
    subregion = subregion.replace("/", "-")
    return subregion


if __name__ == '__main__':
    config = config.load_config()
    infile = Path(config['paths']['processed_data']) / "admin" / "Admin01_regions" / "TZA_regions_dissolved.gpkg"
    outfile = Path(config['paths']['snakemake']) / "input" / "admin" / "level01.geoparquet"
    os.makedirs(outfile.parent, exist_ok=True)

    gdf = gpd.read_file(infile)
    gdf["subregion"] = gdf["reg_name"].apply(format_subregion_name)
    gdf[["subregion", "geometry"]].to_parquet(outfile)

# %%
