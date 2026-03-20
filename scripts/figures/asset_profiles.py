"""
Report figures: Asset-type damage/cost profiles.

Updated to use cleaned risk data.
One figure for each hazard, asset, and epoch.
scenarios represented by error bars

"""
# %%
import numpy as np
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch

from pathlib import Path
from itertools import product

import ttra
from oi_risk import config as cfg


plt.rcParams.update({'font.size': 12, 'axes.titlesize': 14, 'axes.labelsize': 12})

dryrun = False
hazards   = [
    # "fluvial",
    # "pluvial",
    # "coastal",
    # "cyclone",
    # "landslide",
    "extremeheat"
]
asset_geoms = [
    "tza_roads_edges",
    "tza_railway_edges",
    # "tza_roads_bridges_and_culverts_nodes",
    # "tza_hubs_polygons",
]
metric = "cost"
statistic = "mean"
subregion = None
scalefac = 1e-6 if metric == "cost" else 1
assetcol = "asset_type"

if __name__ == "__main__":

    config = cfg.load_config()
    indir = Path(config["paths"]["results"]) / "intersections"
    figdir = Path(config["paths"]["figures"]) / "asset_profiles"
    figdir.mkdir(exist_ok=True, parents=True)


    combinations = list(product(hazards, asset_geoms))

    for hazard, asset_geom in (pbar := tqdm(combinations, desc="Processing combinations")):
        pbar.set_postfix(hazard=hazard, asset_geom=asset_geom, subregion=subregion)

        asset_dir = indir / asset_geom / hazard
        df = ttra.load_risk_profile(asset_dir, subregion=None, verbose=True)
        
        # choose correct metric column
        if metric == "damage":
            units = df["unit_type"].unique()[0]
        elif metric == "cost":
            units = "USD"

        # wrangle df into correct format for plotting
        risk_cols = [col for col in df.columns if col.startswith(metric)]
        df_agg = df.groupby(assetcol)[risk_cols].sum().reset_index()
        risk_gdf = df_agg.melt(
            id_vars=[assetcol],
            var_name="risk_col",
            value_name="value"
        )
        risk_tuples = risk_gdf["risk_col"].apply(ttra.hazards.extract_info)
        risk_info = pd.DataFrame(
            risk_tuples.tolist(),
            columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
        )
        risk_gdf = risk_gdf.join(risk_info).drop(columns=["risk_col"])

        print(f"  Rows in df: {len(df)}")
        print(f"  Risk columns: {len(risk_cols)}")
        print(f"  Rows after melt: {len(risk_gdf)}")

        if risk_gdf["value"].max() == 0:
            print(f"  No values for hazard: {hazard}, asset: {asset_geom}, "\
                    f"subregion: {subregion if subregion else 'national'}")
            continue

        totals = risk_gdf.copy()
        totals["scenario"] = totals["scenario"].map(ttra.plot.labels.scenarios)

        # After the new code produces totals
        print(f"totals shape: {totals.shape}")
        print(totals[totals['range'] == statistic].groupby([assetcol, 'epoch', 'rp'])['value'].sum().head(20))

        epochs = sorted(list(totals['epoch'].unique()), reverse=True) # biggest to smallest
        assets = sorted(list(totals[assetcol].unique()))
        nassets = len(assets)
        max_values = totals["value"].max()

        fig, axs = plt.subplots(
            1, nassets + 1,
            figsize=((nassets * 2) + 1, 3),
            sharey=True,
            gridspec_kw={
                'wspace': 0, 'width_ratios': [1]*nassets + [0.5]
            }
        )

        axs = axs.flatten()
        legend_ax = axs[-1]
        axs = axs[:-1]
        epoch_patches = []

        totals["value"] = totals["value"] * scalefac
        max_asset_value = totals["value"].max()
        print(f"   Max {metric} for asset: {max_asset_value:.2f} {scalefac} {units}")

        # plot each asset_type on its own axis
        for i, asset_type in (pbar := tqdm(enumerate(assets), total=len(assets))):
            pbar.set_description(f" Processing asset type: {asset_type}")
            ax = axs[i]
            totals_asset = totals[totals[assetcol] == asset_type].copy()

            for i_epoch, epoch in (pbar:=tqdm(enumerate(epochs), total=len(epochs), leave=False)):
                pbar.set_description(f"  Processing epoch: {epoch}")
                totals_epoch = totals_asset[totals_asset['epoch'] == epoch].copy()
                totals_epoch = totals_epoch[totals_epoch['range'] == statistic].copy()
                if totals_epoch.empty:
                    print(f"    No data for epoch: {epoch}, asset type: {asset_type}, skipping")
                    continue

                totals_epoch = totals_epoch.drop(columns=["metric", "hazard", "epoch"])
                totals_epoch["rp"] = totals_epoch["rp"].astype(int)
                totals_epoch = totals_epoch.sort_values(by=[assetcol, "rp"])

                returnperiods = sorted(
                    list(totals_epoch['rp'].unique()),
                    key=lambda x: int(x)
                )

                # define colours
                base_col = plt.get_cmap("Spectral")(i_epoch / len(epochs))
                cmap = ttra.plot.create_white_to_color_cmap(base_col)
                colors = [cmap(i/len(returnperiods)) for i in range(len(returnperiods))]
                palette_dict = dict(zip(returnperiods, colors))
                legend_flag = (i_epoch == len(epochs) - 1) & (i == len(assets) - 1)
                epoch_flag = (i_epoch < len(epochs) - 1) & (i == 0)

                n_patches_before = len(ax.patches)
                n_lines_before = len(ax.lines)

                totals_epoch = totals_epoch.pivot(
                    index=["asset_type", "rp", "range"],
                    values="value",
                    columns="scenario"
                ).reset_index()

                if int(epoch) <= 2020:
                    column = "Base"
                else:
                    column = "Medium"

                sns.barplot(
                    x=totals_epoch[assetcol].values,
                    y=totals_epoch[column].values,
                    ax=ax,
                    hue=totals_epoch['rp'].values,
                    palette=palette_dict,
                    edgecolor='black',
                    linewidth=0.5,
                    width=0.6,
                    legend=False
                )

                if column == "Medium":
                    # plot error bars for lower/upper scenarios
                    new_patches = ax.patches[n_patches_before:]
                    
                    for patch, rp in zip(new_patches, returnperiods):
                        row = totals_epoch[totals_epoch["rp"] == rp]
                        if row.empty:
                            continue
                        row = row.iloc[0]
                        
                        # Use the actual bar center position
                        x = patch.get_x() + patch.get_width() / 2
                        ycentre = row["Medium"]
                        ylower = np.maximum(0.0, ycentre - row["Low"])
                        yupper = np.maximum(0.0, row["High"] - ycentre)
                        if (ylower > 0) and (yupper > 0):
                            # print(ylower, yupper)
                            ax.errorbar(
                                x, ycentre, 
                                yerr=[[ylower], [yupper]], 
                                fmt='none', c='k', capsize=0, linewidth=0.5,
                                linestyle="dotted",
                                zorder=100,
                            )

                if epoch_flag:
                    # add legend patch for epoch
                    epoch_patch = Patch(
                        facecolor=base_col,
                        edgecolor='black',
                        linewidth=0.5,
                        label=epoch
                    )
                    epoch_patches.append(epoch_patch)
        
        for ax in axs:
            ax.tick_params(axis='y', which='major', labelsize=8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.yaxis.set_ticks_position('left')
            ax.tick_params(axis='x', which='both', bottom=False, top=False)
            ax.tick_params(axis='y', which="both", direction="in")
            ax.set_xlim(-0.35, 0.35)
            
        for ax in axs[1:]:
            ax.spines['left'].set_visible(False)
            ax.tick_params(axis='y', left=False, labelleft=False)

        if scalefac != 1:
            # format scale factor from 1e06 to 10^6
            if scalefac == 1e-6:
                axs[0].set_ylabel(fr"{metric.title()} (m {units})", fontweight='bold')
            elif scalefac == 1e-3:
                axs[0].set_ylabel(fr"{metric.title()} (k {units})", fontweight='bold')
            elif scalefac == 1e-9:
                axs[0].set_ylabel(fr"{metric.title()} (bn {units})", fontweight='bold')
            else:
                raise NotImplementedError(f"Scale factor {scalefac} not implemented")
        else:
            axs[0].set_ylabel(fr"{metric.title()} ({units})", fontweight='bold')

        # legend 
        legend_ax.axis('off')
        leg1 = legend_ax.legend(
            handles=epoch_patches,
            loc='lower left',
            frameon=False,
            title=f"Δbaseline ({epoch[-1]})",
            fontsize=8,
            title_fontsize=9,
            labelspacing=0.3
        )

        legend_ax.add_artist(leg1)
        rp_patches = [Patch(facecolor=palette_dict[rp], edgecolor='black', linewidth=0.5, label=str(rp)) 
                    for rp in returnperiods]
        leg2 = legend_ax.legend(handles=rp_patches, loc='upper left', frameon=False,
                                title=f"{ttra.plot.labels.hazards[hazard]}\nreturn period",
            fontsize=8,
            title_fontsize=9,
            labelspacing=0.3)
            
        for ax in axs:
            # add y-axis gridlines
            ax.grid(axis='y', linestyle='--', linewidth=0.5, alpha=0.7)
            ax.set_axisbelow(True)

        outfile = figdir / f"{asset_geom}_{hazard}_{metric}_{subregion if subregion else 'national'}_{statistic}.png"
        fig.savefig(outfile, dpi=300, bbox_inches='tight', transparent=True)
        print(f"  Saved figure to: {outfile}")
        plt.show()

        if dryrun: break

# %%
