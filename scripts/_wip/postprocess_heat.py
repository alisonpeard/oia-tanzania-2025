"""
move to postprocess_results/ when done.

NOTE: Two-scripts-in-one
Format Pamela's results to match cleaned risk profiles.

- Unsplit geometries back to original
- Restore dropped geometries (for calculating % affected later)
- (Roads only) Concatenate baseline and future results
- Re-categorise asset_types for presentation
- Remove "_min_mean" duplicate cost columns
- Relabel "_mean_mean" etc to single suffix "_mean"
"""
# %%
import os
import numpy as np
import pandas as pd
import geopandas as gpd
from glob import glob
from pathlib import Path
from tqdm import tqdm
from oi_risk import config


config = config.load_config()
inp_dir = config["paths"]["heat_results"]
ref_dir = os.path.join(config["paths"]["snakemake_data"], "assets")
out_dir = config["paths"]["heat_results"]
pd.options.display.max_columns = None


def format_ref_index(vector_ref):
    """NOTE: This is a patch to match with Pamela's older results.
    
    Won't be needed in future.
    """
    aggfunc =  dict(road_class='first', asset_type='first')
    def format_index(index):
        return '_'.join(index.split('_')[:-1])
    vector_ref['id'] = vector_ref['id'].apply(format_index)
    vector_ref = vector_ref.dissolve(by='id', aggfunc=aggfunc)
    return vector_ref.reset_index()


def prepare_roads_data(asset, ref):
    def format_road_class(x:str) -> str:
        return x.title()

    ref["asset_type"] = ref["asset_type"].str.lower()
    ref = ref.set_index("id")
    asset = asset.join(ref[["road_class"]], how="inner") # NOTE: patch: use how='left' later
    asset["asset_type"] = asset["road_class"].copy()
    asset["asset_type"] = asset["asset_type"].apply(format_road_class)
    asset = asset.drop(columns=["road_class"])
    return asset.reset_index()


def prepare_railway_data(asset, *args):
    def format_asset_type(x:str) -> str:
        gauge, structure, status = x.split("_")
        gauge = gauge.upper()
        return f"{gauge} {structure}\n({status})"

    disused = asset["asset_type"].str.contains("disused", case=False, na=False)
    asset = asset[~disused].copy()
    asset["asset_type"] = asset["asset_type"].apply(format_asset_type)
    return asset


def prepare_data(asset:gpd.GeoDataFrame, asset_str:str, *args) -> gpd.GeoDataFrame:
    if asset_str == "tza_railway_edges":
        return prepare_railway_data(asset, *args)
    elif asset_str == "tza_roads_edges":
        return prepare_roads_data(asset, *args)


def unsplit(vector, vector_ref, hazard_cols, damage_cols, cost_cols):
    """Dissolve split geometries back to original geometries.
    
    github.com/alisonpeard/oia-tanzania-2025/workflow/scripts/utils/linestrings.py
    """
    risk_cols = hazard_cols + damage_cols + cost_cols
    meta_cols = ["asset_type", "unit", "unit_type"]

    # make sure to propagate NaNs to unsplit df
    def sum_strict(x):
        return x.sum(min_count=1)
    
    def max_strict(x):
        return np.nan if x.isna().any() else x.max()
    
    agg_func = {col: max_strict for col in hazard_cols} | \
                {col: sum_strict for col in damage_cols} | \
                {col: sum_strict for col in cost_cols}
    meta_agg = {"unit": "sum", 'unit_type': "first", "asset_type": "first"}
    agg_func.update(meta_agg)

    vector = vector[["id"] + meta_cols + risk_cols].copy()
    vector_grouped = vector.groupby("id").agg(agg_func).sort_index()

    vector_ref = vector_ref.set_index("id").sort_index()

    assert vector_ref.index.is_unique
    if not vector_grouped.index.equals(vector_ref.index):
        print("Indexes do not match!")
        # print the differences
        lost_ids = vector_ref.index.difference(vector_grouped.index)
        new_ids = vector_grouped.index.difference(vector_ref.index)
        print("In ref but not in grouped:", len(lost_ids))
        print("In grouped but not in ref:", len(new_ids))

    vector_grouped = vector_grouped.join(vector_ref[["geometry"]], how="left")
    vector_grouped = gpd.GeoDataFrame(
        vector_grouped, geometry="geometry", crs="EPSG:4326"
    )
    return vector_grouped


