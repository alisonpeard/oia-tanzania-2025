"""
Report figures: National-scale AALs.

"""
# %%
import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
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
    "cyclone",
    "hd35",
    "tasmax"
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
    "cyclone": "Cyclones",
    "hd35": "Extreme heat",
    "tasmax": "Extreme heat",
    "heat": "Extreme heat" # new column to groupby heat
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
        wd = os.path.join(results_dir, "risk_finalised", asset_geom, hazard)
        if not os.path.exists(wd):
            print(f"No data for: {asset_geom} - {hazard} - skipping")
            continue
        asset = du.load_asset_data(
            wd, metric_type="annual.parquet"
        )
        asset = asset[asset["metric"] == metric].copy()
        asset = asset.drop(columns=["metric"])

        res = asset.copy() #! new, move groupby to later
        # res = asset.groupby(["epoch", "scenario", "range"])["expected"].sum().reset_index()
        if hazard == "cyclone":
            # change 2010 SSPs to represent 2030
            flag_hist = res["scenario"] == "historical"
            flag_2010 = res["epoch"] == "2010"
            res_hist = res[flag_2010 & flag_hist].copy()
            res_2030 = res[flag_2010 & ~flag_hist].copy()
            res_future = res[~flag_2010 & ~flag_hist].copy()
            res_2030["epoch"] = "2030"
            res = pd.concat([res_hist, res_2030, res_future], axis=0, ignore_index=True)
            # rename epochs
            res["epoch"] = res["epoch"].replace({
                "2010": "baseline",
                "2090": "2080"
            })
            # remove railways with proposed or planned for baseline and 2030
            if asset_geom == "tza_railway_edges":
                flag_proposed = res["asset_type"].str.contains("proposed|planned", case=False)
                flag_current = res["epoch"].isin(["baseline", "2030"])
                flag_remove = flag_proposed & flag_current
                print(f"Found {flag_remove.sum()} proposed/planned railway assets under baseline - removing for baseline and 2030 epochs")
                res = res[~flag_remove].copy()
        elif hazard in ["fluvial", "pluvial", "coastal"]: 
            res["epoch"] = res["epoch"].replace({"2020": "baseline"})
        elif hazard == "landslide":
            res["epoch"] = res["epoch"].replace({"2015": "baseline"})
            res["expected"] = 0.3 * res["expected"]
        elif hazard in ["hd35", "tasmax"]:
            res["epoch"] = res["epoch"].replace({"2010": "baseline"})
            res["scenario"] = res["scenario"].replace({
                "rcp26": "ssp126",
                "rcp45": "ssp245",
                "rcp85": "ssp585"
            })
            res["hazard"] = "heat"

        if asset_geom in "tza_railway_edges":
            # step !sort out historical SSPs and 2030
            flag_base = res["epoch"] == "baseline"
            flag_2030 = res["epoch"] == "2030"
            flag_2050 = res["epoch"] == "2050"
            flag_2080 = res["epoch"] == "2080"

            flag_proposed = res["asset_type"].str.contains("proposed", case=False)
            flag_planned = res["asset_type"].str.contains("planned", case=False)
            flag_construction = res["asset_type"].str.contains("construction", case=False)
            # Table 4-2 in report
            mask_construction = flag_construction & flag_base
            mask_proposed = flag_proposed & (flag_base | flag_2030)
            mask_planned = flag_planned & (flag_base | flag_2030 | flag_2050)

            flag_remove = mask_construction | mask_proposed | mask_planned
            print(f"Found {flag_remove.sum()} railway assets under baseline, 2030, 2050 - removing")
            res = res[~flag_remove].copy()


        res["hazard"] = hazard
        res["asset_geom"] = asset_geom

        res = res.groupby(["hazard", "asset_geom", "epoch", "scenario", "range"])["expected"].sum().reset_index()
        results_list.append(res)


print(res.head())
# %% concatenate all the results
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
ax.set_ylabel("Expected Annual Damages\n(million USD)", fontweight="bold")  
plt.tight_layout()

# %%
# now look at variation between hazards/assets for a given scenario
scenario = "ssp245"

for hue in ["asset_geom"]: # "asset_geom", "hazard"
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
    ax.set_ylabel("Expected Annual Damages\n(million USD)", fontweight="bold")
    plt.tight_layout()

# %%
