
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
from matplotlib.patches import Patch

plt.rcParams.update({'font.size': 12, 'axes.titlesize': 14, 'axes.labelsize': 12})

HAZARDS   = [
    # "fluvial",
    "pluvial",
    "coastal",
    # "cyclone",
    # "landslide"
]
ASSET_GEOMS = [
    # "tza_roads_edges",
    "tza_railway_edges",
    "tza_roads_bridges_and_culverts_nodes",
]
METRIC = "damage"
range_str = "mean"

if METRIC == "cost":
    range_str = range_str + "_" + range_str

SUBREGION = [None, "kilimanjaro"][0]
WD = "../../results"
LOCAL_CRS = 32735
CMAP = ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4', '#91D1C2', '#DC0000', '#7E6148', '#B09C85']
SCALE_FACTOR = [1e-6, 1][1]

ASSET_TYPES = {
    "tza_railway_edges": "asset_type",
    "tza_roads_edges": "road_class",
    "tza_roads_bridges_and_culverts_nodes": "structure_type",
}

FRAMEWORKS = {
    "fluvial": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "pluvial": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "coastal": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
    "cyclone": {"lower": "historical", "centre": "ssp245", "upper": "ssp585"},
    "landslide": {"lower": "ssp126", "centre": "ssp245", "upper": "ssp585"},
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


def format_types(x:str, asset_geom):
    if asset_geom == "tza_railway_edges":
        gauge, structure, status = x.split("_")
        gauge = gauge.upper()
        return f"{gauge} {structure}\n({status})"
    elif asset_geom == "tza_roads_bridges_and_culverts_nodes":
        return x
    else:
        raise NotImplementedError(f"format_types not implemented for asset_geom: {asset_geom}")


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


def create_white_to_color_cmap(hex_color, name='custom', white="beige"):
    colors = ['beige', hex_color]
    cmap = mcolors.LinearSegmentedColormap.from_list(name, colors)#, gamma=.4)
    return cmap


def load_structure_types() -> pd.Series:
    """Process structure type strings to standardize them."""
    df = pd.read_csv("../bridges_and_culverts_types.csv")
    df["asset_class"] = df["asset_class"].str.lower()
    class_dict = df.set_index("asset_type")["asset_class"].to_dict()
    return class_dict

def process_rail(df:pd.DataFrame) -> pd.DataFrame:
    """Process railway asset types to standardize them."""
    disused = df["asset_type"].str.contains("disused", case=False, na=False)
    df = df[~disused].copy()
    return df

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
                asset[ASSET_TYPE] = asset["asset_type"].map(load_structure_types())

            if ASSET_GEOM.startswith("tza_railway"):
                asset = process_rail(asset)
            
            df = asset.copy()
            if METRIC == "damage":
                METRIC_UNIT = df["unit_type"].unique()[0] + "s"
            elif METRIC == "cost":
                METRIC_UNIT = "USD"

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

            if risk_gdf["value"].max() == 0:
                print(f"  No values for hazard: {HAZARD}, asset: {ASSET_GEOM}, "\
                      f"subregion: {SUBREGION if SUBREGION else 'national'}")
                continue

            risk_gdf = risk_gdf.set_index("id")
            risk_gdf = risk_gdf.join(df[ASSET_TYPE], how="inner")
            risk_gdf = risk_gdf.reset_index()

            negatives = risk_gdf[risk_gdf["value"] < 0].copy()
            import collections
            # print all the unique combinations of columns that have negative values
            if not negatives.empty:
                print(f"  Found {len(negatives)} negative values for hazard: {HAZARD}, asset: {ASSET_GEOM}, "\
                      f"subregion: {SUBREGION if SUBREGION else 'national'}")
                risk_gdf = risk_gdf[risk_gdf["value"] >= 0].copy()
            else:
                print(f"  ✅ No negative values for hazard: {HAZARD}, asset: {ASSET_GEOM}, "
                      f"metric: {METRIC}, subregion: {SUBREGION if SUBREGION else 'national'}")

            risk_grouped = risk_gdf.groupby(
                [ASSET_TYPE,"metric", "hazard", "epoch", "scenario", "rp", "range"]
            )[["value"]]


            totals = risk_grouped.sum().reset_index()
            EPOCHS = sorted(list(totals['epoch'].unique()), reverse=True) # biggest to smallest
            assets = sorted(list(totals[ASSET_TYPE].unique()))
            nassets = len(assets)
            max_values = totals["value"].max()

            plt.rcParams['font.size'] = 12 

            fig, axs = plt.subplots(1, nassets + 1,
                        figsize=((nassets * 2) + 1, 4),
                        sharey=True,
                        gridspec_kw={'wspace': 0, 'width_ratios': [1]*nassets + [0.5]})

            axs = axs.flatten()
            legend_ax = axs[-1]
            axs = axs[:-1]
            
            delta_patches = []

            # order big-to-small to show legend on final plot
            asset_totals = totals.groupby(ASSET_TYPE)[["value"]].sum().reset_index()
            asset_totals = asset_totals.sort_values(by="value", ascending=False)
            assets = asset_totals[ASSET_TYPE].tolist()

            for i, asset_type in (pbar := tqdm(enumerate(assets), total=len(assets))):
                pbar.set_description(f" Processing asset type: {asset_type}")
                ax = axs[i]
                totals_asset = totals[totals[ASSET_TYPE] == asset_type].copy()

                for i_EPOCH, EPOCH in (pbar:=tqdm(enumerate(EPOCHS), total=len(EPOCHS), leave=False)):
                    pbar.set_description(f"  Processing epoch: {EPOCH}")

                    totals_epoch = totals_asset[totals_asset['epoch'] == EPOCH].copy()

                    totals_epoch = totals_epoch[totals_epoch['range'] == range_str].copy()
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
                    cmap = create_white_to_color_cmap(
                        base_col, white="#ffffff"
                    )
                    colors = [cmap(i/len(returnperiods)) for i in range(len(returnperiods))]
                    palette_dict = dict(zip(returnperiods, colors))
                    legend_flag = (i_EPOCH == len(EPOCHS) - 1) & (i == len(assets) - 1)
                    delta_flag = (i_EPOCH < len(EPOCHS) - 1) & (i == 0)

                    n_patches_before = len(ax.patches)
                    n_lines_before = len(ax.lines)

                    sns.barplot(
                        x=totals_epoch[ASSET_TYPE].values,
                        y=totals_epoch["value"].values * SCALE_FACTOR,
                        ax=ax,
                        hue=totals_epoch['rp'].values,
                        palette=palette_dict,
                        edgecolor='black',
                        linewidth=0.5,
                        width=0.6,
                        legend=False,
                        errorbar=('pi', 100),  # full range (min to max)
                        capsize=0.0,#0.3,
                        err_kws={
                            'linewidth': 0.5,
                            'color': 'k',
                            'linestyle': 'solid'
                            }
                    )

                    if delta_flag: # add delta patches once
                        from matplotlib.patches import Patch
                        delta_patch = Patch(
                            facecolor=base_col,
                            edgecolor='black',
                            linewidth=0.5,
                            label=EPOCH
                        )
                        delta_patches.append(delta_patch)
                    
                    upper = FRAMEWORK["upper"]
                    lower = FRAMEWORK["lower"]
                    centre = FRAMEWORK["centre"]

                    bar_width = ax.patches[n_patches_before].get_width()
                    
                    shift_left = -(0.2 * bar_width)
                    offset = (0.2 * bar_width) + (0.01 * (len(EPOCHS) - i_EPOCH))

                    # for patch in ax.patches[n_patches_before:]:
                    #     patch.set_x(patch.get_x() + shift_left)

                    # for line in ax.lines[n_lines_before:]:
                    #     xdata = line.get_xdata()
                    #     line.set_xdata(xdata + offset)

                    # # Draw connectors after both bars and error bars are positioned
                    # for patch, line in zip(ax.patches[n_patches_before:], ax.lines[n_lines_before:]):
                    #     height = patch.get_height()
                    #     bar_right = patch.get_x() + patch.get_width()
                    #     error_bar_x = line.get_xdata()[0]  # where the error bar actually is
                    #     ax.plot([bar_right, error_bar_x], [height, height],
                    #             color='k',
                    #             linewidth=0.5,
                    #             linestyle='solid'
                    #     )

            formatter = FuncFormatter(clean_sci_formatter)

            for ax in axs:
                ax.tick_params(axis='y', which='major', labelsize=8)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.yaxis.set_ticks_position('left')
                ax.tick_params(axis='x', which='both', bottom=False, top=False)
                ax.tick_params(axis='y', which="both", direction="in")
                ax.set_xlim(-0.35, 0.35)
                labels = [format_types(label.get_text(), asset_geom=ASSET_GEOM) for label in ax.get_xticklabels()]
                ax.set_xticklabels(labels)
            for ax in axs[1:]:
                ax.spines['left'].set_visible(False)
                ax.tick_params(axis='y', left=False, labelleft=False)

            if SCALE_FACTOR != 1:
                axs[0].set_ylabel(fr"{METRIC} × {SCALE_FACTOR} ({METRIC_UNIT})")
            else:
                axs[0].set_ylabel(fr"{METRIC} ({METRIC_UNIT})")

            # legend 
            legend_ax.axis('off')
            leg1 = legend_ax.legend(
                handles=delta_patches,
                loc='lower left',
                frameon=False,
                title="Δfrom baseline",
                fontsize=8,
                title_fontsize=9,
                labelspacing=0.3
            )
            legend_ax.add_artist(leg1)
            rp_patches = [Patch(facecolor=palette_dict[rp], edgecolor='black', linewidth=0.5, label=str(rp)) 
                        for rp in returnperiods]
            leg2 = legend_ax.legend(handles=rp_patches, loc='upper left', frameon=False, title="return period",
                fontsize=8,
                title_fontsize=9,
                labelspacing=0.3)

            outfile = f"{outdir}/{ASSET_GEOM}_{HAZARD}_{METRIC}_{range_str}_{SUBREGION if SUBREGION else 'national'}_{EPOCH}.png"
            fig.savefig(outfile, dpi=300, bbox_inches='tight', transparent=True)
            print(f"  Saved figure to: {outfile}")
            plt.show()
            # break #! debugging
# %%
