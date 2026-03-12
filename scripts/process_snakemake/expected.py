"""
Post-process results for reporting. Ideally hazards would not need
post-processing because it would be done before snakemake.

Cleaning implemented:
    Roads:
        - asset_type <- road_class (using ref data)
    Rail:
        - format strings nicer
    Bridges:
        - asset_type <- structure_type (using config file)
    Hubs:
        - group airports, maritime ports, iww ports into 'hubs'
    Landslides:
        - scale damages and costs by 0.3
    Costs:
        - change stat0_stat1 syntax to stat0 and drop cases where stat0≠stat1
    

Inputs:
    snakemake_results/intersections/*/expected.parquet

Outputs:
    results/intersections/*/expected.parquet
    results/intersections/missing_expected.csv


NOTE: don't do heat here (handled separately)
NOTE: add hazard post-processing as needed.
NOTE: newest snakemake annual.parquet -> expected.parquet
NOTE: using snakemake_results but new results in snakemake_data
"""
# %%
import os
from glob import glob
from tqdm import tqdm
from pathlib import Path
import pandas as pd
import geopandas as gpd
from warnings import warn

import ttra
from oi_risk import config


REDO = True
HAZARDS = [
    # "fluvial",
    # "pluvial",
    # "coastal",
    "landslide",
    # "cyclone"
]
ASSETS = [
    "tza_roads_edges",
    "tza_roads_bridges_and_culverts_nodes",
    "tza_railway_edges",
    "tza_hubs_polygons"
]


