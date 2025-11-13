"""
NOTE: refactor this so not repeatedly doing IO with the same csvs.
"""
import os
import pandas as pd
import geopandas as gpd
import logging


def get_hazard_from_colname(hazcol):
    return hazcol.split("_")[0].split("-")[1]


def main(input, output, params):
    exposure = gpd.read_parquet(input.vector)

    asset_types = list(exposure["asset_type"].unique())
    hazard_cols = [col for col in exposure.columns if col.startswith("hazard-")]

    asset_exposures = []
    for asset_type in asset_types:
        asset_exposure = exposure[exposure["asset_type"] == asset_type].copy()
        
        for hazard_col in hazard_cols:
            hazard = get_hazard_from_colname(hazard_col)

            design_standard_file = os.path.join(params.protection_dir, f"{hazard}.csv")
            design_standard_df = pd.read_csv(design_standard_file, comment='#')
            design_standard_df = design_standard_df.set_index("asset_type", drop=True)

            if asset_type in design_standard_df.index:
                design_standard_hazard: str = design_standard_df.loc[asset_type, "design_standard_hazard"]
                if design_standard_hazard is None or pd.isna(design_standard_hazard):
                    logging.info(f"No design standard provided for asset type '{asset_type}' from hazard '{hazard}'. Skipping subtraction.")
                    continue

                design_standard_col = "hazard-" + design_standard_hazard
                if design_standard_col not in asset_exposure.columns:
                    raise ValueError(
                        f"Design standard hazard column '{design_standard_col}' not found in asset exposure data for asset type '{asset_type}'."
                    )
                thresholds = asset_exposure[design_standard_col]
                asset_exposure[hazard_col] = asset_exposure[hazard_col] - thresholds
                asset_exposure[hazard_col] = asset_exposure[hazard_col].clip(lower=0.0)
                logging.info(f"Design standards: subtracted '{design_standard_col}' from '{hazard_col}' for asset type '{asset_type}'.")
            else:
                logging.warning(
                    f"No design standard found for asset type '{asset_type}' in hazard '{hazard}' design standard file '{design_standard_file}'."
                )
        asset_exposures.append(asset_exposure)
    
    residual_exposure = pd.concat(asset_exposures)
    assert len(residual_exposure) == len(exposure), \
        "Length of residual exposure does not match original exposure."

    residual_exposure.to_parquet(output.vector)
    logging.info(f"Wrote residual exposure to {output.vector}")


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(process)d %(filename)s %(message)s", level=logging.INFO
    )
    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)