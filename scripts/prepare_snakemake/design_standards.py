"""
Format the protection standards for snakemake.
Only floods have standards, make dummy files for the rest (hardcoded).
"""
# %%
import pandas as pd
from functools import partial
from pathlib import Path
from oi_risk import config


BASE_EPOCH = 2020
BASE_SCEN = "historical"


def format_design_standard(rp, hazard, scenario, epoch):
    if rp == 0:
        return None
    return '_'.join([
        hazard,
        str(epoch),
        scenario,
        f"rp{str(rp).zfill(5)}"
    ])


if __name__ == "__main__":
    config = config.load_config()
    inpath = Path(config['paths']['processed_data']) / "protection_standards"/ "protection_standards_flooding.csv"
    outdir = Path(config["paths"]["snakemake"]) / "input" / "config" / "design_standards"
    outdir.mkdir(parents=True, exist_ok=True)

    standards_df = pd.read_csv(inpath)

    for hazard in ["fluvial", "pluvial", "coastal"]:
        df_hazard = standards_df.copy()
        outfile = outdir / f"{hazard}.csv"
        format_design_hazard = partial(
            format_design_standard,
            hazard=hazard, scenario=BASE_SCEN, epoch=BASE_EPOCH
        )
        df_hazard["design_hazard"] = df_hazard["design_return_period"].apply(format_design_hazard)
        df_hazard = df_hazard[["asset_type", "design_hazard"]].copy()
        df_hazard.to_csv(outfile, index=False)
        print(f"Wrote {outfile} with {len(df_hazard)} rows.")

    for hazard in ["landslide", "cyclone", "hd35", "tasmax"]:
        df_hazard = standards_df.copy()
        outfile = outdir / f"{hazard}.csv"
        df_hazard["design_hazard"] = float("nan")
        df_hazard = df_hazard[["asset_type", "design_hazard"]].copy()
        df_hazard.to_csv(outfile, index=False)
        print(f"Wrote {outfile} with {len(df_hazard)} rows.")


# %%
