"""
Report figures: National-scale EADs barcharts.
"""
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
sns.set_style("whitegrid")
pd.options.display.max_rows = None

metric = "cost"
savefig = False

assets = [
    "tza_roads_edges",
    # "tza_roads_bridges_and_culverts_nodes",
    # "tza_railway_edges",
    # "tza_hubs_polygons"
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
figdir = Path(config["paths"]["figures"]) / "summaries"
figdir.mkdir(exist_ok=True, parents=True)

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

        asset = asset[asset["metric"] == metric].copy()
        asset = asset.drop(columns=["metric"])

        res = asset.copy()
        res["epoch"] = res["epoch"].replace({labels.baselines[hazard]: "baseline"})
        res["scenario"] = res["scenario"].map(labels.scenarios)

        if hazard in ["hd35", "tasmax"]:
            res["hazard"] = "heat"

        res["hazard"] = hazard
        res["asset_geom"] = asset_geom

        res = res.groupby(["hazard", "asset_geom", "epoch", "scenario", "range"])["expected"].sum().reset_index()
        reslist.append(res)

# %% concatenate all the results
results = pd.concat(reslist, axis=0, ignore_index=True)
epoch_order = ["baseline", "2030", "2050", "2080"]
scen_order = ["Base", "Low", "Medium", "High"]
results["epoch"] = pd.Categorical(results["epoch"], categories=epoch_order, ordered=True)
results["scenario"] = pd.Categorical(results["scenario"], categories=scen_order, ordered=True)
results.groupby(["hazard", "epoch", "scenario", "range"])[["expected"]].count()

results["expected"] = results["expected"] / 1e6  # million USD
results["asset_geom"] = results["asset_geom"].map(labels.assets)
results["hazard"] = results["hazard"].map(labels.hazards)

# %%
# first look at variation between scenarios
if True:
    hue = "scenario"

    results_pivot = results.groupby(["epoch", hue, "range"])["expected"].sum().unstack("range").reset_index()
    results_pivot = results_pivot[results_pivot["max"] > 0].copy()

    fig, ax = plt.subplots(figsize=(9, 3), constrained_layout=True)

    sns.barplot(
        data=results_pivot,
        x="epoch",
        y="mean",
        hue=hue,
        width=0.4,
        linewidth=0.5, 
        edgecolor="k",
        palette="Spectral_r",
        ax=ax
    )

    n_epochs = len(epoch_order)
    n_hues = results_pivot[hue].nunique()
    hue_order = results_pivot[hue].unique()

    width = 0.4
    bar_width = width / n_hues
    tza_gdp = 87.44 * 1e9 # https://en.wikipedia.org/wiki/Economy_of_Tanzania
    for i, epoch in enumerate(epoch_order):
        for j, hue_val in enumerate(hue_order):
            row = results_pivot[(results_pivot["epoch"] == epoch) & (results_pivot[hue] == hue_val)]
            if row.empty:
                continue
            row = row.iloc[0]
            
            x = i + (j - n_hues/2 + 0.5) * bar_width
            ax.errorbar(x, row["mean"], 
                        yerr=[[row["mean"] - row["min"]], [row["max"] - row["mean"]]], 
                        fmt='none', c='k', capsize=3, linewidth=1)
            
            print(f"{epoch} {hue_val}: {row['mean']:,.2f} ({row['min']:,.2f} - {row['max']:,.2f}), ({(row['mean']/tza_gdp)*100:.3f} % of GDP)")

    ax.legend(title=labels.fields[hue], frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))
    ax.set_xlabel("Epoch", fontweight="bold")
    ax.set_ylabel("Expected Annual Damages\n(million USD)", fontweight="bold")  

# %%
# now look at variation between hazards/assets for a given scenario
if True:
    scenario = "Medium"

    for hue in ["hazard"]: # "asset_geom", "hazard"
        results_scen = results[results["scenario"].isin(["Baseline", scenario])].copy()
        results_scen_pivot = results_scen.groupby(["epoch", hue, "range"])["expected"].sum().unstack("range").reset_index()

        fig, ax = plt.subplots(figsize=(9, 3), constrained_layout=True)
        sns.barplot(
            data=results_scen_pivot,
            x="epoch",
            y="mean",
            hue=hue,
            width=0.4,
            linewidth=0.5, 
            edgecolor="k",
            palette=palette,
            ax=ax
        )

        n_epochs = len(epoch_order)
        n_hues = results_scen_pivot[hue].nunique()
        hue_order = results_scen_pivot[hue].unique()
        width = 0.4
        bar_width = width / n_hues

        for i, epoch in enumerate(epoch_order):
            for j, hue_val in enumerate(hue_order):
                row = results_scen_pivot[(results_scen_pivot["epoch"] == epoch) & (results_scen_pivot[hue] == hue_val)]
                if row.empty:
                    continue
                row = row.iloc[0]
                
                x = i + (j - n_hues/2 + 0.5) * bar_width
                ax.errorbar(x, row["mean"], 
                            yerr=[[row["mean"] - row["min"]], [row["max"] - row["mean"]]], 
                            fmt='none', c='k', capsize=3, linewidth=1)
                print(f"{epoch} {hue_val}: {row['mean']:,.2f} ({row['min']:,.2f} - {row['max']:,.2f}), ({(row['mean']/tza_gdp)*100:.3f} % of GDP)")

        ax.legend(title=labels.fields[hue], frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))
        
        ax.set_xlabel("Epoch", fontweight="bold")
        ax.set_ylabel("Expected Annual Damages\n(million USD)", fontweight="bold")

# %%
