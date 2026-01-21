"""
Summarise all hazards into a table of mean hazard values.

Change REDO to True to re-generate the table from the hazard files.
"""
# %%
import os
import ast
import pandas as pd
from osgeo import gdal
from glob import glob
from pathlib import Path

from oi_risk import config
import ttra

pd.set_option('display.max_rows', None)


MAKE = False


if __name__ == '__main__':
    # configure paths
    config = config.load_config()
    hazdir = Path(config['paths']['snakemake_data']) / "hazards" / "raw"
    outpath = Path(config['paths']['results']) / "tables" / "input-hazard-summary.xlsx"
    outpath.parent.mkdir(parents=True, exist_ok=True)

    hazfiles = glob(os.path.join(hazdir, "*.tif"))
    hazfiles = [f for f in hazfiles if not Path(f).name.startswith("_")]
    if MAKE:
        hazards = []
        for hazfile in hazfiles:
            hazstem = Path(hazfile).stem
            print(f"Processing {hazstem}")
            info:tuple = ttra.hazards.extract_info(hazstem)
            hazard = info[1]
            epoch = int(info[2])
            scenario = info[3]
            returnperiods = int(info[4])

            with gdal.Open(hazfile) as src:
                ### get mean hazard over raster for reference
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
        hazdf = pd.read_excel(outpath, index_col=[0, 1, 2])
        hazdf.head()
# %%
