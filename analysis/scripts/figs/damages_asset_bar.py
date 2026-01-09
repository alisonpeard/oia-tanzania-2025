"""
Report figures: Asset-type damage/cost profiles.

Updated to use cleaned risk data.
One figure for each hazard, asset, and epoch.
scenarios represented by error bars

"""
# %%
import os
# from glob import glob

import numpy as np
import pandas as pd
# import geopandas as gpd
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
# import matplotlib.colors as mcolors
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch


import sys
sys.path.append("..")
from utils import data as du
from utils import plot as pu

plt.rcParams.update({'font.size': 12, 'axes.titlesize': 14, 'axes.labelsize': 12})

dryrun = False
HAZARDS   = [
    # "fluvial",
    # "pluvial",
    # "coastal",
    # "cyclone",
    # "landslide"
    # "hd35",
    "tasmax"
]
ASSET_GEOMS = [
    # "tza_roads_edges",
    "tza_railway_edges",
    # "tza_roads_bridges_and_culverts_nodes",
    # "tza_hubs_polygons",
]
METRIC = "cost"
RANGE = "mean"
# RANGE = RANGE + "_" + RANGE if METRIC == "cost" else RANGE
SUBREGION = [None, "kilimanjaro"][0]
WD = "/Users/alison/Local/github/oia-tanzania-2025/results"
SCALE_FACTOR = 1e-6 if METRIC == "cost" else 1
FRAMEWORKS = {
    "fluvial": {"base": "historical", "lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "pluvial": {"base": "historical", "lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "coastal": {"base": "historical", "lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "cyclone": {"base": "historical", "lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "landslide": {"base": "historical", "lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "hd35": {"base": "historical", "lower": "rcp26", "centre": "rcp45", "upper": "rcp85"},
    "tasmax": {"base": "historical", "lower": "rcp26", "centre": "rcp45", "upper": "rcp85"},
}


if __name__ == "__main__":

    outdir = "../figures/asset_type_profiles"
    os.makedirs(outdir, exist_ok=True)

    for HAZARD in HAZARDS:
        FRAMEWORK = FRAMEWORKS[HAZARD]
        for ASSET_GEOM in ASSET_GEOMS:

            ASSET_TYPE = "asset_type"

            print(f"Plotting hazard: {HAZARD}, asset: {ASSET_GEOM}, subregion: {SUBREGION if SUBREGION else 'national'}")
            #! temp patch for risk location
            base_dir = os.path.join(WD, "risk_final", ASSET_GEOM, HAZARD)
            df = du.load_asset_data(base_dir, metric_type="profile.geoparquet", subregion=SUBREGION, verbose=True)

            if METRIC == "damage":
                METRIC_UNIT = df["unit_type"].unique()[0]
            elif METRIC == "cost":
                METRIC_UNIT = "USD"

            risk_cols = [col for col in df.columns if col.startswith(METRIC)]
            df_agg = df.groupby(ASSET_TYPE)[risk_cols].sum().reset_index()
            risk_gdf = df_agg.melt(
                id_vars=[ASSET_TYPE],
                var_name="risk_col",
                value_name="value"
            )
            risk_tuples = risk_gdf["risk_col"].apply(du.extract_hazard_info)
            risk_info = pd.DataFrame(
                risk_tuples.tolist(),
                columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
            )
            risk_gdf = risk_gdf.join(risk_info).drop(columns=["risk_col"])

            print(f"  Rows in df: {len(df)}")
            print(f"  Risk columns: {len(risk_cols)}")
            print(f"  Rows after melt: {len(risk_gdf)}")

            if risk_gdf["value"].max() == 0:
                print(f"  No values for hazard: {HAZARD}, asset: {ASSET_GEOM}, "\
                      f"subregion: {SUBREGION if SUBREGION else 'national'}")
                continue

            totals = risk_gdf.copy()

            # After the new code produces totals
            print(f"totals shape: {totals.shape}")
            print(totals[totals['range'] == RANGE].groupby([ASSET_TYPE, 'epoch', 'rp'])['value'].sum().head(20))

            EPOCHS = sorted(list(totals['epoch'].unique()), reverse=True) # biggest to smallest
            assets = sorted(list(totals[ASSET_TYPE].unique()))
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

            totals["value"] = totals["value"] * SCALE_FACTOR
            max_asset_value = totals["value"].max()
            print(f"   Max {METRIC} for asset: {max_asset_value:.2f} {SCALE_FACTOR} {METRIC_UNIT}")

            # plot each asset_type on its own axis
            for i, asset_type in (pbar := tqdm(enumerate(assets), total=len(assets))):
                pbar.set_description(f" Processing asset type: {asset_type}")
                ax = axs[i]
                totals_asset = totals[totals[ASSET_TYPE] == asset_type].copy()
                for i_EPOCH, EPOCH in (pbar:=tqdm(enumerate(EPOCHS), total=len(EPOCHS), leave=False)):
                    pbar.set_description(f"  Processing epoch: {EPOCH}")

                    totals_epoch = totals_asset[totals_asset['epoch'] == EPOCH].copy()
                    totals_epoch = totals_epoch[totals_epoch['range'] == RANGE].copy()
                    totals_epoch = totals_epoch.drop(columns=["metric", "hazard", "epoch"])
                    
                    if totals_asset.empty:
                        print(f"    No data for epoch: {EPOCH}, asset type: {asset_type}, skipping")
                        continue

                    totals_epoch["rp"] = totals_epoch["rp"].astype(int)
                    totals_epoch = totals_epoch.sort_values(by=[ASSET_TYPE, "rp"])

                    returnperiods = sorted(
                        list(totals_epoch['rp'].unique()),
                        key=lambda x: int(x)
                    )

                    base_col = plt.get_cmap("Spectral")(i_EPOCH / len(EPOCHS))
                    cmap = pu.create_white_to_color_cmap(
                        base_col, white="#ffffff"
                    )
                    colors = [cmap(i/len(returnperiods)) for i in range(len(returnperiods))]
                    palette_dict = dict(zip(returnperiods, colors))
                    legend_flag = (i_EPOCH == len(EPOCHS) - 1) & (i == len(assets) - 1)
                    epoch_flag = (i_EPOCH < len(EPOCHS) - 1) & (i == 0)

                    n_patches_before = len(ax.patches)
                    n_lines_before = len(ax.lines)

                    totals_epoch = totals_epoch.pivot(
                        index=["asset_type", "rp", "range"],
                        values="value",
                        columns="scenario"
                    ).reset_index()

                    if int(EPOCH) <= 2020:
                        column = FRAMEWORK["base"]
                    else:
                        column = FRAMEWORK["centre"]

                    sns.barplot(
                        x=totals_epoch[ASSET_TYPE].values,
                        y=totals_epoch[column].values,
                        ax=ax,
                        hue=totals_epoch['rp'].values,
                        palette=palette_dict,
                        edgecolor='black',
                        linewidth=0.5,
                        width=0.6,
                        legend=False
                    )

                    # add error bars
                    if column == FRAMEWORK["centre"]:
                        # plot error bars for lower/upper scenarios
                        new_patches = ax.patches[n_patches_before:]
                        
                        for patch, rp in zip(new_patches, returnperiods):
                            row = totals_epoch[totals_epoch["rp"] == rp]
                            if row.empty:
                                continue
                            row = row.iloc[0]
                            
                            # Use the actual bar center position
                            x = patch.get_x() + patch.get_width() / 2
                            ycentre = row[FRAMEWORK["centre"]]
                            ylower = np.maximum(0.0, ycentre - row[FRAMEWORK["lower"]])
                            yupper = np.maximum(0.0, row[FRAMEWORK["upper"]] - ycentre)
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
                            label=EPOCH
                        )
                        epoch_patches.append(epoch_patch)
                    

            formatter = FuncFormatter(pu.clean_sci_formatter)

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

            if SCALE_FACTOR != 1:
                # format scale factor from 1e06 to 10^6
                if SCALE_FACTOR == 1e-6:
                    axs[0].set_ylabel(fr"{METRIC.title()} (million {METRIC_UNIT})", fontweight='bold')
                elif SCALE_FACTOR == 1e-3:
                    axs[0].set_ylabel(fr"{METRIC.title()} (k {METRIC_UNIT})", fontweight='bold')
                elif SCALE_FACTOR == 1e-9:
                    axs[0].set_ylabel(fr"{METRIC.title()} (billion {METRIC_UNIT})", fontweight='bold')
                else:
                    raise NotImplementedError(f"Scale factor {SCALE_FACTOR} not implemented")
            else:
                axs[0].set_ylabel(fr"{METRIC.title()} ({METRIC_UNIT})", fontweight='bold')

            # legend 
            legend_ax.axis('off')
            leg1 = legend_ax.legend(
                handles=epoch_patches,
                loc='lower left',
                frameon=False,
                title=f"Δbaseline ({EPOCHS[-1]})",
                fontsize=8,
                title_fontsize=9,
                labelspacing=0.3
            )
            legend_ax.add_artist(leg1)
            rp_patches = [Patch(facecolor=palette_dict[rp], edgecolor='black', linewidth=0.5, label=str(rp)) 
                        for rp in returnperiods]
            leg2 = legend_ax.legend(handles=rp_patches, loc='upper left', frameon=False,
                                    title=f"{pu.hazard_labels[HAZARD]}\nreturn period",
                fontsize=8,
                title_fontsize=9,
                labelspacing=0.3)
            
            # add a background x and y grid to all axes
            for ax in axs:
                ax.grid(axis='y', linestyle='--', linewidth=0.5, alpha=0.7)
                ax.set_axisbelow(True)

            outfile = f"{outdir}/{ASSET_GEOM}_{HAZARD}_{METRIC}_{RANGE}_{SUBREGION if SUBREGION else 'national'}_{EPOCH}.png"
            fig.savefig(outfile, dpi=300, bbox_inches='tight', transparent=True)
            print(f"  Saved figure to: {outfile}")
            plt.show()

            if dryrun: break
        if dryrun: break

# %%