def scale_landslide_risk(asset: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    warn("Scaling landslide costs & damages by 0.3. Won't be necessary in future.")
    id_scale = asset[asset["metric"].isin(["cost", "damage"])].index
    asset.loc[id_scale, "expected"] *= 0.3
    return asset


def filter_output_stats(asset:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Remove any min_mean etc and set max_max -> max"""
    def checksame(x:str) -> bool:
        x0, x1 = x.split('_')
        if x0 == x1:
            return x0
        else:
            return float("nan")

    cost_mask = asset["metric"] == "cost"
    asset.loc[cost_mask, "range"] = asset.loc[cost_mask, "range"].apply(checksame)
    asset = asset.dropna(subset="range")
    return asset


def verify_ranges(asset:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Check no min > mean or mean > max"""
    groupby = [col for col in asset.columns if col != "expected"]
    grouped = asset.groupby(groupby).agg("sum").unstack("range").reset_index()
    groupby = [col for col in groupby if col != "range"]
    grouped.columns = groupby + ["max", "mean", "min"]

    if any(grouped["min"] > grouped["mean"]):
        warn("min > mean, setting min <- mean")
        mask = grouped["min"] > grouped["mean"]
        grouped.loc[mask, "min"] = grouped.loc[mask, "mean"]
    
    if any(grouped["max"] < grouped["mean"]):
        warn("mean > max, setting max <- mean")
        mask = grouped["max"] < grouped["mean"]
        grouped.loc[mask, "max"] = grouped.loc[mask, "mean"]
    
    grouped = grouped.set_index(groupby)
    grouped.columns.name = "range"
    asset = grouped.stack("range").rename("expected").reset_index()
    return asset


def assign_road_class(asset, ref, how='left'):
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
        print(f"Warning: {nnan} nans dropped in road_class")

    return asset.set_index('id')


def prepare_roads_data(asset_dir, ref_dir, subregion=None, verbose=False):
    def format_asset(x:str) -> str:
        return x.title()
    
    asset = ttra.load_risk_expected(asset_dir, subregion=subregion, verbose=verbose)
    if asset.empty:
        return asset
    
    if subregion:
        ref_path = os.path.join(ref_dir, subregion + ".geoparquet")
        ref = gpd.read_parquet(ref_path)
    else:
        ref_files = glob(os.path.join(ref_dir, "*.parquet"))
        ref_dfs = [pd.read_parquet(f).reset_index() for f in ref_files]
        ref = pd.concat(ref_dfs, axis=0, ignore_index=True)
        ref = ref.copy() # de-fragment
    
    ref["asset_type"] = ref["asset_type"].str.lower()
    asset = assign_road_class(asset, ref, how='left')
    asset["asset_type"] = asset["road_class"].copy()
    asset["asset_type"] = asset["asset_type"].apply(format_asset)
    asset = asset.drop(columns=["road_class"])
    return asset.reset_index()


def prepare_roads_bridges_and_culverts_data(
        asset_dir, cfgdir, subregion=None, verbose=False
    ):
    
    def format_asset(x:str) -> str:
        x = x.split(" ")[-1]
        return x.title()

    asset = ttra.load_risk_expected(asset_dir, subregion=subregion, verbose=verbose)
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
    # set up all the masks
    disused = asset["asset_type"].str.contains("disused", case=False, na=False)
    proposed = asset["asset_type"].str.contains("proposed", case=False)
    planned = asset["asset_type"].str.contains("planned", case=False)
    construction = asset["asset_type"].str.contains("construction", case=False)
    epoch_base = asset["epoch"].apply(lambda x: x in ["2010", "2015", "2020"])
    epoch_2030 = asset["epoch"] == "2030"
    epoch_2050 = asset["epoch"] == "2050"

    # Table 4-2 in report
    remove_construction = construction & epoch_base
    remove_proposed = proposed & (epoch_base | epoch_2030)
    remove_planned = planned & (epoch_base | epoch_2030 | epoch_2050)
    remove = disused | remove_construction | remove_proposed | remove_planned
    asset = asset[~remove].copy()
    return asset


def prepare_railway_data(asset_dir, subregion=None, verbose=False):
    def format_asset(x:str) -> str:
        gauge, structure, status = x.split("_")
        gauge = gauge.upper()
        return f"{gauge} {structure}\n({status})"

    asset = ttra.load_risk_expected(asset_dir, subregion=subregion, verbose=verbose)
    if asset.empty:
        return asset

    asset = handle_railway_planning(asset)
    asset["asset_type"] = asset["asset_type"].apply(format_asset)
    return asset


def prepare_asset(
        asset_geom, asset_dir, subregion=None,
        cfgdir=None, refdir=None, verbose=False
    ):
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
        airports = ttra.load_risk_expected(
            str(asset_dir).replace("hubs", "airports"),
            subregion=subregion,
            verbose=verbose
        )
        airports["asset_type"] = "Airport"

        maritime_ports = ttra.load_risk_expected(
            str(asset_dir).replace("hubs", "maritime_ports"),
            subregion=subregion,
            verbose=verbose
        )
        maritime_ports["asset_type"] = "Maritime port"
        iww_ports = ttra.load_risk_expected(
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
        asset = asset.drop(columns="geometry")
        asset = verify_ranges(asset)

    return asset


if __name__ == "__main__":
    print("Beginning to process expectation files...")
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
    for asset_geom in (pbar := tqdm(ASSETS)):
        for hazard in HAZARDS:
            for subregion in subregions:

                outpath = outdir / asset_geom / hazard / subregion / "expected.parquet"

                if os.path.exists(outpath) and not REDO:
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
                        verbose=True
                    )
                    if asset.empty:
                        missing.append([asset_geom, hazard, subregion])
                        continue

                    asset = verify_ranges(asset)
                    if hazard == "landslide":
                        asset = scale_landslide_risk(asset)
                    
                    asset.to_parquet(outpath)
                    print(f"Saved cleaned data to {outpath}")
                except FileNotFoundError as e:
                    missing.append([asset_geom, hazard, subregion])
                    continue


    missing_df = pd.DataFrame(missing, columns=["asset_geom", "hazard", "subregion"])
    missing_df = missing_df.groupby(["asset_geom", "hazard"]).agg(
        count=("subregion", "count"),
        subregions=("subregion", list)
        )
    missing_df["subregions"] = missing_df["subregions"].str.join(";")
    missing_df.to_csv(outdir / "missing_expected.csv")

    print("Finished!")
# %%
