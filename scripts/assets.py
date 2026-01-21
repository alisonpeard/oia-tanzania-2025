"""
Prepare infrastructure assets for snakemake direct damage analysis.
"""
# %%
import os
import pandas as pd
import geopandas as gpd
from pathlib import Path
from tqdm import tqdm

from oi_risk import config


REDO = True
ASSETS = [
    "tza_roads_edges", "tza_roads_bridges_and_culverts_nodes", "tza_railway_edges",
    "tza_iww_ports_polygons", "tza_maritime_ports_polygons", "tza_airports_polygons"
]


def main(config, redo=False):
    indir = Path(config['paths']['processed_data']) / "infrastructure" / "geoparquets"
    outdir = Path(config['paths']['snakemake_data']) / "assets" / "raw"
    configdir = Path(config['paths']['snakemake_data']) / "config"
    os.makedirs(outdir, exist_ok=True)

    asset_types = []

    for asset in (pbar := tqdm(ASSETS)):
        pbar.set_postfix(asset=asset)

        inpath = indir / f"{asset}.parquet"
        outpath = outdir / f"{asset}.geoparquet"

        if outpath.exists() and not REDO:
            print(f"  Skipping existing: {outpath}")
            continue

        if asset == "tza_roads_bridges_and_culverts_nodes":
            inpath = inpath.with_name(inpath.name.replace("_nodes", ""))

        gdf = gpd.read_parquet(inpath)

        if asset == "tza_railway_edges":
            gdf = gdf[gdf['status'] != 'disused'].copy()
        
        gdf.to_parquet(outpath)
        print(f"\nSaved:\n  {outpath}")

        gdf["asset"] = asset
        asset_types.append(gdf[["asset", "asset_type"]].drop_duplicates())

    asset_types = pd.concat(asset_types).drop_duplicates().sort_values(["asset", "asset_type"])
    asset_types_outpath = configdir / "asset_types.csv"
    asset_types.to_csv(asset_types_outpath, index=False)


if __name__ == '__main__':
    CONFIG = config.load_config()
    main(CONFIG, REDO)
# %%

