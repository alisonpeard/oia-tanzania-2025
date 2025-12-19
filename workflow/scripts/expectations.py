"""Use trapezoidal integration to avoid overfitting and negative EAD values."""
import geopandas as gpd
import pandas as pd
import numpy as np
from tqdm import tqdm
from scipy import integrate
import logging

from utils import naming


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


def check_for_negatives(df:pd.DataFrame):
     if (df["expected"] < 0).any():
        negative_rows = df[df["expected"] < 0].copy()
        logging.warning(f"\nNegative expected risk values found:{len(negative_rows)}\n")
        # print debugging information
        for idx, row in negative_rows.head(5).iterrows():
            logging.debug(f"Row {idx} details:\n{row}")


def main(input, output, params=None):
    gdf = gpd.read_parquet(input.vector)

    if gdf.empty:
        gdf.to_parquet(output.parquet, index=True)
        logging.info("Input asset file is empty, saved empty output.")
        return

    hazard_cols = [col for col in gdf.columns if col.startswith("hazard-")]
    defended_cols = [col for col in gdf.columns if col.startswith("defended-")]
    damage_cols = [col for col in gdf.columns if col.startswith("damage-")]
    cost_cols = [col for col in gdf.columns if col.startswith("cost-")]
    risk_cols = hazard_cols + defended_cols + damage_cols + cost_cols
    base_cols = [col for col in gdf.columns if col not in risk_cols]

    risk_gdf = gdf[risk_cols].copy().T
    risk_tuples = risk_gdf.reset_index()["index"].apply(naming.extract_hazard_info)
    risk_info = pd.DataFrame(
        risk_tuples.tolist(),
        columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
    )
    risk_gdf = risk_gdf.reset_index(drop=True).join(risk_info)
    risk_gdf = risk_gdf.melt(
        id_vars=["metric", "hazard", "epoch", "scenario", "rp", "range"],
        var_name="id"
        )

    # risk_gdf["value"] = risk_gdf["value"].fillna(0.0)

    risk_grouped = risk_gdf.groupby(
        ["id", "metric", "hazard", "epoch", "scenario", "range"],
        dropna=False
    )[["rp", "value"]]

    tqdm.pandas(desc="Calculating EAD")

    ead_results = risk_grouped.progress_apply(ead)
    ead_results = ead_results.reset_index()
    ead_results = ead_results.rename(columns={0: "expected"})

    final_gdf = gdf[base_cols].reset_index().merge(
        ead_results,
        on="id",
        how="outer"
    ).set_index("id")

    final_df = final_gdf.drop(columns="geometry")
    final_df.to_parquet(output.parquet, index=True)

    columns = ["asset_type", "unit", "unit_type", "metric", "hazard", "epoch", "scenario", "expected", "range"]
    final_df = final_df[columns].sort_values(by=columns)

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

    result = main(input, output, params)