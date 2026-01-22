"""
This script patches the results from the snakemake run to fix known issues.

Ideally hazards won't need post-processing this time.

Cleaning implemented:
1. replace roads asset_type with road class from reference data
2. replace bridges and culverts asset_type with structure type from config
3. reformat railway asset_type strings for display
4. group airports, maritime ports, and iww ports into transport hubs

NOTE: add hazard post-processing as needed.
"""
# %%
import os
from glob import glob
from tqdm import tqdm
from pathlib import Path
import pandas as pd
import geopandas as gpd

import ttra
from oi_risk import config


REDO = False
HAZARDS = [
    "fluvial",
    "pluvial",
    "coastal",
    "landslide",
    "cyclone",
    "hd35",
    "tasmax"
]
ASSETS = [
    "tza_roads_edges",
    "tza_roads_bridges_and_culverts_nodes",
    "tza_railway_edges",
    "tza_hubs_polygons"
]


def prepare_roads_data(asset_dir, ref_dir, subregion=None, verbose=False):
    def format_asset(x:str) -> str:
        return x.title()
    asset = ttra.load_asset_data(asset_dir, subregion=subregion, verbose=verbose)
    if asset.empty:
        return asset

    if subregion:
        ref_path = os.path.join(ref_dir, subregion + ".geoparquet")
        ref = gpd.read_parquet(ref_path)
    else:
        ref_files = glob(os.path.join(ref_dir, "*.geoparquet"))
        ref_dfs = [gpd.read_parquet(f).reset_index() for f in ref_files]
        ref = pd.concat(ref_dfs, axis=0, ignore_index=True)
        ref = ref.copy() # de-fragment
    ref["asset_type"] = ref["asset_type"].str.lower()
    ref = ref.set_index("id")
    asset = asset.set_index("id")
    asset = asset.join(ref[["road_class"]], how="left")
    asset["asset_type"] = asset["road_class"].copy()
    asset["asset_type"] = asset["asset_type"].apply(format_asset)
    asset = asset.drop(columns=["road_class"])
    return asset.reset_index()


def prepare_roads_bridges_and_culverts_data(
        asset_dir, config_dir, subregion=None, verbose=False):
    def format_asset(x:str) -> str:
        x = x.split(" ")[-1]
        return x.title()
    asset = load_asset_data(asset_dir, subregion=subregion, verbose=verbose)
    if asset.empty:
        return asset
    config_path = config_dir / "bridges_and_culverts_types.csv"
    ref = pd.read_csv(config_path)
    ref["asset_class"] = ref["asset_class"].str.lower()
    class_dict = ref.set_index("asset_type")["asset_class"].to_dict()
    asset["asset_type"] = asset["asset_type"].map(class_dict)
    asset["asset_type"] = asset["asset_type"].apply(format_asset)
    return asset


def prepare_railway_data(asset_dir, subregion=None, verbose=False):
    def format_asset(x:str) -> str:
        gauge, structure, status = x.split("_")
        gauge = gauge.upper()
        return f"{gauge} {structure}\n({status})"
    asset = load_asset_data(asset_dir, subregion=subregion, verbose=verbose)
    if asset.empty:
        return asset
    disused = asset["asset_type"].str.contains("disused", case=False, na=False)
    asset = asset[~disused].copy()
    asset["asset_type"] = asset["asset_type"].apply(format_asset)
    return asset


def prepare_asset(asset_geom, asset_dir, subregion=None,
                    config_dir=None, reference_dir=None,
                    verbose=False):
    """Prepare asset data based on asset geometry type"""
    if asset_geom == "tza_roads_edges":
        asset = prepare_roads_data(
            asset_dir,
            ref_dir=reference_dir,
            subregion=subregion,
            verbose=verbose
        )
    elif asset_geom == "tza_roads_bridges_and_culverts_nodes":
        asset = prepare_roads_bridges_and_culverts_data(
            asset_dir,
            config_dir=config_dir,
            subregion=subregion,
            verbose=verbose,
        )
    elif asset_geom == "tza_railway_edges":
        asset = prepare_railway_data(
            asset_dir,
            subregion=subregion,
            verbose=verbose,
        )
    elif asset_geom == "tza_hubs_polygons":
        airports = load_asset_data(
            str(asset_dir).replace("hubs", "airports"),
            subregion=subregion,
            verbose=verbose
        )
        airports["asset_type"] = "Airport"

        maritime_ports = load_asset_data(
            str(asset_dir).replace("hubs", "maritime_ports"),
            subregion=subregion,
            verbose=verbose
        )
        maritime_ports["asset_type"] = "Maritime port"
        iww_ports = load_asset_data(
            str(asset_dir).replace("hubs", "iww_ports"),
            subregion=subregion,
            verbose=verbose
        )
        iww_ports["asset_type"] = "IWW port"
        asset = pd.concat([airports, maritime_ports, iww_ports], ignore_index=True)
    else:
        raise ValueError(f"Unknown asset geometry type: {asset_geom}")
    
    return asset


if __name__ == "__main__":
    # configure paths
    config = config.load_config()
    indir = Path(config['paths']['snakemake_data']) / "intersections"
    reference_dir  = Path(config["paths"]["snakemake_data"]) / "assets"
    config_dir = Path(config['paths']['snakemake_data']) / "config"
    outdir = Path(config['paths']['results']) / "intersections"
    outdir.mkdir(parents=True, exist_ok=True)

    # load the subregions
    regions_file = Path(config['paths']['snakemake_data']) / "config" / "subregions.txt"
    with open(regions_file, "r") as f:
        subregions = [line.strip() for line in f.readlines()]

    for asset_geom in (pbar := tqdm(ASSETS)):
        for hazard in HAZARDS:
            for subregion in subregions:

                outpath = outdir / asset_geom / hazard / subregion / "profile.geoparquet"

                if os.path.exists(outpath) and not REDO:
                    continue

                pbar.set_postfix(asset=asset_geom, hazard=hazard, subregion=subregion)
                
                outpath.parent.mkdir(parents=True, exist_ok=True)
                asset_dir = indir / asset_geom / hazard
                refdir_asset = reference_dir / asset_geom

                asset = prepare_asset(
                    asset_geom=asset_geom,
                    asset_dir=asset_dir,
                    subregion=subregion,
                    config_dir=config_dir,
                    reference_dir=refdir_asset,
                    verbose=True
                )

                asset.to_parquet(outpath)
                print(f"Saved cleaned data to {outpath}")

# %%
