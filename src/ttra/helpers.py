import os
from glob import glob
import pandas as pd
import geopandas as gpd


__all__ = ["load_risk_profile", "load_risk_expected"]


def handle_duplicates_profiles(asset:pd.DataFrame) -> pd.DataFrame:
    """This is to handle double-counting in older results dataframes.
    Won't be needed for new analysis. Just don't want to make others
    re-run their results.
    """
    if asset[["id", "geometry"]].duplicated().any():
        print(f"dropping duplicates... ({len(asset)} -> ", end="")
        asset = asset.groupby(["id", "geometry"]).max().reset_index()
        print(f"{len(asset)}) rows")
        return asset.copy()
    else:
        print("passed duplicates check.")
        return asset.copy()
    

def load_risk_profile(asset_dir, subregion=None, verbose=False):
    """Helper function to load the asset risk profile data.
    
    Args:
        asset_dir (str): Path to the asset directory containing subregion folders.
        subregion (str, optional): Specific subregion to load. If None, loads all subregions.
        verbose (bool, optional): If True, prints loading information.
    """
    if subregion:
        asset_path = os.path.join(asset_dir, subregion, "profile.geoparquet")
        asset = gpd.read_parquet(asset_path).reset_index()
    else:
        if verbose:
            print(f"Loading all subregions from {asset_dir}")
        asset_files = glob(os.path.join(asset_dir, "*", "profile.geoparquet"))
        asset_dfs = []
        for f in asset_files:
            asset_subregion = gpd.read_parquet(f).reset_index()
            subregion_name = os.path.basename(os.path.dirname(f))
            asset_subregion["subregion"] = subregion_name
            asset_dfs.append(asset_subregion)
        asset = pd.concat(asset_dfs, axis=0, ignore_index=True)

        # NOTE: this is a patch for earlier double counting. Won't be needed
        # for new intersections data.
        asset = handle_duplicates_profiles(asset)

    if verbose:
        print(f"Loaded {len(asset)} assets from {asset_dir}")
    return asset.copy()


def duplicates_expected(asset:pd.DataFrame, columns:list) -> bool:
    asset = asset.groupby(columns)["expected"].count()
    duplicated = asset[asset > 1].copy()
    if duplicated.max() > 1:
        print(f"{len(duplicated)} duplicates found.")
        return True
    else:
        return False


def handle_duplicates_expected(asset:pd.DataFrame) -> pd.DataFrame:
    """This is to handle double-counting in older results dataframes.
    Won't be needed for new analysis. Just don't want to make others
    re-run their results.
    """
    metacols = ["id", "unit"] # NOTE: "subregion" NOT included
    scencols = ["hazard", "epoch", "scenario", "range", "metric", "expected"]
    
    if duplicates_expected(asset, metacols + scencols):
        print(f"dropping duplicates... ({len(asset)} -> ", end="")
        asset1 = asset.drop_duplicates(subset=metacols + scencols)
        assert not duplicates_expected(asset1, metacols + scencols), \
            "duplicates still found after dropping duplicates."
        print(f"{len(asset1)}) rows")
        return asset1
    else:
        print("passed duplicates check.")
        return asset.copy()


def load_risk_expected(asset_dir, subregion=None, verbose=False, nonzero=True):
    """Helper function to load the asset risk profile data.
    
    Args:
        asset_dir (str): Path to the asset directory containing subregion folders.
        subregion (str, optional): Specific subregion to load. If None, loads all subregions.
        verbose (bool, optional): Whether to print loading information.
        nonzero (bool, optional): Whether to filter out zero expected values.
    """
    if subregion:
        asset_path = os.path.join(asset_dir, subregion, "expected.parquet")
        asset = pd.read_parquet(asset_path).reset_index()
    else:
        if verbose:
            print(f"loading all subregions from {asset_dir}")
        
        asset_files = glob(os.path.join(asset_dir, "*", "expected.parquet"))
        asset_dfs = []
        for f in asset_files:
            if verbose: print(f"Loading {f}...")

            asset_sub = pd.read_parquet(f).reset_index()
            if asset_sub.empty:
                continue
            
            asset_sub["subregion"] = os.path.basename(os.path.dirname(f))
            asset_dfs.append(asset_sub)
        
        if len(asset_dfs) == 0:
            return None
        
        asset = pd.concat(asset_dfs, axis=0, ignore_index=True)
        asset = handle_duplicates_expected(asset)

        try:
            asset = asset[asset["expected"] > 0].copy() if nonzero else asset
        except Exception as e:
            print(e)
            print(asset.head())
            raise(e)
    
    if verbose:
        print(f"loaded {len(asset)} assets from {asset_dir}")

    return asset.copy()