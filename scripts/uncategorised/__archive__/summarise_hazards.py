# %%
import os
import ast
from glob import glob
import pandas as pd
from pathlib import Path

from osgeo import gdal

import utils.data as du

pd.set_option('display.max_rows', None)

rerun = False
hazdir = "/Users/alison/Local/github/oia-tanzania-2025/results/hazards/aligned"
outpath = "/Users/alison/Local/github/oia-tanzania-2025/analysis/tables/input-hazard-summary.xlsx"
hazfiles = glob(os.path.join(hazdir, "*.tif"))

if rerun:
    hazards = []
    for hazfile in hazfiles:
        hazstem = Path(hazfile).stem
        print(f"Processing {hazstem}")
        info:tuple = du.extract_hazard_info(hazstem)
        hazard = info[1]
        epoch = int(info[2])
        scenario = info[3]
        returnperiods = int(info[4])

        with gdal.Open(hazfile) as src:
            band = src.GetRasterBand(1)
            stats = band.ComputeStatistics(False)  # (min, max, mean, std)
            mean = stats[2]
        hazards.append((hazard, epoch, scenario, returnperiods, mean))

    hazdf = pd.DataFrame(hazards, columns=["hazard", "epoch", "scenario", "return_period", "mean_hazard"])
    hazdf = hazdf.sort_values(by=["hazard", "epoch", "scenario", "return_period"])
    hazdf = hazdf.groupby(["hazard", "epoch", "scenario"]).agg({"return_period": list, "mean_hazard": list})
    hazdf.to_excel(outpath, index=True)
    print(f"Number of hazards: {len(hazfiles)}")
else:
    hazdf = pd.read_excel(outpath, index_col=[0,1,2])

    idx = pd.IndexSlice
    missing = ("pluvial", [2080], "ssp245")
    missing = ("coastal", [2050], "ssp585")
    missing_subset = hazdf.loc[idx[missing]].copy()
    missing_subset["return_period"] = missing_subset["return_period"].apply(ast.literal_eval)
    missing_subset["mean_hazard"] = missing_subset["mean_hazard"].apply(ast.literal_eval)
    return_periods = missing_subset["return_period"].values.tolist()
    values = missing_subset["mean_hazard"].values.tolist()
    missing_values = pd.DataFrame(values, columns=return_periods[0])
    missing_values
# %%
