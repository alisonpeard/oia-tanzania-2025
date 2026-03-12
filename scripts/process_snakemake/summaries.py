"""Make national summary tables"""
# %%
import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

from oi_risk import config
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
    # "hd35",
    # "tasmax"
]


config = config.load_config()
indir = Path(config["paths"]["results"]) / "intersections"
outdir = Path(config["paths"]["results"]) / "summaries"
outdir.mkdir(exist_ok=True, parents=True)

# %%
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
            print(f"No expected found for ({asset_geom}, {hazard})")
            missing.append((asset_geom, hazard))
            continue

        res = asset.copy()
        res["epoch"] = res["epoch"].replace({labels.baselines[hazard]: "baseline"})
        res["scenario"] = res["scenario"].map(labels.scenarios)

        if hazard in ["hd35", "tasmax"]:
            res["hazard"] = "heat"

        res["hazard"] = hazard
        res["asset_geom"] = asset_geom

        res = res.groupby(["hazard", "asset_geom", "epoch", "scenario", "metric", "range"])["expected"].sum().reset_index()
        reslist.append(res)

results = pd.concat(reslist, axis=0, ignore_index=True)
epoch_order = ["baseline", "2030", "2050", "2080"]
scen_order = ["Base", "Low", "Medium", "High"]
range_order = ["min", "mean", "max"]

# results["epoch"] = pd.Categorical(results["epoch"], categories=epoch_order, ordered=True)
# results["scenario"] = pd.Categorical(results["scenario"], categories=scen_order, ordered=True)
# results.groupby(["hazard", "epoch", "scenario", "range"])[["expected"]].count()

results["expected"] = results["expected"] #/ 1e6  # million USD
# results["asset_geom"] = results["asset_geom"].map(labels.assets)
# results["hazard"] = results["hazard"].map(labels.hazards)

# %%
groupby = [col for col in results.columns if col != "expected"]
unstacked = results.groupby(groupby)["expected"].agg("sum").unstack("range").reset_index()
groupby = [col for col in groupby if col != "range"]
unstacked.columns = groupby + ["max", "mean", "min"] # alphabetical
unstacked = unstacked[groupby + ["min", "mean", "max"]]

# %%
unstacked.to_csv(outdir / "expected.csv")
# %%