def clean_duplicate_columns(df, cost_cols):
    suffixes = ['max', 'mean', 'min']
    
    cost_cols_to_drop = []
    for col in cost_cols:
        s0, s1 = col.split("_")[-2:]

        if "None" in [s0, s1]:
            # drop any columns with 'None' in them
            cost_cols_to_drop.append(col)
            continue

        if s0 == s1:
            # if single and repeared suffix exist, drop the double suffix column
            # I looked at this earlier and the single-suffix ones had more
            # complete data...
            single_suffix_col = col.replace(f"_{s0}_{s1}", f"_{s0}")
            if single_suffix_col in df.columns and col in df.columns:
                cost_cols_to_drop.append(col)
                continue
        if s0 != s1:
            if (s0 in suffixes) and (s1 in suffixes):
                # it's a _min_mean etc - drop
                cost_cols_to_drop.append(col)
                continue
            else:
                # it's already a single-suffix column - ignore
                continue

    cost_cols_cleaned= list(set(cost_cols) - set(cost_cols_to_drop))

    # Drop the duplicate columns
    df_cleaned = df.drop(columns=cost_cols_to_drop)
    
    print(f"\nDropped {len(cost_cols_to_drop)} duplicate cost columns")
    print(f"Original columns: {len(df.columns)}, Cleaned columns: {len(df_cleaned.columns)}")

    # now rename all double-suffixes to single-suffixes
    rename_dict = {}
    for col in cost_cols_cleaned:
        for suffix in suffixes:
            double_suffix = f"_{suffix}_{suffix}"
            if double_suffix in col:
                new_col = col.replace(double_suffix, f"_{suffix}")
                rename_dict[col] = new_col
    
    df_cleaned = df_cleaned.rename(columns=rename_dict)
    cost_cols_cleaned = [rename_dict.get(col, col) for col in cost_cols_cleaned]
    
    return df_cleaned, cost_cols_cleaned


if __name__ == "__main__":

    asset = ["tza_roads_edges", "tza_railway_edges"][0]
    
    paths = glob(f"{inp_dir}/{asset}/*/splits.geoparquet")

    for splits_path in tqdm(paths):

        # process baseline along with the future results
        base_path = splits_path.replace(asset, f"{asset}_base")

        subregion = Path(splits_path).parent.name
        os.makedirs(os.path.join(out_dir, asset, subregion), exist_ok=True)

        print(f"Processing {asset} - {subregion}...")
        
        out_path = splits_path.replace(inp_dir, out_dir).replace("splits", "profile")
        
        if os.path.exists(out_path):
            print(f"Already exists: {out_path}")
            continue
        
        ref_path = splits_path.replace(inp_dir, ref_dir).replace("/splits", "")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)

        vector_ref = gpd.read_parquet(ref_path)
        vector_ref = format_ref_index(vector_ref) # NOTE: patch won't need later

        sub_dfs = []
        for sub_path in [base_path, splits_path]:

            vector_splits = gpd.read_parquet(sub_path)

            # define the groups of risk columns to keep
            hazard_cols = [c for c in vector_splits.columns if c.startswith("hazard")]
            defended_cols = [c for c in vector_splits.columns if c.startswith("defended")]
            damage_cols = [c for c in vector_splits.columns if c.startswith("damage")]
            cost_cols = [c for c in vector_splits.columns if c.startswith("cost")]
            hazard_cols += defended_cols
            hazard_cols = list(set(hazard_cols))
            damage_cols = list(set(damage_cols))
            cost_cols = list(set(cost_cols))

            vector_splits, cost_cols = clean_duplicate_columns(
                vector_splits, cost_cols
            )
            vector_splits["unit_type"] = "m"

            vector = unsplit(
                vector_splits, vector_ref,
                hazard_cols, damage_cols, cost_cols
            )

            vector_clean = prepare_data(vector, asset, vector_ref)
            # ensure "id" is the index column
            if not vector_clean.index.name == "id":
                vector_clean = vector_clean.set_index("id")
            sub_dfs.append(vector_clean)

        vector_clean = pd.concat(sub_dfs, ignore_index=False)
        vector_clean.to_parquet(out_path)
        print(f"Saved to {out_path}")

vector_clean.describe()
# %%
