"""
Post-process results for reporting. Ideally hazards would not need
post-processing because it would be done before snakemake.

Add new post-processing steps as needed.

NOTE: don't do heat here (handled separately)

Post-processing implemented:
    Roads:
        - asset_type <- road_class (using ref data)
    Rail:
        - format strings nicer
    Bridges:
        - asset_type <- structure_type (using config file)
    Hubs:
        - group airports, maritime ports, iww ports
    Landslides:
        - scale damages and costs by 0.3
    Remove all excluded subregions


Inputs:
    snakemake_results/intersections/*/profile.geoparquet

Outputs:
    results/intersections/*/profile.geoparquet
    results/intersections/missing_profiles.csv
"""
# %%
import os
import shutil
import subprocess
from glob import glob
from tqdm import tqdm
from pathlib import Path
import pandas as pd
import geopandas as gpd
from warnings import warn
from itertools import product
import ttra
from oi_risk import config


remake = False
verbose = True
hazards = [
    "fluvial",
    "pluvial",
    "coastal",
    "landslide",
    "cyclone"
]
assets = [
    "tza_roads_edges",
    "tza_roads_bridges_and_culverts_nodes",
    "tza_railway_edges",
    "tza_hubs_polygons"
]

exclude = [
    'kaskazini_unguja', 'kusini_unguja',
    'mjini_magharibi',
    'kaskazini_pemba','kusini_pemba' 
]

