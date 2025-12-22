
"""
One figure for each hazard, asset, and epoch.
scenarios represented by error bars
barcharts clustered by 
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

plt.rcParams.update({'font.size': 12, 'axes.titlesize': 14, 'axes.labelsize': 12})

HAZARDS   = ["fluvial", "pluvial", "coastal", "cyclone"]#, "landslide"]
ASSET_GEOMS = [
    # "tza_roads_edges", "tza_railway_edges",
    "tza_roads_bridges_and_culverts_nodes",
    # "tza_airports_polygons", "tza_maritime_ports_polygons", "tza_iww_ports_polygons"
]
METRIC = "damage"
range_str = "mean"
SUBREGION = [None, "kilimanjaro"][0]
WD = "../../results"
LOCAL_CRS = 32735
CMAP = npg = ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4', '#91D1C2', '#DC0000', '#7E6148', '#B09C85']
SCALE_FACTOR = [1e-6, 1][1]

ASSET_TYPES = {
    "tza_railway_edges": "asset_type",
    "tza_roads_edges": "road_class",
    "tza_roads_bridges_and_culverts_nodes": "structure_type"
}

FRAMEWORKS = {
    "fluvial": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "pluvial": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "coastal": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "cyclone": {"lower": "historical", "centre": "ssp245", "upper": "ssp585"},
}


def clean_sci_formatter(x, pos):
    """Format with scientific notation but without leading zeros in exponent."""
    if x == 0:
        return '0'
    # Format with scientific notation
    s = f'{x:.3g}'
    # If it contains 'e', clean up the exponent
    if 'e' in s:
        base, exp = s.split('e')
        exp = str(int(exp))  # Remove leading zeros/plus signs
        return f'{base}e{exp}'
    return s

def extract_hazard_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract hazard, epoch, scenario, and return period from hazard column name."""
    prefix, parts = hazcol.split("-")
    parts = parts.split("_")
    hazard = parts[0]
    epoch = parts[1]
    scenario = parts[2]
    rp = str(int(parts[3].replace("rp", "")))
    if len(parts) > 4:
        stat = "_".join(parts[4:])
    else:
        stat = pd.NA
    return prefix, hazard, epoch, scenario, rp, stat


def create_white_to_color_cmap(hex_color, name='custom_cmap'):
    colors = ['beige', hex_color]
    cmap = mcolors.LinearSegmentedColormap.from_list(name, colors)#, gamma=.4)
    return cmap


def process_structure_type(structure_type: str) -> str:
    """Process structure type strings to standardize them."""
    print(structure_type)
    structure_type = structure_type.lower()
    if "bridge" in structure_type:
        output_type = "bridge"
    elif "culvert" in structure_type:
        output_type = "culvert"
    else:
        print(f"  Unrecognized structure type: {structure_type}, assigning to 'other'")
        output_type = "other"
    return output_type

