"""
Prepare all the direct damage results for plotting.

This script includes hard-coded patches for missing hazard data.
"""
import os
import pandas as pd
import geopandas as gpd
from glob import glob

from . import paths


def extract_hazard_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract hazard, epoch, scenario, and return period from hazard column name."""
    if "-" in hazcol:
        prefix, parts = hazcol.split("-")
    else:
        prefix = ""
        parts = hazcol
    parts = parts.split("_")
    hazard = parts[0]
    epoch = parts[1]
    scenario = parts[2]
    rp = str(int(parts[3].replace("rp", "")))
    if len(parts) > 4:
        stat = "_".join(parts[4:])
    else:
        stat = pd.NA
    return prefix, hazard, epoch, scenario, rp, stat


def prepare_hazard_coastal(df) -> pd.DataFrame:
    # interpolate missing 50-year coastal hazard based on 10- and 100-year
    missing_stem = "-coastal_2050_ssp585_rp00050"
    lower_stem = "-coastal_2050_ssp585_rp00010"
    upper_stem = "-coastal_2050_ssp585_rp00100"

    def interp(xmin, ymin, xmax, ymax):
        """Linear interpolation"""
        return lambda x: ymin + (ymax - ymin) * (x - xmin) / (xmax - xmin)
    
    xmin, xmax = 10, 100
    for metric in ["damage", "cost"]: #TODO: check if hazard and defended
        stats = ["min", "mean", "max"]
        for stat in stats:
            lower_col = metric + lower_stem + "_" + stat
            upper_col = metric + upper_stem + "_" + stat
            missing_col = metric + missing_stem + "_" + stat
            df[missing_col] = df.apply(
                lambda row: interp(
                    xmin, row[lower_col],
                    xmax, row[upper_col]
                )(50),
                axis=1
            )
            print(f"WARNING: Replaced {missing_col} with interpolated values from {lower_col} and {upper_col}")
    return df.copy() # de-fragment

    
def prepare_hazard_pluvial(df) -> pd.DataFrame:
    # interpolate missing 200-year pluvial hazard based on 100- and 500-year
    missing_stem = "-pluvial_2080_ssp245_rp00200"
    lower_stem = "-pluvial_2080_ssp245_rp00100"
    upper_stem = "-pluvial_2080_ssp245_rp00500"

    def interp(xmin, ymin, xmax, ymax):
        """Linear interpolation"""
        return lambda x: ymin + (ymax - ymin) * (x - xmin) / (xmax - xmin)
    
    xmin, xmax = 100, 500
    for metric in ["damage", "cost"]: #TODO: check if hazard and defended
        stats = ["min", "mean", "max"]
        for stat in stats:
            lower_col = metric + lower_stem + "_" + stat
            upper_col = metric + upper_stem + "_" + stat
            missing_col = metric + missing_stem + "_" + stat
            df[missing_col] = df.apply(
                lambda row: interp(
                    xmin, row[lower_col],
                    xmax, row[upper_col]
                )(200),
                axis=1
            )
            print(f"WARNING: Replaced {missing_col} with interpolated values from {lower_col} and {upper_col}")
    return df.copy() # de-fragment


def prepare_hazard_cyclone(df) -> pd.DataFrame:
    """Let SSP126 be based on historical baseline for cyclone hazard"""
    i = 0
    # represent ssp126 using historical baseline
    newkeys = []
    newvals = []
    for metric in ["hazard", "defended"]:
        for rp in ['10', '25', '50', '250', '1000']:
            ref = metric + '-cyclone_2010_historical_rp' + rp.zfill(5)
            ssp126_2010 = metric + '-cyclone_2010_ssp126_rp' + rp.zfill(5)
            ssp126_2050 = metric + '-cyclone_2050_ssp126_rp' + rp.zfill(5)
            ssp126_2090 = metric + '-cyclone_2090_ssp126_rp' + rp.zfill(5)
            newkeys.append(ssp126_2010)
            newvals.append(df[ref].copy())
            newkeys.append(ssp126_2050)
            newvals.append(df[ref].copy())
            newkeys.append(ssp126_2090)
            newvals.append(df[ref].copy())
            i += 3
    
    for metric in ["damage", "cost"]:
        stats = ["min", "mean", "max"]
        for rp in ['10', '25', '50', '250', '1000']:
            for stat in stats:
                ref = metric + '-cyclone_2010_historical_rp' + rp.zfill(5) + "_" + stat
                ssp126_2010 = metric + '-cyclone_2010_ssp126_rp' + rp.zfill(5) + "_" + stat
                ssp126_2050 = metric + '-cyclone_2050_ssp126_rp' + rp.zfill(5) + "_" + stat
                ssp126_2090 = metric + '-cyclone_2090_ssp126_rp' + rp.zfill(5) + "_" + stat
                newkeys.append(ssp126_2010)
                newvals.append(df[ref].copy())
                newkeys.append(ssp126_2050)
                newvals.append(df[ref].copy())
                newkeys.append(ssp126_2090)
                newvals.append(df[ref].copy())
                i += 3
    
    newcols = pd.DataFrame(dict(zip(newkeys, newvals)))
    df = pd.concat([df, newcols], axis=1)
    print(f"WARNING: Prepared cyclone data using baseline with {i} new columns for 2050 and 2080 SSP1-2.6")
    return df


def prepare_hazard_data(df, hazard) -> pd.DataFrame:
    """Prepare direct damage results for a given hazard"""
    df = df.copy()
    costcols = [col for col in df.columns if col.startswith("cost")]
    costcols_clean = ["_".join(col.split("_")[:-1]) for col in costcols]

    renamed_costs = df[costcols].copy()
    renamed_costs.columns = costcols_clean
    df = pd.concat([df.drop(columns=costcols), renamed_costs], axis=1)

    df = df.copy()
    if hazard == "cyclone":
        df = prepare_hazard_cyclone(df)
    if hazard == "pluvial":
        df = prepare_hazard_pluvial(df)
    if hazard == "coastal":
        df = prepare_hazard_coastal(df)
    return df


def load_asset_data(asset_dir, subregion=None, verbose=False, metric_type="profile.geoparquet"):
    filetype = metric_type.split(".")[-1]
    load = gpd.read_parquet if filetype == "geoparquet" else pd.read_parquet
    if subregion:
        asset_path = os.path.join(asset_dir, subregion, metric_type)
        asset = load(asset_path).reset_index()
    else:
        if verbose:
            print(f"Loading all subregions from {asset_dir}")
        asset_files = glob(os.path.join(asset_dir, "*", metric_type))
        asset_dfs = []
        for f in asset_files:
            asset_subregion = load(f).reset_index()
            subregion_name = os.path.basename(os.path.dirname(f))
            asset_subregion["subregion"] = subregion_name
            asset_dfs.append(asset_subregion)
        asset = pd.concat(asset_dfs, axis=0, ignore_index=True)
    if verbose:
        print(f"Loaded {len(asset)} assets from {asset_dir}")
    return asset.copy()


def prepare_roads_data(asset_dir, ref_dir, subregion=None, verbose=False, metric_type="profile.geoparquet"):
    def format_asset(x:str) -> str:
        return x.title()
    asset = load_asset_data(asset_dir, subregion=subregion, verbose=verbose, metric_type=metric_type)
    if asset.empty:
        return asset
    # ref = load_asset_data(ref_dir, subregion=subregion, verbose=verbose)
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


def prepare_roads_bridges_and_culverts_data(asset_dir, ref_csv, subregion=None, verbose=False, metric_type="profile.geoparquet"):
    def format_asset(x:str) -> str:
        x = x.split(" ")[-1]
        return x.title()
    asset = load_asset_data(asset_dir, subregion=subregion, verbose=verbose, metric_type=metric_type)
    if asset.empty:
        return asset
    ref = pd.read_csv(ref_csv)
    ref["asset_class"] = ref["asset_class"].str.lower()
    class_dict = ref.set_index("asset_type")["asset_class"].to_dict()
    asset["asset_type"] = asset["asset_type"].map(class_dict)
    asset["asset_type"] = asset["asset_type"].apply(format_asset)
    return asset


def prepare_railway_data(asset_dir, subregion=None, verbose=False, metric_type="profile.geoparquet"):
    def format_asset(x:str) -> str:
        gauge, structure, status = x.split("_")
        gauge = gauge.upper()
        return f"{gauge} {structure}\n({status})"
    asset = load_asset_data(asset_dir, subregion=subregion, verbose=verbose, metric_type=metric_type)
    if asset.empty:
        return asset
    disused = asset["asset_type"].str.contains("disused", case=False, na=False)
    asset = asset[~disused].copy()
    asset["asset_type"] = asset["asset_type"].apply(format_asset)
    return asset


def prepare_asset(asset_geom, asset_dir, subregion=None, verbose=False, metric_type="profile.geoparquet"):
    """Prepare asset data based on asset geometry type"""
    if asset_geom == "tza_roads_edges":
        asset = prepare_roads_data(
            asset_dir,
            ref_dir=os.path.join(paths.road_reference_dir),
            subregion=subregion,
            verbose=verbose,
            metric_type=metric_type
        )
    elif asset_geom == "tza_roads_bridges_and_culverts_nodes":
        asset = prepare_roads_bridges_and_culverts_data(
            asset_dir,
            ref_csv=os.path.join(paths.bridges_and_culverts_reference_csv),
            subregion=subregion,
            verbose=verbose,
            metric_type=metric_type
        )
    elif asset_geom == "tza_railway_edges":
        asset = prepare_railway_data(
            asset_dir,
            subregion=subregion,
            verbose=verbose,
            metric_type=metric_type
        )
    elif asset_geom == "tza_hubs_polygons":
        airports = load_asset_data(
            asset_dir.replace("hubs", "airports"),
            subregion=subregion,
            verbose=verbose,
            metric_type=metric_type
        )
        print("WARNING: Multiplying airport costs by 0.1 to account for overestimation")
        costcols = [col for col in airports.columns if col.startswith("cost")]
        airports[costcols] = airports[costcols] * 0.1
        airports["asset_type"] = "Airport"
        maritime_ports = load_asset_data(
            asset_dir.replace("hubs", "maritime_ports"),
            subregion=subregion,
            verbose=verbose,
            metric_type=metric_type
        )
        maritime_ports["asset_type"] = "Maritime port"
        iww_ports = load_asset_data(
            asset_dir.replace("hubs", "iww_ports"),
            subregion=subregion,
            verbose=verbose,
            metric_type=metric_type
        )
        iww_ports["asset_type"] = "IWW port"
        asset = pd.concat([airports, maritime_ports, iww_ports], ignore_index=True)
    else:
        raise ValueError(f"Unknown asset geometry type: {asset_geom}")
    
    return asset