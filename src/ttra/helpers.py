import os
from glob import glob
import pandas as pd
import geopandas as gpd


__all__ = ["load_risk_profile", "load_risk_expected"]


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
    if verbose:
        print(f"Loaded {len(asset)} assets from {asset_dir}")
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
            print(f"Loading all subregions from {asset_dir}")
        
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

        try:
            asset = asset[asset["expected"] > 0].copy() if nonzero else asset
        except Exception as e:
            print(e)
            print(asset.head())
            raise(e)
    
    if verbose:
        print(f"Loaded {len(asset)} assets from {asset_dir}")

    return asset.copy()