"""
Make mini asset datasets for development.
"""
# %%
import os
import yaml
import geopandas as gpd
from collections import Counter

with open("../../workflow/config.yaml") as f:
    cfg = yaml.safe_load(f)

input_path = cfg["inputs"]
damage_path = os.path.join("config", "damage_curves")
cost_path = os.path.join("config", "rehab_costs")
asset_dir = os.path.join(input_path, "input", "assets", "geoparquets")
mini_asset_dir = os.path.join(input_path, "input", "mini_assets", "geoparquets")

os.makedirs(os.path.join(mini_asset_dir), exist_ok=True)
# asset_files = [f for f in os.listdir(asset_dir) if f.endswith(".parquet")]
asset_files = ["tza_roads_edges.parquet", "tza_airports_polygons.parquet"]

asset_file = next(iter(asset_files))
for asset_file in asset_files:
    print(f"Processing {asset_file}")
    asset = gpd.read_parquet(os.path.join(asset_dir, asset_file)) 
    asset_types = asset["asset_type"].unique()
    type_counts = Counter(asset["asset_type"])
    type_counts = dict(sorted(type_counts.items(), key=lambda item: item[1], reverse=True))
    asset_type = next(iter(asset_types))
    print(f"  Taking asset type {asset_type} with {type_counts[asset_type]} records")
    mini_asset = asset[asset["asset_type"] == asset_type]
    mini_asset.to_parquet(os.path.join(mini_asset_dir,  asset_file))

# %%