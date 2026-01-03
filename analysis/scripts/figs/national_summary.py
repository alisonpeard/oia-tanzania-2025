"""
Report figures: National-scale AALs.

NOTE: Cyclone has histoical baseline *and* historical SSP data. Filter to
just baselines.
"""
# %%
import os
import sys
import pandas as pd
import seaborn as sns
sys.path.append("..") 

import utils.data as du
import utils.plot as pu
import utils.paths as paths

sns.set_style("whitegrid")
pd.options.display.max_rows = None

metric = "cost"
results_dir = paths.results_dir

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
    "cyclone"
]

asset_labels = {
    "tza_roads_edges": "Roads",
    "tza_roads_bridges_and_culverts_nodes": "Bridges & Culverts",
    "tza_railway_edges": "Railways",
    "tza_hubs_polygons": "Ports & Airports"
}

hazard_labels = {
    "fluvial": "Fluvial flooding",
    "pluvial": "Pluvial flooding",
    "coastal": "Coastal flooding",
    "landslide": "Landslides",
    "cyclone": "Cyclones"
}

field_labels = {
    "asset_geom": "Infrastructure sector",
    "hazard": "Climate hazard",
    "scenario": "Climate scenario"
}

scenario_labels = {
    "historical": "Baseline",
    "ssp126": "SSP1-2.6",
    "ssp245": "SSP2-4.5",
    "ssp585": "SSP5-8.5"
}




results_list = []
for asset_geom in assets:
    for hazard in hazards:
        wd = os.path.join(results_dir, "risk_cleaned", asset_geom, hazard)
        asset = du.load_asset_data(
            wd, metric_type="annual.parquet"
        )
        asset = asset[asset["metric"] == metric].copy()
        asset = asset.drop(columns=["metric"])
        res = asset.groupby(["epoch", "scenario", "range"])["expected"].sum().reset_index()
        
        # explicitly add baseline simplifications
        if hazard == "cyclone":
            scen_hist = res["scenario"] == "historical"
            epoch_base = res["epoch"] == "2010"
            res = res[~(epoch_base & ~scen_hist)].copy()
            res["epoch"] = res["epoch"].replace({
                "2010": "baseline",
                "2090": "2080"
            })
        elif hazard in ["fluvial", "pluvial", "coastal"]: 
            res["epoch"] = res["epoch"].replace({"2020": "baseline"})
        elif hazard == "landslide":
            res["epoch"] = res["epoch"].replace({"2015": "baseline"})
        res["hazard"] = hazard
        res["asset_geom"] = asset_geom
        results_list.append(res)
# %%

results = pd.concat(results_list, axis=0, ignore_index=True)

epoch_order = ["baseline", "2030", "2050", "2080"]
results["epoch"] = pd.Categorical(results["epoch"], categories=epoch_order, ordered=True)
results.groupby(["hazard", "epoch", "scenario", "range"])[["expected"]].count()

# %%
results["expected"] = results["expected"] / 1e6  # million USD
results["asset_geom"] = results["asset_geom"].map(asset_labels)
results["hazard"] = results["hazard"].map(hazard_labels)

# %%
# first look at variation between scenarios
import seaborn as sns
import matplotlib.pyplot as plt

hue = "scenario"

results_pivot = results.groupby(["epoch", hue, "range"])["expected"].sum().unstack("range").reset_index()
results_pivot = results_pivot[results_pivot["max"] > 0].copy()
results_pivot[hue] = results_pivot["scenario"].map(scenario_labels)

fig, ax = plt.subplots(figsize=(9, 3))

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

ax.legend(title=field_labels[hue], frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))
ax.set_xlabel("Epoch", fontweight="bold")
ax.set_ylabel("Annual expected losses\n(million USD)", fontweight="bold")  
plt.tight_layout()

# %%
# now look at variation between hazards/assets for a given scenario
scenario = "ssp245"

for hue in ["asset_geom", "hazard"]:
    results_scen = results[results["scenario"].isin(["historical", scenario])].copy()
    results_scen_pivot = results_scen.groupby(["epoch", hue, "range"])["expected"].sum().unstack("range").reset_index()

    fig, ax = plt.subplots(figsize=(9, 3))
    sns.barplot(
        data=results_scen_pivot,
        x="epoch",
        y="mean",
        hue=hue,
        width=0.4,
        linewidth=0.5, 
        edgecolor="k",
        palette=pu.npg,
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

    ax.legend(title=field_labels[hue], frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))
    
    ax.set_xlabel("Epoch", fontweight="bold")
    ax.set_ylabel("Annual expected losses\n(million USD)", fontweight="bold")
    plt.tight_layout()
# %%
# 