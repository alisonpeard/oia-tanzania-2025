"""Use trapezoidal integration to avoid overfitting and negative EAD values."""
import geopandas as gpd
import pandas as pd
import numpy as np
import logging
from utils import naming


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


def check_for_negatives(df: pd.DataFrame):
    if (df["expected"] < 0).any():
        negative_rows = df[df["expected"] < 0].copy()
        logging.warning(f"\nNegative expected risk values found: {len(negative_rows)}\n")
        for idx, row in negative_rows.head(5).iterrows():
            logging.debug(f"Row {idx} details:\n{row}")


def main(input, output, params=None):
    df = pd.read_parquet(input.vector)
    if df.index.name != 'id':
        df = df.set_index('id')
    
    if df.empty:
        df.to_parquet(output.parquet, index=True)
        logging.info("Input asset file is empty, saved empty output.")
        return
    
    isolated_cols = [col for col in df.columns if col.startswith("isolated-")]
    detoured_cols = [col for col in df.columns if col.startswith("detoured-")]
    wdetoured_cols = [col for col in df.columns if col.startswith("wdetoured-")]
    risk_cols = isolated_cols + detoured_cols + wdetoured_cols
    base_cols = [col for col in df.columns if col not in risk_cols]
    
    # Transpose and parse column names
    risk_df = df[risk_cols].copy().T.reset_index()
    risk_tuples = risk_df["index"].apply(naming.extract_hazard_info)
    risk_info = pd.DataFrame(
        risk_tuples.tolist(),
        columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
    )
    risk_df = risk_df.drop(columns="index").join(risk_info)
    
    # Melt to long format
    id_cols = ["metric", "hazard", "epoch", "scenario", "rp", "range"]
    risk_df = risk_df.melt(id_vars=id_cols, var_name="id", value_name="value")
    risk_df["value"] = risk_df["value"].fillna(0.0)
    
    # vectorised EAD calculation
    group_cols = ["metric", "hazard", "epoch", "scenario", "range"]
    ead_results = vectorised_ead(risk_df, group_cols)
    
    # Merge back with base columns
    final_df = df[base_cols].reset_index().merge(
        ead_results,
        on="id",
        how="outer"
    ).set_index("id")
    
    final_df.to_parquet(output.parquet, index=True)
    check_for_negatives(final_df)
    logging.info(f"Saved expected risk results to {output.parquet}")


if __name__ == "__main__":
    logging.basicConfig(
        filename=snakemake.log.file,
        format="%(asctime)s %(process)d %(filename)s %(message)s",
        level=logging.INFO
    )
    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)