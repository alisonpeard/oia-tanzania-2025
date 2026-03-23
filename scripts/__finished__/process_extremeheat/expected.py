"""Calculate EADs over all extreme heat results.

Same code as github.com/oi-analytics/direct-damages-workflow

Use trapezoidal integration to avoid overfitting and negative EAD values.
"""
# %%
import os
from glob import glob
import geopandas as gpd
import pandas as pd
import numpy as np
from tqdm import tqdm
from pathlib import Path
from scipy import integrate
import logging
import subprocess
from oi_risk import config


remake = True


def extract_hazard_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract hazard, epoch, scenario, and return period from hazard column name."""
    prefix, parts = hazcol.split("-")
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


def ead(df:pd.DataFrame, method="trapezoid") -> float:
        """Calculate expected annual damage from damage values and return periods."""
        if df.empty | (df["value"] == 0).all():
            return 0.0
        damages = df["value"].astype(float).values
        rps = df["rp"].astype(float).values
        probs = 1 / rps
        idx = np.argsort(probs)
        probs = np.insert(probs[idx], 0, 0.0)
        damages = np.insert(damages[idx], 0, 0.0)
        ead_value = getattr(integrate, method)(damages, x=probs)
        return ead_value


def vectorised_ead(risk_df, group_cols):
    """Compute EAD for all groups at once using pivot + vectorized trapezoid."""

    risk_df = risk_df.copy()
    risk_df["rp"] = risk_df["rp"].astype(float)
    
    # check RPs are consistent
    expected_rp_count = risk_df["rp"].nunique()
    rps_per_group = risk_df.groupby(group_cols + ["id"])["rp"].nunique()
    if not (rps_per_group == expected_rp_count).all():
        raise ValueError("Inconsistent RPs across groups")
    
    pivoted = risk_df.pivot_table(
        index=group_cols + ["id"],
        columns="rp",
        values="value",
        fill_value=0.0
    )
    
    # sort columns by descending RP (ascending probability)
    rps = np.array(sorted(pivoted.columns, reverse=True))
    pivoted = pivoted[rps]
    
    probs = 1.0 / rps
    probs = np.insert(probs, 0, 0.0)
    
    damages = pivoted.values
    damages = np.hstack([np.zeros((damages.shape[0], 1)), damages])
    
    # vectorized trapezoid
    # [y1 + y2] / 2 * (x2 - x1)
    dp = np.diff(probs)
    ead_values = np.sum((damages[:, :-1] + damages[:, 1:]) / 2 * dp, axis=1)
    
    result = pivoted.reset_index()
    result = result[group_cols + ["id"]].copy()
    result["expected"] = ead_values
    return result


def check_for_negatives(df:pd.DataFrame):
     if (df["expected"] < 0).any():
        negative_rows = df[df["expected"] < 0].copy()
        logging.warning(f"\nNegative expected risk values found:{len(negative_rows)}\n")
        # print debugging information
        for idx, row in negative_rows.head(5).iterrows():
            logging.debug(f"Row {idx} details:\n{row}")


def main(input, output, params=None):
    df = pd.read_parquet(input)

    if df.index.name != 'id':
        df = df.set_index('id')

    if df.empty:
        df.to_parquet(output, index=True)
        logging.info("Input asset file is empty, saved empty output.")
        return

    hazard_cols = [col for col in df.columns if col.startswith("hazard-")]
    defended_cols = [col for col in df.columns if col.startswith("defended-")]
    damage_cols = [col for col in df.columns if col.startswith("damage-")]
    cost_cols = [col for col in df.columns if col.startswith("cost-")]
    risk_cols = hazard_cols + defended_cols + damage_cols + cost_cols
    base_cols = [col for col in df.columns if col not in risk_cols]

    # tranpose and parse column names
    risk_df = df[risk_cols].copy().T.reset_index()
    risk_tuples = risk_df["index"].apply(extract_hazard_info)
    risk_info = pd.DataFrame(
        risk_tuples.tolist(),
        columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
    )
    risk_df = risk_df.drop(columns="index").join(risk_info)
    
    # melt to long format
    id_cols = ["metric", "hazard", "epoch", "scenario", "rp", "range"]
    risk_df = risk_df.melt(id_vars=id_cols, var_name="id", value_name="value")

    # to prevent accidentally dropping metrics (hazard) without ranges
    risk_df["range"] = risk_df["range"].fillna("mean")
    risk_df["value"] = risk_df["value"].fillna(0.0)

    # vectorised ead calculation
    group_cols = ["metric", "hazard", "epoch", "scenario", "range"]
    ead_results = vectorised_ead(risk_df, group_cols)

    final_df = df[base_cols].reset_index().merge(
        ead_results,
        on="id",
        how="outer"
    ).set_index("id")

    final_df.to_parquet(output, index=True)

    check_for_negatives(final_df)
    logging.info(f"Saved expected risk results to {output}")



if __name__ == "__main__":

    for asset in ["tza_railway_edges", "tza_roads_edges"]:

        cfg = config.load_config()
        wd = Path(cfg["paths"]["results"]) / "intersections" / asset / "extremeheat"

        pattern = os.path.join(wd, "*", "profile.geoparquet")

        inputs = glob(pattern)

        for input in tqdm(inputs):
            output = input.replace("profile.geoparquet", "expected.parquet")
            if os.path.exists(output) and not remake:
                print(f"Already exists: {output}")
                continue
            main(input, output)

subprocess.run(["say", "done"])
# %%
