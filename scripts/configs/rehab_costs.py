"""
Process input rehab costs to a single row per asset_type for every hazard type.
"""
#%% 
import pandas as pd
from glob import glob
from pathlib import Path
from oi_risk import config


HAZARDS_CATEGORIES = {
    "fluvial": "floods_storms_landslides",
    "pluvial": "floods_storms_landslides",
    "coastal": "floods_storms_landslides",
    "cyclone": "floods_storms_landslides",
    "landslide": "floods_storms_landslides",
    "heat": "heat",
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
    config = config.load_config()
    indir = Path(config['paths']['processed_data']) / "costs"
    outdir = Path(config["paths"]["snakemake_data"]) / "config" / "rehab_costs"
    configdir = Path(config['paths']['snakemake_data']) / "config"
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"Processing rehab costs from {indir}")

    asset_types = pd.read_csv(configdir / "asset_types.csv")["asset_type"].tolist()

    for hazard, hazdir in HAZARDS_CATEGORIES.items():
        print(f"Processing hazard: {hazard}")
        print(f"  from directory: {hazdir}")
        
        cost_files = glob(str(indir / hazdir / "*.csv"))       

        cost_dfs = []
        for file in cost_files:
            df = pd.read_csv(file)
            df = df.set_index("asset_type")
            df = standardise_cost_columns(df)
            cost_dfs.append(df)

        cost_df = pd.concat(cost_dfs)
        cost_df = cost_df[~cost_df.index.duplicated(keep="first")]
        cost_df = cost_df.reindex(asset_types)
        cost_df.index.name = "asset_type"
        cost_df = cost_df.sort_index()

        if hazard == "heat":
            cost_df["min_cost_usd"] = float("nan")
            cost_df["max_cost_usd"] = float("nan")
            cost_df["mean_cost_usd"] = float("nan")
            for heat_hazard in ["hd35", "tasmax"]:
                outpath = outdir / f"{heat_hazard}.csv"
                cost_df.to_csv(outpath)
                print(f"Wrote {outpath} with {len(cost_df)} rows.")
            continue

        outpath = outdir / f"{hazard}.csv"
        cost_df.to_csv(outpath)
        print(f"Wrote {outpath} with {len(cost_df)} rows.")
    # %%