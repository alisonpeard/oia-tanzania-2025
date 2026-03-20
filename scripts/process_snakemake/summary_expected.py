"""Make national summary tables"""
# %%
import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

from oi_risk import config as cfg
from ttra import load_risk_expected
from ttra.plot import labels, palette

sys.path.append("..") 

assets = [
    "tza_roads_edges",
    "tza_roads_bridges_and_culverts_nodes",
    "tza_railway_edges",
    "tza_hubs_polygons"
]
hazards = [
    "fluvial",
    "pluvial",
    "coastal",
    "landslide",
    "cyclone",
    "extremeheat"
]

if __name__ == "__main__":
    config = cfg.load_config()
    indir = Path(config["paths"]["results"]) / "intersections"
    outdir = Path(config["paths"]["results"]) / "summary_tables"
    outdir.mkdir(exist_ok=True, parents=True)

    reslist = []
    missing = []
    for asset_geom in assets:
        for hazard in hazards:
            inpath = indir / asset_geom / hazard

            if not os.path.exists(inpath):
                print(f"No data for: ({asset_geom}, {hazard}) - skipping")
                continue

            asset = load_risk_expected(inpath, verbose=False)

            if asset is None:
                print(f"No expected.parquet files found for ({asset_geom}, {hazard})")
                missing.append((asset_geom, hazard))
                continue

            res = asset.copy()
            res["epoch"] = res["epoch"].replace({labels.baselines[hazard]: "baseline"})
            res["scenario"] = res["scenario"].map(labels.scenarios)

            if hazard in ["hd35", "tasmax"]:
                res["hazard"] = "heat"

            res["hazard"] = hazard
            res["asset_geom"] = asset_geom
            res = res.groupby([
                "hazard", "asset_geom", "epoch",
                "scenario", "metric", "range"
            ])["expected"].sum().reset_index()

            reslist.append(res)

    results = pd.concat(reslist, axis=0, ignore_index=True)
    groupby = [col for col in results.columns if col != "expected"]
    unstacked = results.groupby(groupby)["expected"].agg("sum").unstack("range").reset_index()
    groupby = [col for col in groupby if col != "range"]
    unstacked.columns = groupby + ["max", "mean", "min"] # alphabetical
    out = unstacked[groupby + ["min", "mean", "max"]]
    out.to_csv(outdir / "expected.csv")

    print("finished.")

# %%
