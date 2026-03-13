"""
Report figures: National-scale EADs barcharts.
"""
# %%
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.colors import ListedColormap

from oi_risk import config as cfg
from ttra.plot import labels, palette

sys.path.append("..") 
sns.set_style("whitegrid")
pd.options.display.max_rows = None

scaling_dict = {
    "cost": 1e-6,
    "damage": 1.,
    "defended": 1.,
    "hazard": 1.
}

unit_dict = {
    "cost": "million USD",
    "damage": "fraction",
    "defended": "varies by hazard",
    "hazard": "varies by hazard"
}

savefig = True
metric  = "cost"
scaling = scaling_dict[metric]
unit    = scaling_dict[metric]

asset_filter = [
    "tza_roads_edges",
    "tza_roads_bridges_and_culverts_nodes",
    "tza_railway_edges",
    "tza_hubs_polygons"
]

hazard_filter = [
    "fluvial",
    "pluvial",
    "coastal",
    "landslide",
    "cyclone",
    # "hd35",
    # "tasmax"
]

if __name__ == "__main__":
    config = cfg.load_config()
    indir = Path(config["paths"]["results"]) / "summaries"
    figdir = Path(config["paths"]["figures"]) / "summaries"
    figdir.mkdir(exist_ok=True, parents=True)

    data = pd.read_csv(indir / "expected.csv", index_col=[0])
    epoch_order = ["baseline", "2030", "2050", "2080"]
    scen_order = ["Base", "Low", "Medium", "High"]
    data = data[data["metric"] == metric].copy()

    data = data[data["hazard"].isin(hazard_filter)]
    data = data[data["asset_geom"].isin(asset_filter)]

    data["epoch"] = pd.Categorical(data["epoch"], categories=epoch_order, ordered=True)
    data["scenario"] = pd.Categorical(data["scenario"], categories=scen_order, ordered=True)
    data["asset"] = data["asset_geom"].map(labels.assets)
    data["hazard"] = data["hazard"].map(labels.hazards)
    data[['min', 'mean', 'max']] = data[['min', 'mean', 'max']] * scaling # million USD
    data = data.drop(columns=["metric", "asset_geom"])
    # %%
    if True:
        # inspect variation between scenarios
        hue = "scenario"
        data_pivot = data.groupby(["epoch", hue])[['min', 'mean', 'max']].sum().reset_index()

        fig, ax = plt.subplots(figsize=(9, 3), constrained_layout=True)

        sns.barplot(
            data=data_pivot,
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
        n_hues = data_pivot[hue].nunique()
        hue_order = data_pivot[hue].unique()

        width = 0.4
        bar_width = width / n_hues
        tza_gdp = 87.44 * 1e9 * scaling # wikipedia.org/wiki/Economy_of_Tanzania

        summary = []
        for i, epoch in enumerate(epoch_order):
            for j, hue_val in enumerate(hue_order):
                row = data_pivot[(data_pivot["epoch"] == epoch) & (data_pivot[hue] == hue_val)]
                if row.empty:
                    continue
                row = row.iloc[0]
                
                if metric in ["damage", "cost"]:
                    # no ranges for hazards
                    x = i + (j - n_hues/2 + 0.5) * bar_width
                    ax.errorbar(
                        x, row["mean"],
                        yerr=[[row["mean"] - row["min"]], [row["max"] - row["mean"]]],
                        fmt='none', c='k', capsize=3, linewidth=1
                    )
                
                summary.append((epoch, hue_val, row['min'].round(2), row['mean'].round(2), row['max'].round(2), (row['mean']/tza_gdp*100).round(4)))

        ax.legend(title=labels.fields[hue], frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))
        ax.set_xlabel("Epoch", fontweight="bold")
        ax.set_ylabel(f"Expected Annual Damages\n({unit})", fontweight="bold")

        summary = pd.DataFrame(summary, columns=["epoch", hue, "min", "mean", "max", "GDP(%)"])
        summary.to_csv(indir / "all.csv")
        print(summary)

        if savefig:
            fig.savefig(figdir / f"{metric}.png", transparent=True, dpi=300)

    # %%
    import random

    if True:
        # inspect variation between hazards or assets for a given scenario
        scenario = "Medium"
        random.seed(16)
        colors = palette.copy()

        for hue in ["hazard", "asset"]:
            random.shuffle(colors)
            
            data_scen = data[data["scenario"].isin(["Baseline", scenario])].copy()
            data_scen_pivot = data_scen.groupby(["epoch", hue])[['min', 'mean', 'max']].sum().reset_index()

            fig, ax = plt.subplots(figsize=(9, 3), constrained_layout=True)
            sns.barplot(
                data=data_scen_pivot,
                x="epoch",
                y="mean",
                hue=hue,
                width=0.4,
                linewidth=0.5, 
                edgecolor="k",
                palette=colors,
                ax=ax
            )

            n_epochs = len(epoch_order)
            n_hues = data_scen_pivot[hue].nunique()
            hue_order = data_scen_pivot[hue].unique()
            width = 0.4
            bar_width = width / n_hues

            summary = []
            for i, epoch in enumerate(epoch_order):
                for j, hue_val in enumerate(hue_order):
                    row = data_scen_pivot[(data_scen_pivot["epoch"] == epoch) & (data_scen_pivot[hue] == hue_val)]
                    if row.empty:
                        continue
                    row = row.iloc[0]
                    if metric in ["damage", "cost"]:
                        x = i + (j - n_hues/2 + 0.5) * bar_width
                        ax.errorbar(x, row["mean"], 
                                    yerr=[[row["mean"] - row["min"]], [row["max"] - row["mean"]]], 
                                    fmt='none', c='k', capsize=3, linewidth=1)
                    summary.append((epoch, hue_val, row['min'].round(2), row['mean'].round(2), row['max'].round(2), (row['mean']/tza_gdp*100).round(4)))

            ax.legend(title=labels.fields[hue], frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))
            
            ax.set_xlabel("Epoch", fontweight="bold")
            ax.set_ylabel("Expected Annual Damages\n(million USD)", fontweight="bold")

            summary = pd.DataFrame(summary, columns=["epoch", hue, "min", "mean", "max", "GDP(%)"])
            summary.to_csv(indir / f"{hue}.csv")
            print(summary)

            if savefig:
                fig.savefig(figdir / f"{metric}_{scenario}_{hue}s.png".lower(), transparent=True, dpi=300)
    # %%
    # NEW: conditional stackplots
    cmap = ListedColormap(colors)
    xvar = "asset"
    zvar = "hazard"
    yvar = "mean"
    epochs = ["2030", "2050", "2080"]
    scenarios = ["Low", "Medium", "High"]

    fig, axs = plt.subplots(3, 3, figsize=(9, 9), constrained_layout=True, sharex=True, sharey=True)

    i = 0
    for epoch in epochs:
        for scen in scenarios:
            ax = axs.flat[i]
            data_sub = data[data['epoch'] == epoch]
            data_sub = data_sub[data_sub['scenario'] == scen]
            data_sub = data_sub.groupby([xvar, zvar])[[yvar]].sum(min_count=1).reset_index()
            data_pivot = data_sub.pivot(index=xvar, columns=zvar, values=yvar)
            data_pivot.plot(kind='bar', stacked=True, cmap=cmap, ax=ax, legend=(i==0), edgecolor='k', linewidth=0.5)
            if i == 0:
                ax.get_legend().set_title(labels.fields[zvar])
            ax.label_outer()
            i += 1

    for i, epoch in enumerate(epochs):
        axs[i, 0].set_ylabel(epoch)
    
    for i, scen in enumerate(scenarios):
        axs[-1, i].set_xlabel(scen)

    if savefig:
        fig.savefig(figdir / f"{metric}_{scenario}_{xvar}sv{zvar}s.png".lower(), transparent=True, dpi=300)
    # %%
