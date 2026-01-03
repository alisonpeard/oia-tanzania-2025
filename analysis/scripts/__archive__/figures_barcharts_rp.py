"""
One figure for each hazard, asset, and epoch.
scenarios represented by error bars barcharts clustered by 
- asset_type (railways) ✅ 
- road_type (roads) ✅ 
- structure_type (bridges and culverts) 
- hub_type (airports, iww ports, maritime ports) [other scrtip]

"""
# %%
import os
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.colors as mcolors
from matplotlib.ticker import FuncFormatter

from utils import paths
from utils import plot
import utils.data as du

plt.rcParams.update({'font.size': 12, 'axes.titlesize': 14, 'axes.labelsize': 12})

dryrun = True

HAZARDS   = ["landslide", "fluvial", "pluvial", "coastal", "cyclone"]#, "landslide"]
ASSET_GEOMS = [
    # "tza_roads_edges",
    "tza_railway_edges",
    # "tza_roads_bridges_and_culverts_nodes",
    # "tza_airports_polygons", "tza_maritime_ports_polygons", "tza_iww_ports_polygons"
]

WD = paths.results_dir
METRIC = "damage"
range_str = "mean"
SUBREGION = [None, "kilimanjaro"][0]
LOCAL_CRS = 32735
SCALE_FACTOR = [1e-6, 1][1]


FRAMEWORKS = {
    "fluvial": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "pluvial": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "coastal": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "cyclone": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "landslide": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
}