def scale_landslide_risk(asset:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    warn("Scaling landslide costs & damages by 0.3. Won't be necessary in future.")
    landslide_cols = [col for col in asset.columns if "landslide" in col]
    cost_cols = [col for col in asset.columns if "cost-" in col]
    damage_cols = [col for col in asset.columns if "damage-" in col]
    scale_cols = list(set(landslide_cols) & set(cost_cols + damage_cols))
    asset[scale_cols] *= 0.3
    return asset


def filter_output_stats(asset:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Remove any min_mean etc and set max_max -> max"""
    cost_cols = [col for col in asset.columns if col.startswith("cost")]

    def fix(x:str) -> bool:
        xlist = x.split('_')
        x0, x1 = xlist[-2], xlist[-1]
        if x0 == x1:
            return '_'.join(xlist[:-2] + [x0])
        else:
            return None
    
    rename_map = {col: fix(col) for col in cost_cols}
    cols_to_drop = [col for col, new in rename_map.items() if new is None]
    cols_to_rename = {col: new for col, new in rename_map.items() if new is not None}

    asset = asset.drop(columns=cols_to_drop)
    asset = asset.rename(columns=cols_to_rename)

    return asset


def assign_road_class(asset, ref, how='left', verbose=False):
    """Assign road class based on id.
    Join needs to only consider subset of split id
    """
    def format_id(id):
        return '_'.join(id.split('_')[:3])
    
    asset["id_parent"] = asset["id"].apply(format_id)
    ref["id_parent"] = ref["id"].apply(format_id)
    asset = asset.set_index('id_parent')
    ref = ref.set_index('id_parent')
    asset = asset.join(ref[['road_class']], how=how)

    if asset['road_class'].isnull().any():
        nnan = asset['road_class'].isnull().sum()
        asset = asset.dropna(subset="road_class")
        if verbose:
            print(f"Warning: {nnan} nans dropped in road_class")

    return asset.set_index('id')


def prepare_roads_data(asset_dir, ref_dir, subregion=None, verbose=False):
    def format_asset(x:str) -> str:
        return x.title()
    
    asset = ttra.load_risk_profile(asset_dir, subregion=subregion, verbose=verbose)
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
    asset = assign_road_class(asset, ref, how='left')
    asset["asset_type"] = asset["road_class"].copy()
    asset["asset_type"] = asset["asset_type"].apply(format_asset)
    asset = asset.drop(columns=["road_class"])
    return asset.reset_index()


def prepare_roads_bridges_and_culverts_data(
        asset_dir, cfgdir, subregion=None, verbose=False):
    def format_asset(x:str) -> str:
        x = x.split(" ")[-1]
        return x.title()
    asset = ttra.load_risk_profile(asset_dir, subregion=subregion, verbose=verbose)
    if asset.empty:
        return asset
    config_path = cfgdir / "bridges_and_culverts_types.csv"
    ref = pd.read_csv(config_path)
    ref["asset_class"] = ref["asset_class"].str.lower()
    class_dict = ref.set_index("asset_type")["asset_class"].to_dict()
    asset["asset_type"] = asset["asset_type"].map(class_dict)
    asset["asset_type"] = asset["asset_type"].apply(format_asset)
    return asset


def handle_railway_planning(asset:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Table 4.2 in report."""
    # set up all the masks
    disused = asset["asset_type"].str.contains("disused", case=False, na=False)
    proposed = asset["asset_type"].str.contains("proposed", case=False)
    planned = asset["asset_type"].str.contains("planned", case=False)
    construction = asset["asset_type"].str.contains("construction", case=False)

    cols_base = [col for col in asset.columns if any(yr in col for yr in ["2010", "2015", "2020"])]
    cols_2030 = [col for col in asset.columns if "2030" in col]
    cols_2050 = [col for col in asset.columns if "2050" in col]

    asset.loc[disused, cols_base + cols_2030 + cols_2050] = 0
    asset.loc[construction, cols_base] = 0
    asset.loc[proposed, cols_base + cols_2030] = 0
    asset.loc[planned, cols_base + cols_2030 + cols_2050] = 0

    return asset


def prepare_railway_data(asset_dir, subregion=None, verbose=False):
    def format_asset(x:str) -> str:
        gauge, structure, status = x.split("_")
        gauge = gauge.upper()
        return f"{gauge} {structure}\n({status})"
    
    asset = ttra.load_risk_profile(asset_dir, subregion=subregion, verbose=verbose)
    if asset.empty:
        return asset
    asset = handle_railway_planning(asset)
    asset["asset_type"] = asset["asset_type"].apply(format_asset)
    return asset


def prepare_asset(asset_geom, asset_dir, subregion=None,
                    cfgdir=None, refdir=None,
                    verbose=False):
    """Prepare asset data based on asset geometry type"""
    if asset_geom == "tza_roads_edges":
        asset = prepare_roads_data(
            asset_dir,
            ref_dir=refdir,
            subregion=subregion,
            verbose=verbose
        )
    elif asset_geom == "tza_roads_bridges_and_culverts_nodes":
        asset = prepare_roads_bridges_and_culverts_data(
            asset_dir,
            cfgdir=cfgdir,
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
        airports = ttra.load_risk_profile(
            str(asset_dir).replace("hubs", "airports"),
            subregion=subregion,
            verbose=verbose
        )
        airports["asset_type"] = "Airport"

        maritime_ports = ttra.load_risk_profile(
            str(asset_dir).replace("hubs", "maritime_ports"),
            subregion=subregion,
            verbose=verbose
        )
        maritime_ports["asset_type"] = "Maritime port"
        iww_ports = ttra.load_risk_profile(
            str(asset_dir).replace("hubs", "iww_ports"),
            subregion=subregion,
            verbose=verbose
        )
        iww_ports["asset_type"] = "IWW port"
        asset = pd.concat([airports, maritime_ports, iww_ports], ignore_index=True)
    else:
        raise ValueError(f"Unknown asset geometry type: {asset_geom}")
    if not asset.empty:
        asset = filter_output_stats(asset)
    return asset


if __name__ == "__main__":
    # configure paths
    config = config.load_config()
    indir = Path(config['paths']['snakemake']) / "results" / "intersections"
    refdir  = Path(config["paths"]["snakemake"]) / "temp" / "assets"
    cfgdir = Path(config['paths']['snakemake']) / "input" / "config"
    outdir = Path(config['paths']['results']) / "intersections"
    outdir.mkdir(parents=True, exist_ok=True)

    # load the subregions
    regions_file = Path(config['paths']['snakemake']) / "temp" / "config" / "subregions.txt"
    with open(regions_file, "r") as f:
        subregions = [line.strip() for line in f.readlines()]

    missing = []
    combinations = list(product(assets, hazards, subregions))
    for asset_geom, hazard, subregion in (pbar := tqdm(combinations, leave=False)):
        pbar.set_postfix(asset=asset_geom, hazard=hazard, subregion=subregion)

        outpath = outdir / asset_geom / hazard / subregion / "profile.geoparquet"

        if subregion in exclude and outpath.exists():
            tmpdir = outdir / asset_geom / hazard / subregion
            print(f"Removing {tmpdir} from results.")
            shutil.rmtree(tmpdir)
            missing.append([asset_geom, hazard, subregion, "excluded"])
            continue

        if outpath.exists() and not remake:
            continue

        pbar.set_postfix(asset=asset_geom, hazard=hazard, subregion=subregion)
        
        outpath.parent.mkdir(parents=True, exist_ok=True)
        asset_dir = indir / asset_geom / hazard
        refdir_asset = refdir / asset_geom

        try:
            asset = prepare_asset(
                asset_geom=asset_geom,
                asset_dir=asset_dir,
                subregion=subregion,
                cfgdir=cfgdir,
                refdir=refdir_asset,
                verbose=verbose
            )
            if hazard == "landslide":
                asset = scale_landslide_risk(asset)
            asset.to_parquet(outpath)
            if verbose: print(f"Saved cleaned data to {outpath}")
        
        except FileNotFoundError as e:
            missing.append([asset_geom, hazard, subregion, "missing"])
            continue

missing_df = pd.DataFrame(missing, columns=["asset_geom", "hazard", "subregion", "reason"])
missing_df = missing_df.groupby(["asset_geom", "hazard"]).agg(
    count=("subregion", "count"),
    subregions=("subregion", list)
)
missing_df["subregions"] = missing_df["subregions"].str.join(";")
missing_df.to_csv(outdir / "missing_profiles.csv")
print(f"\nMissing profiles:\n{missing_df}")

subprocess.run(["say", "done"])
# %%