if __name__ == "__main__":
    outdir = "../figures/asset_type_profiles"
    os.makedirs(outdir, exist_ok=True)

    for HAZARD in HAZARDS:
        FRAMEWORK = FRAMEWORKS[HAZARD]
        for ASSET_GEOM in ASSET_GEOMS:
            ASSET_TYPE = ASSET_TYPES[ASSET_GEOM]

            # try:
            print(f"Processing hazard: {HAZARD}, asset: {ASSET_GEOM}, subregion: {SUBREGION if SUBREGION else 'national'}")

            if SUBREGION:
                asset_path = os.path.join(
                    WD, "risk", ASSET_GEOM, HAZARD, SUBREGION, "profile.geoparquet"
                )
                asset = gpd.read_parquet(asset_path)
            else:
                base_dir = os.path.join(WD, "risk", ASSET_GEOM, HAZARD)
                subregions = os.listdir(base_dir)
                asset_files = [os.path.join(base_dir, subregion, "profile.geoparquet") for subregion in
                                tqdm(subregions) if os.path.isdir(os.path.join(base_dir, subregion))]
                asset_dfs = [gpd.read_parquet(f).reset_index() for f in asset_files]
                asset = pd.concat(asset_dfs, axis=0)
                # asset = asset.groupby("id").mean().reset_index() # need to do later

            if ASSET_GEOM.startswith("tza_roads"):
                # load original asset file
                road_path = os.path.join(
                    WD, "assets", ASSET_GEOM
                )
                if SUBREGION:
                    roads = gpd.read_parquet(
                        os.path.join(road_path, f"{SUBREGION}.geoparquet")
                    )
                else:
                    road_files = os.listdir(road_path)
                    road_files = [f for f in road_files if not f.startswith(".")]
                    road_files = [os.path.join(road_path, f) for f in road_files]
                    road_dfs = [gpd.read_parquet(f).reset_index() for f in road_files]
                    roads = pd.concat(road_dfs, axis=0)
                roads[ASSET_TYPE] = roads[ASSET_TYPE].str.lower()
                roads = roads.set_index("id")
            
                asset = asset.set_index("id")
                asset = asset.join(roads[[ASSET_TYPE]], how="left")

            
            if ASSET_GEOM.startswith("tza_roads_bridges_and_culverts"):
                asset["old_type"] = asset[ASSET_TYPE].copy()
                asset[ASSET_TYPE] = asset[ASSET_TYPE].apply(process_structure_type)

            df = asset.copy()
            METRIC_UNIT = df["unit_type"].unique()[0]

            # barplot_scenarios(asset)
            risk_cols = [col for col in df.columns if col.startswith(METRIC)]
            risk_gdf = df[risk_cols].copy().T
            risk_tuples = risk_gdf.reset_index()["index"].apply(extract_hazard_info)
            risk_info = pd.DataFrame(
                risk_tuples.tolist(),
                columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
            )
            risk_gdf = risk_gdf.reset_index(drop=True).join(risk_info)
            risk_gdf = risk_gdf.melt(
                id_vars=["metric", "hazard", "epoch", "scenario", "rp", "range"],
                var_name="id"
                )

            risk_gdf["value"] = risk_gdf["value"].fillna(0.0)
            if risk_gdf["value"].max() == 0:
                print(f"  No values for hazard: {HAZARD}, asset: {ASSET_GEOM}, subregion: {SUBREGION if SUBREGION else 'national'}")
                continue


            risk_gdf = risk_gdf.set_index("id")
            risk_gdf = risk_gdf.join(df[ASSET_TYPE], how="inner")
            risk_gdf = risk_gdf.reset_index()

            risk_grouped = risk_gdf.groupby(
                [ASSET_TYPE,"metric", "hazard", "epoch", "scenario", "rp", "range"]
            )[["value"]]

            totals = risk_grouped.sum().reset_index()

            EPOCHS = sorted(list(totals['epoch'].unique()))

            for i_EPOCH, EPOCH in enumerate(EPOCHS):
                print(f"  Epoch: {EPOCH}")

                totals_epoch = totals[totals['epoch'] == EPOCH].copy()

                totals_epoch = totals_epoch[totals_epoch['range'] == range_str].copy()
                totals_epoch = totals_epoch.drop(columns=["metric", "hazard", "epoch"])


                totals_epoch["rp"] = totals_epoch["rp"].astype(int)
                totals_epoch = totals_epoch.sort_values(by=[ASSET_TYPE, "rp"])

                # separate out assets with small values
                average_values = totals_epoch[totals_epoch["value"] > 0]["value"].mean()
                min_values = 0
                max_values = totals_epoch["value"].max()
                asset_means = totals_epoch.groupby(ASSET_TYPE)["value"].mean()
                threshold = 0.1 * average_values
                main_assets = sorted([at for at in asset_means.index if asset_means[at] >= threshold])
                small_assets = sorted([at for at in asset_means.index if asset_means[at] < threshold])
                asset_order = main_assets + small_assets
                # asset_order = [
                #     at for at in asset_order 
                #     if totals_epoch[totals_epoch[ASSET_TYPE] == at]["value"].sum() > 0
                # ]

                ntypes = len(asset_order)
                n_main = len(main_assets)

                ntypes = len(totals_epoch[ASSET_TYPE].unique())

                fig, axs = plt.subplots(1, ntypes,
                                        figsize=(ntypes * 3.5, 4),
                                        sharey=False,
                                        gridspec_kw={'wspace': 0})
                
                axs = [axs] if ntypes == 1 else axs.flatten()

                for i, asset_type in enumerate(asset_order):
                    ax = axs[i]
                    data = totals_epoch[totals_epoch[ASSET_TYPE] == asset_type].copy()

                    if data.empty:
                        continue

                    returnperiods = sorted(list(data['rp'].unique()), key=lambda x: int(x))
                    cmap = create_white_to_color_cmap(CMAP[i_EPOCH])
                    cmap = plt.get_cmap("OrRd") # YlGnBu
                    colors = [cmap(i/len(returnperiods)) for i in range(len(returnperiods))]
                    palette_dict = dict(zip(returnperiods, colors))

                    sns.barplot(
                        x=data[ASSET_TYPE].values,
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
                            ASSET_TYPE, "rp", "range"]
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
                
                formatter = FuncFormatter(clean_sci_formatter)

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
                for ax in axs[1:n_main]:
                    ax.spines['left'].set_visible(False)
                    ax.set_yticks([])

                axs[0].set_ylabel(fr"{METRIC} * {SCALE_FACTOR} [{METRIC_UNIT}]")

                if small_assets:
                    for i, asset_type in zip(range(n_main, ntypes), small_assets):
                        small_max = totals_epoch[totals_epoch[ASSET_TYPE] == asset_type]["value"].max() * SCALE_FACTOR
                        axs[i].set_ylim(bottom=0, top=small_max * 1.1)
                        axs[i].spines['left'].set_visible(True)
                        axs[i].yaxis.set_ticks_position('left')
                        axs[i].tick_params(axis='y', which='major', labelsize=8, direction="in")
                        # axs[i].yaxis.set_major_formatter(formatter)

                # title is hazard, asset_geom, subregion, range_str
                fig.suptitle(
                    f"hazard: {HAZARD} - asset: {ASSET_GEOM} ({ASSET_TYPE}) - epoch : {EPOCH} - "
                    f"region: {SUBREGION if SUBREGION else 'national'} - range: {range_str}",
                    fontsize=16
                )

                outfile = f"{outdir}/{ASSET_GEOM}_{HAZARD}_{METRIC}_{range_str}_{SUBREGION if SUBREGION else 'national'}_{EPOCH}.png"
                fig.savefig(outfile, dpi=300, bbox_inches='tight', transparent=True)
                print(f"  Saved figure to: {outfile}")
                plt.show()
# %%