if __name__ == "__main__":
    outdir = "../figures/asset_type_profiles"
    os.makedirs(outdir, exist_ok=True)

    for HAZARD in HAZARDS:
        FRAMEWORK = FRAMEWORKS[HAZARD]
        for ASSET_GEOM in ASSET_GEOMS:
            # try:
            print(f"Processing hazard: {HAZARD}, asset: {ASSET_GEOM}, subregion: {SUBREGION if SUBREGION else 'national'}")

            asset_dir = os.path.join(WD, "risk", ASSET_GEOM, HAZARD)
            asset = du.prepare_asset(
                asset_geom=ASSET_GEOM,
                asset_dir=asset_dir,
                subregion=SUBREGION,
                verbose=True
            )   
            asset = du.prepare_hazard_data(asset, HAZARD)
            print(asset["asset_type"].value_counts())
            units = asset["unit_type"].unique()[0]

            # asset = asset.fillna(0.0)
            riskcols = [col for col in asset.columns if col.startswith(METRIC)]
            grouped = asset.groupby("asset_type")[riskcols].sum().T
            risktups = grouped.reset_index()["index"].apply(du.extract_hazard_info)
            riskinfo = pd.DataFrame(
                risktups.tolist(),
                columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
            )
            risk = grouped.reset_index(drop=True).join(riskinfo)
            risk = risk.melt(
                id_vars=["metric", "hazard", "epoch", "scenario", "rp", "range"],
                var_name="asset_type"
            )

            epochs = sorted(list(risk['epoch'].unique()), reverse=True)

            for i_EPOCH, EPOCH in enumerate(epochs):
                print(f"  Epoch: {EPOCH}")

                totals_epoch = risk[risk['epoch'] == EPOCH].copy()

                totals_epoch = totals_epoch[totals_epoch['range'] == range_str].copy()
                totals_epoch = totals_epoch.drop(columns=["metric", "hazard", "epoch"])


                totals_epoch["rp"] = totals_epoch["rp"].astype(int)
                totals_epoch = totals_epoch.sort_values(by=["asset_type", "rp"])

                average_values = totals_epoch[totals_epoch["value"] > 0]["value"].mean()
                min_values = 0
                max_values = totals_epoch["value"].max()
                assets = totals_epoch["asset_type"].unique()

                ntypes = len(totals_epoch["asset_type"].unique())

                fig, axs = plt.subplots(1, ntypes,
                                        figsize=(ntypes * 3.5, 4),
                                        sharey=False,
                                        gridspec_kw={'wspace': 0})
                
                axs = [axs] if ntypes == 1 else axs.flatten()

                for i, asset_type in enumerate(assets):
                    ax = axs[i]
                    data = totals_epoch[totals_epoch["asset_type"] == asset_type].copy()

                    if data.empty:
                        continue

                    returnperiods = sorted(list(data['rp'].unique()), key=lambda x: int(x))
                    cmap = plt.get_cmap("PuBu") # YlGnBu
                    colors = [cmap(i/len(returnperiods)) for i in range(len(returnperiods))]
                    palette_dict = dict(zip(returnperiods, colors))

                    sns.barplot(
                        x=data["asset_type"].values,
                        y=data["value"].values * SCALE_FACTOR,
                        ax=ax,
                        hue=data['rp'].values,
                        palette=palette_dict,
                        edgecolor='black',
                        linewidth=0.5,
                        width=0.5,
                        legend=i == 0
                    )
                    if i == 0:
                        sns.move_legend(ax, "upper left", title="return period", frameon=False)
                    ax.set_xlabel(asset_type, fontweight='bold', x=0.5)

                    # Manually add error bars to each bar
                    if data["scenario"].nunique() > 1:
                        import numpy as np

                        def create_bounds(df, framework:dict=FRAMEWORK):
                            lower_scenario = framework["lower"]
                            mean_scenario = framework["centre"]
                            upper_scenario = framework["upper"]
                            lower = df[df['scenario'] == lower_scenario]['value'].values[0]
                            mean = df[df['scenario'] == mean_scenario]['value'].values[0]
                            upper = df[df['scenario'] == upper_scenario]['value'].values[0]
                            return pd.Series({
                                "value": mean,
                                "lower": lower,
                                "upper": upper
                            })
                        data = data.groupby([
                            "asset_type", "rp", "range"]
                        ).apply(create_bounds).reset_index()

                        lower_err = ((data["value"] - data["lower"]).values * SCALE_FACTOR).clip(min=0)
                        upper_err = ((data["upper"] - data["value"]).values * SCALE_FACTOR).clip(min=0)
                        yerr = np.array([lower_err, upper_err])
                        bars = ax.patches
                        for bar, low, up in zip(bars, lower_err, upper_err):
                            x = bar.get_x() + bar.get_width() / 2
                            y = bar.get_height()
                            ax.errorbar(x, y, yerr=[[low], [up]], 
                                        fmt='none', c='black', capsize=3, capthick=1, linewidth=1)
                
                formatter = FuncFormatter(plot.clean_sci_formatter)

                for ax in axs:
                    # ax.yaxis.set_major_formatter(formatter)
                    ax.tick_params(axis='y', which='major', labelsize=8)
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    ax.yaxis.set_ticks_position('left')
                    ax.set_ylim(bottom=1e-6, top=max_values * SCALE_FACTOR * 1.1)
                    ax.set_xlabel("")
                    ax.tick_params(axis='x', which='both', bottom=False, top=False)
                    ax.tick_params(axis='y', which="both", direction="in")
                    ax.set_xlim(-0.35, 0.35)
                for ax in axs[1:]:
                    ax.spines['left'].set_visible(False)
                    ax.set_yticks([])

                axs[0].set_ylabel(fr"{METRIC} * {SCALE_FACTOR} [{units}]")

                # title is hazard, asset_geom, subregion, range_str
                fig.suptitle(
                    f"hazard: {HAZARD} - asset: {ASSET_GEOM} - epoch : {EPOCH} - "
                    f"region: {SUBREGION if SUBREGION else 'national'} - range: {range_str}",
                    fontsize=16
                )

                outfile = f"{outdir}/{ASSET_GEOM}_{HAZARD}_{METRIC}_{range_str}_{SUBREGION if SUBREGION else 'national'}_{EPOCH}.png"
                fig.savefig(outfile, dpi=300, bbox_inches='tight', transparent=True)
                print(f"  Saved figure to: {outfile}")
                plt.show()


                if dryrun: break
            if dryrun: break
        if dryrun: break

# %%