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
from ttra.plot import labels, hazardclrs, assetclrs

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
unit    = unit_dict[metric]
project = [None, "ccdr", "cerc"][0]

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
    "extremeheat"
]

if project is not None:
    if project == "cerc":
        hazard_filter = ["fluvial", "pluvial", "coastal", "landslide", "cyclone"]
    if project == "ccdr":
        hazard_filter = ["fluvial", "extremeheat"]
        asset_filter = ["tza_roads_edges", "tza_roads_bridges_and_culverts_nodes"]

if __name__ == "__main__":
    config = cfg.load_config()
    indir = Path(config["paths"]["results"]) / "summary_tables"
    figdir = Path(config["paths"]["figures"]) / "summary_charts"
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
    data["hazard"] = pd.Categorical(data["hazard"], categories=labels.hazards.values(), ordered=True)
    data["asset"] = pd.Categorical(data["asset"], categories=labels.assets.values(), ordered=True)

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

        # add errorbars
        summary = []
        for i, epoch in enumerate(epoch_order):
            for j, hue_val in enumerate(hue_order):
                row = data_pivot[(data_pivot["epoch"] == epoch) & (data_pivot[hue] == hue_val)]
                if row.empty:
                    continue
                row = row.iloc[0]
                
                if metric in ["damage", "cost"]:
                    x = i + (j - n_hues/2 + 0.5) * bar_width
                    ax.errorbar(
                        x, row["mean"],
                        yerr=[[row["mean"] - row["min"]], [row["max"] - row["mean"]]],
                        fmt='none', c='k', capsize=3, linewidth=1
                    )
                
                summary.append((
                    epoch, hue_val, row['min'].round(2),
                    row['mean'].round(2), row['max'].round(2),
                    (row['mean']/tza_gdp*100).round(4),
                    (row['min']/tza_gdp*100).round(4),
                    (row['max']/tza_gdp*100).round(4),
                ))

        ax.legend(title=labels.fields[hue], frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))
        ax.set_xlabel("Epoch", fontweight="bold")
        ax.set_ylabel(f"Expected Annual Damages\n({unit})", fontweight="bold")

        summary = pd.DataFrame(summary, columns=[
            "epoch", hue, "min", "mean", "max",
            "mean GDP(%)", "min GDP(%)", "max GDP(%)"
        ])
        print(summary)

        if savefig:
            summary.to_csv(indir / f"{metric}.csv", index=False)
            fig.savefig(figdir / f"{metric}.png", transparent=True, dpi=300)

    # %%
    if True:
        # inspect variation between hazards or assets for a given scenario
        scenario = "Medium"
        width = 0.4

        for hue, palette in [
            ("hazard", hazardclrs),
            ("asset", assetclrs)
        ]:
            
            data_scen = data[data["scenario"].isin(["Base", scenario])].copy()
            data_scen_pivot = data_scen.groupby(["epoch", hue])[['min', 'mean', 'max']].sum().reset_index()

            fig, ax = plt.subplots(figsize=(9, 3), constrained_layout=True)
            sns.barplot(
                data=data_scen_pivot,
                x="epoch",
                y="mean",
                hue=hue,
                width=width,
                linewidth=0.5, 
                edgecolor="k",
                palette=palette,
                ax=ax
            )

            n_epochs = len(epoch_order)
            n_hues = len(data[hue].cat.categories)
            hue_order = data[hue].cat.categories
            width = width
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
                    summary.append((epoch, hue_val, row['min'].round(2), row['mean'].round(2), row['max'].round(2), (row['mean']/tza_gdp*100).round(4), (row['min']/tza_gdp*100).round(4), (row['max']/tza_gdp*100).round(4)))


            ax.legend(title=labels.fields[hue], frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))
            
            ax.set_xlabel("Epoch", fontweight="bold")
            ax.set_ylabel("Expected Annual Damages\n(million USD)", fontweight="bold")

            summary = pd.DataFrame(summary, columns=["epoch", hue, "min", "mean", "max", "mean GDP(%)", "min GDP(%)", "max GDP(%)"])
            print(f"\nSummary {hue}:\n{summary}\n")

            if savefig:
                summary.to_csv(indir / f"{metric}_{scenario}_{hue}.csv".lower(), index=False)
                fig.savefig(figdir / f"{metric}_{scenario}_{hue}s.png".lower(), transparent=True, dpi=300)
    
    # %%
    # Add new conditional stackplots
    ymid = "mean"
    ymin = "min"
    ymax = "max"
    epochs = ["2030", "2050", "2080"]
    scenarios = ["Low", "Medium", "High"]


    def add_errorbars(ax, ymin, ymid, ymax):
        total_mid = ymid.sum(axis=1)
        total_min = ymin.sum(axis=1)
        total_max = ymax.sum(axis=1)

        error_lower = total_mid - total_min
        error_upper = total_max - total_mid

        xpos = range(len(total_mid))
        ax.errorbar(
            x=xpos,
            y=total_mid.values,
            yerr=[error_lower.values, error_upper.values],
            fmt='none',
            c='k',
            capsize=3,
            linewidth=0.5,
            zorder=5
        )


    for xvar, zvar, clrmap in [
        ["hazard", "asset", assetclrs],
        ["asset", "hazard", hazardclrs]
        ]:

        fig, axs = plt.subplots(
            3, 3, figsize=(10, 5), constrained_layout=True,
            sharex=True, sharey=True,
            gridspec_kw={'wspace': 0.05}
        )

        i = 0
        summaries = []
        for epoch in epochs:
            for scen in scenarios:
                ax = axs.flat[i]
                data_sub = data[data['epoch'] == epoch]
                data_sub = data_sub[data_sub['scenario'] == scen]

                data_mid = data_sub.groupby([xvar, zvar])[[ymid]].sum(min_count=1).reset_index()
                data_mid = data_mid.pivot(index=xvar, columns=zvar, values=ymid)

                data_min = data_sub.groupby([xvar, zvar])[[ymin]].sum(min_count=1).reset_index()
                data_min = data_min.pivot(index=xvar, columns=zvar, values=ymin)

                data_max = data_sub.groupby([xvar, zvar])[[ymax]].sum(min_count=1).reset_index()
                data_max = data_max.pivot(index=xvar, columns=zvar, values=ymax)

                clrs = [clrmap[col] for col in data_mid.columns]
                data_mid.plot(
                    kind='bar', stacked=True, color=clrs, ax=ax,
                    legend=False, edgecolor='k', linewidth=0.5
                )

                # adjust subplot appearances
                ax.label_outer()
                ax.grid(axis='x', visible=False)
                add_errorbars(ax, data_min, data_mid, data_max)

                data_perc = data_mid / data_mid.sum(axis=1) * 100

                summaries.append((epoch, scen, data_perc))
                i += 1

        # clean y-axis ticks and gridlines
        ymax_val = data[ymax].max()
        step = 50 if ymax_val > 250 else 25
        ticks = range(0, int(ymax_val) + step, step)
        for ax in axs.flat:
            ax.set_yticks(ticks)
            ax.set_ylim(ticks[0], ticks[-1])

        # make legend
        handles, lbels = ax.get_legend_handles_labels()
        fig.legend(
            handles, 
            lbels, 
            title=labels.fields[zvar], 
            loc='upper center', 
            bbox_to_anchor=(0.5, 1.105),
            ncol=len(lbels),
            frameon=False,
            title_fontproperties={"weight": "bold"}
        )

        for i, epoch in enumerate(epochs):
            axs[i, 0].set_ylabel(epoch, fontweight="bold")
        
        for i, scen in enumerate(scenarios):
            axs[-1, i].set_xlabel(scen, fontweight="bold")
            xlabels = axs[-1, i].get_xticklabels()
            xlabels = [x.get_text().replace(" ", "\n") for x in xlabels]
            axs[-1, i].set_xticklabels(
                xlabels, rotation=45, ha='center'
            )
        plt.subplots_adjust(top=0.85)

        data_perc = pd.concat([
            pd.DataFrame({
                "epoch": epoch,
                "scenario": scen,
                xvar: data_perc.index,
                **{col: data_perc[col].values for col in data_perc.columns}
            }) for epoch, scen, data_perc in summaries
        ], ignore_index=True)

        print(f"\nSummary {xvar} vs {zvar}:\n{data_perc.groupby(xvar)[list(clrmap.keys())].mean()}\n")

        if savefig:
            data_perc.to_csv(indir / f"{metric}_{scenario}_{xvar}sv{zvar}s.csv".lower(), index=True)
            fig.savefig(figdir / f"{metric}_{scenario}_{xvar}sv{zvar}s.png".lower(), transparent=True, dpi=300)
    # %%