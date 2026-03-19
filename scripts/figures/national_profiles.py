"""Not using in report but useful for checking for missing data."""
# %%
import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import matplotlib.colors as mcolors
from matplotlib.patches import Patch

import ttra
from oi_risk import config

plt.rcParams['font.size'] = 8
plt.rcParams['figure.dpi'] = 300


SAVEFIG = False
METRIC = "cost"
METRIC_UNIT = "USD"
RANGE = "mean"
SCALE_FACTOR = 1e-6
HAZARDS   = [
    "cyclone",
    # "landslide",
    # "pluvial",
    # "fluvial",
    # "coastal",
    # "hd35",
    # "tasmax"
]
ASSET_GEOMS = [
    "tza_railway_edges",
    # "tza_roads_edges",
    # "tza_roads_bridges_and_culverts_nodes",
    # "tza_hubs_polygons"
]

def summarise_risk_by_scenario(
        df:pd.DataFrame, metric:str, range_str:str
    ) -> pd.DataFrame:
    cols = [col for col in df.columns if col.startswith(metric)]
    df = df[cols].copy().T.reset_index()
    tuples = df["index"].apply(ttra.hazards.extract_info)
    info_df = pd.DataFrame(
        tuples.tolist(),
        columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
    )
    info_df = info_df[info_df['range'] == range_str].copy()
    info_df = info_df.drop(columns=['metric', 'hazard', 'range'])
    df = df.drop(columns=['index'])
    totals = df.sum(axis=1).rename("total")
    totals = info_df.join(totals, how="left")

    # format field types
    totals["epoch"] = totals["epoch"].astype(int)
    totals["rp"] = totals["rp"].astype(int)
    scenario_order = sorted(list(totals['scenario'].unique()))
    totals['scenario'] = pd.Categorical(totals['scenario'], categories=scenario_order, ordered=True)
    totals = totals.sort_values(by=["epoch", "scenario", "rp"])

    return totals


def format_legend_handles(cmap, labels):
    n = len(labels)
    handles = [
        Patch(
            facecolor=(cmap(i / n)),
            edgecolor='black',
            linewidth=0.5,
            label=label
            ) for i, label in enumerate(labels)
    ]
    return handles


if __name__ == "__main__":
    config = config.load_config()

    indir = Path(config["paths"]["results"]) / "intersections"
    figdir = Path(config["paths"]["figures"])
    figdir = figdir / "damages_national_bar"
    figdir.mkdir(parents=True, exist_ok=True)

    for hazard in HAZARDS:
        for asset_geom in ASSET_GEOMS:
            # load the asset data
            inpath = indir / asset_geom / hazard
            asset_df = ttra.load_risk_profile(inpath)

            # pivot so each row is a scenario/epoch/rp combination
            results = summarise_risk_by_scenario(asset_df, METRIC, RANGE)

            # filter to scen/epoch combinations with risk > 0
            totals = results.groupby(["scenario", "epoch"]).sum()
            valid_scens = totals[totals['total'] > 0].reset_index()
            ncols = len(valid_scens)
            if ncols == 0:
                print(f"  No {METRIC}s for {hazard} and {asset_geom}")
                continue
            results = results.merge(
                valid_scens[['scenario', 'epoch']],
                on=['scenario', 'epoch'],
                how='inner'
            )

            # get all scenarios, epochs, and return periods
            scenarios = sorted(list(set(results['scenario'])))
            epochs = sorted(list(set(results['epoch'])))
            returnperiods = sorted(list(set(results['rp'])))

            # plotting starts here
            fig, axs = plt.subplots(
                1, ncols, figsize=(7, 1.8), sharey=True, #figsize=(ncols * 2, 4),
                gridspec_kw={'wspace': 0}
            )
            axs = [axs] if ncols == 1 else axs.flatten()

            # prepare the colourmaps
            palette = ttra.plot.palette
            cmaps = {}
            for i, scenario in enumerate(scenarios):
                cmap = ttra.plot.create_white_to_color_cmap(palette[i])
                cmaps[scenario] = cmap

            # plot the data
            i = 0
            for epoch in sorted(epochs):
                results_epoch = results[results['epoch'] == epoch].copy()
                scenarios_epoch = list(results_epoch['scenario'].unique())
                first_scenario = True
                for scenario in sorted(scenarios_epoch):
                    try:
                        ax = axs[i]
                        results_scen = results_epoch[results_epoch['scenario'] == scenario].copy()
                        results_scen["scenario"] = results_scen["scenario"].astype(str) # NB!

                        cmap = cmaps[scenario]
                        colors = [cmap(i/len(returnperiods)) for i in range(len(returnperiods))]
                        palette_dict = dict(zip(returnperiods, colors))

                        sns.barplot(
                            x=results_scen['scenario'].values,
                            y=results_scen["total"].values * SCALE_FACTOR,
                            hue=results_scen['rp'].values, ax=ax,
                            palette=palette_dict,
                            legend=False,
                            edgecolor='black',
                            linewidth=0.5,
                            width=0.6
                        )
                        ax.set_xlabel("")
                    except Exception as e:
                        print(f"ERROR: {e}")
                    
                    # remove spines between scenarios in the same epoch
                    if not first_scenario:
                        ax.spines['left'].set_visible(False)
                        ax.yaxis.set_ticks_position('none')
                        ax.set_xlabel("")
                    # remove ticks for internal spines
                    elif epoch != epochs[0]:
                        ax.yaxis.set_ticks_position('none')
                    
                    first_scenario = False
                    i += 1

                # add centred epoch label
                mid_idx = i - len(scenarios_epoch) // 2 - 1
                axs[mid_idx].set_xlabel(f"{epoch}", fontweight='bold', labelpad=5)

            # tidy up axes
            for ax in axs:
                ax.set_xlim(-0.35, 0.35)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.yaxis.grid(True, linestyle='--', which='major', color='darkgrey', alpha=0.4, zorder=0, linewidth=0.5)
            axs[0].set_ylabel(fr"{METRIC} * {SCALE_FACTOR} [{METRIC_UNIT}]")

            # add manual legend
            legend_handles = format_legend_handles(cmaps["historical"], returnperiods)
            fig.legend(handles=legend_handles, title="Return Period\n(years)",
                        bbox_to_anchor=(0.9, 0.5), loc='center left',
                        handleheight=0.5, handlelength=1.1, labelspacing=0.05,
                        frameon=False)
                

            # save figure
            if SAVEFIG:
                outpath = figdir / f"{asset_geom}_{hazard}.png"
                fig.savefig(outpath, bbox_inches='tight')
                plt.close(fig)
                print(f"Wrote figure to {outpath}")
            else:
                fig.suptitle(f"{asset_geom} + {hazard}")
                fig

# %%

