# %% 
"""Process input rehab costs to a single row per asset_type for every hazard type."""
import os
import pandas as pd
from glob import glob
import yaml


hazard_cost_dict = {
    "fluvial": "flood_storm_landslide",
    "pluvial": "flood_storm_landslide",
    "coastal": "flood_storm_landslide",
    # "cyclone": "flood_storm_landslide",
    # "landslide": "flood_storm_landslide",
    # "heat": "heat",
}

def standardise_cost_columns(df, currency="usd"):
    units_list = []
    for prefix in ["min", "mean", "max"]:
        cost_prefix = f"{prefix}_cost_{currency}"
        cost_cols = [col for col in df.columns if col.startswith(cost_prefix)]
        assert len(cost_cols) == 1, f"Expected one column for {cost_prefix}, found {cost_cols}"
        cost_col = cost_cols[0]
        if cost_col == cost_prefix:
            units_list.append("unit")
            continue
        cost_standardised, units = cost_col.split("_per_")
        df = df.rename(columns={cost_col: cost_standardised})
        units_list.append(units)
    assert all(u == units_list[0] for u in units_list), f"Different units found: {units_list}"
    df["unit_type"] = units_list[0]
    return df


if __name__ == "__main__":

    cfg_path = os.path.join("..", "..", "workflow", "config.yaml")
    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)

    indir = cfg["inputs"]
    indir = os.path.join(indir, "input", "costs")

    for hazard, hazdir in hazard_cost_dict.items():
        cost_files = glob(os.path.join(indir, hazdir, "*.csv"))                
        cost_dfs = []
        for file in cost_files:

            df = pd.read_csv(file)

            df = df.set_index("asset_type")
            df = standardise_cost_columns(df)
            cost_dfs.append(df)


        cost_df = pd.concat(cost_dfs)
        cost_df = cost_df[~cost_df.index.duplicated(keep="first")]
        outpath = os.path.join("..", "..", "config", "rehab_costs", f"{hazard}.csv")
        cost_df.to_csv(outpath)
        print(f"Wrote {outpath} with {len(cost_df)} rows.")
    # %%