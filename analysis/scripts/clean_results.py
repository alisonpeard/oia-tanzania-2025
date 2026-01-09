"""
This script patches the results from the snakemake run to fix known issues.

NB: only replaces cost and damage, not hazard.

Cleaning required:
1. Interpolate missing pluvial_2080_ssp245_rp00200
2. Interpolate missing coastal_2050_ssp585_rp00050
3. Multipled airport costs by 0.1
4. Replace asset types with output naming (road class, structure type, etc.)
5. Change "_stat_stat" -> "_stat" in cost columns
"""
# %%
indir = "/Users/alison/Local/github/oia-tanzania-2025/results/risk"
outdir = "/Users/alison/Local/github/oia-tanzania-2025/results/risk_cleaned"

hazards = [
    # "fluvial",
    # "pluvial",
    # "coastal",
    # "landslide",
    # "cyclone",
    "hd35",
    "tasmax"
]

assets = [
    "tza_roads_edges",
    "tza_roads_bridges_and_culverts_nodes",
    "tza_railway_edges",
    "tza_hubs_polygons"
]

import os
from tqdm import tqdm
import utils.data as du

# asset_geom = "tza_railway_edges"
# hazard = "fluvial"
subregions_file = "/Users/alison/Local/github/oia-tanzania-2025/results/assets/subregions.txt"

# load text file
with open(subregions_file, "r") as f:
    subregions = [line.strip() for line in f.readlines()]

for asset_geom in assets:
    for hazard in hazards:
        print(f"Processing {asset_geom} - {hazard}")
        for subregion in (pbar := tqdm(subregions)):
            pbar.set_postfix(subregion=subregion)
            outpath = os.path.join(outdir, asset_geom, hazard, subregion, "profile.geoparquet")

            if os.path.exists(outpath):
                print(f"Skipping {subregion} - already done")
                continue
            
            os.makedirs(os.path.dirname(outpath), exist_ok=True)

            asset_dir = os.path.join(indir, asset_geom, hazard)
            asset = du.prepare_asset(
                asset_geom=asset_geom,
                asset_dir=asset_dir,
                subregion=subregion,
                verbose=True,
                metric_type="profile.geoparquet"
            )
            if not asset.empty:
                asset = du.prepare_hazard_data(asset, hazard)

            asset.to_parquet(outpath)
            print(f"Saved cleaned data to {outpath}")
# %%
import geopandas as gpd
tmp_path = os.path.join(outdir, "tza_railway_edges", "pluvial", "profile.geoparquet")
tmp = gpd.read_parquet(tmp_path)
tmp.head()
# %%
