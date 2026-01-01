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
from glob import glob
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
    "fluvial",
    # "pluvial",
    # "coastal",
    # "cyclone",
    # "landslide"
]
ASSET_GEOMS = [
    # "tza_roads_edges",
    # "tza_railway_edges",
    "tza_roads_bridges_and_culverts_nodes"
]
METRIC = "cost"
RANGE = "mean"
RANGE = RANGE + "_" + RANGE if METRIC == "cost" else RANGE
SUBREGION = [None, "kilimanjaro"][0]
WD = "../../results"
SCALE_FACTOR = 1e-6 if METRIC == "cost" else 1

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

# helper functions
def clean_sci_formatter(x, pos):
    """Format with scientific notation but without leading zeros in exponent."""
    if x == 0:
        return '0'
    s = f'{x:.3g}'
    if 'e' in s:
        base, exp = s.split('e')
        exp = str(int(exp))
        return f'{base}e{exp}'
    return s


def format_asset_type(x:str, asset_geom):
    if asset_geom == "tza_railway_edges":
        gauge, structure, status = x.split("_")
        gauge = gauge.upper()
        return f"{gauge} {structure}\n({status})"
    elif asset_geom == "tza_roads_bridges_and_culverts_nodes":
        return x.title()
    elif asset_geom == "tza_roads_edges":
        return x.title()
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


def process_railway(df:pd.DataFrame, *args) -> pd.DataFrame:
    # process railway asset types to standardize them.
    disused = df["asset_type"].str.contains("disused", case=False, na=False)
    df = df[~disused].copy()
    return df


def process_bridges_and_culverts(df:pd.DataFrame, asset_type_col:str) -> pd.DataFrame:
    # process structure type strings to standardize them.
    def format(x:str) -> str:
        x = x.replace(" ", "\n")
        return x.title()
    ref = pd.read_csv("../bridges_and_culverts_types.csv")
    ref["asset_class"] = ref["asset_class"].str.lower()
    class_dict = ref.set_index("asset_type")["asset_class"].to_dict()
    df[asset_type_col] = df["asset_type"].map(class_dict)
    df[asset_type_col] = df[asset_type_col].apply(format)
    return df


def process_roads(df:pd.DataFrame, asset_type_col:str) -> pd.DataFrame:
    road_path = os.path.join(WD, "assets", ASSET_GEOM)
    if SUBREGION:
        path = os.path.join(road_path, SUBREGION, f"{SUBREGION}.geoparquet")
        roads = gpd.read_parquet(path)
    else:
        road_files = glob(os.path.join(road_path, "*.geoparquet"))
        road_dfs = [gpd.read_parquet(f).reset_index() for f in road_files]
        roads = pd.concat(road_dfs, axis=0)
        roads = roads.copy() # de-fragment
    
    roads[asset_type_col] = roads[asset_type_col].str.lower()
    roads = roads.set_index("id")
    df = df.set_index("id")
    df = df.join(roads[[asset_type_col]], how="left")
    return df.reset_index()


if __name__ == "__main__":

    outdir = "../figures/asset_type_profiles"
    os.makedirs(outdir, exist_ok=True)

    for HAZARD in HAZARDS:
        FRAMEWORK = FRAMEWORKS[HAZARD]
        for ASSET_GEOM in ASSET_GEOMS:

            ASSET_TYPE = ASSET_TYPES[ASSET_GEOM]

            print(f"Plotting hazard: {HAZARD}, asset: {ASSET_GEOM}, subregion: {SUBREGION if SUBREGION else 'national'}")
            base_dir = os.path.join(WD, "risk", ASSET_GEOM, HAZARD)

            if SUBREGION:
                asset_path = os.path.join(base_dir, SUBREGION, "profile.geoparquet")
                asset = gpd.read_parquet(asset_path)
            else:
                asset_files = glob(os.path.join(base_dir, "*", "profile.geoparquet"))
                asset_dfs = [gpd.read_parquet(f).reset_index() for f in asset_files]
                asset = pd.concat(asset_dfs, axis=0, ignore_index=True)
                asset = asset.copy() # de-fragment

            if ASSET_GEOM.startswith("tza_roads_bridges_and_culverts"):
                asset = process_bridges_and_culverts(asset, ASSET_TYPE)
                print(f" Asset types after processing: {asset[ASSET_TYPE].unique()}")
            elif ASSET_GEOM.startswith("tza_roads"):
                asset = process_roads(asset, ASSET_TYPE)
                print(f" Asset types after processing: {asset[ASSET_TYPE].unique()}")
            elif ASSET_GEOM.startswith("tza_railway"):
                asset = process_railway(asset, ASSET_TYPE)
                print(f" Asset types after processing: {asset[ASSET_TYPE].unique()}")
            else:
                raise NotImplementedError(f"Processing not implemented for asset geom: {ASSET_GEOM}")
            
            df = asset.copy()
            if METRIC == "damage":
                METRIC_UNIT = df["unit_type"].unique()[0]
            elif METRIC == "cost":
                METRIC_UNIT = "USD"

            # prepare dataframe for barplot
            # ! start of old
            # risk_cols = [col for col in df.columns if col.startswith(METRIC)]
            # risk_gdf = df[risk_cols].copy().T
            # risk_tuples = risk_gdf.reset_index()["index"].apply(extract_hazard_info)
            # risk_info = pd.DataFrame(
            #     risk_tuples.tolist(),
            #     columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
            # )
            # risk_gdf = risk_gdf.reset_index(drop=True).join(risk_info)
            # print("  Melting...")
            # risk_gdf = risk_gdf.melt(
            #     id_vars=["metric", "hazard", "epoch", "scenario", "rp", "range"],
            #     var_name="id"
            # )
            # ! end of old

            # ! start of new
            risk_cols = [col for col in df.columns if col.startswith(METRIC)]
            df_agg = df.groupby(ASSET_TYPE)[risk_cols].sum().reset_index()
            risk_gdf = df_agg.melt(
                id_vars=[ASSET_TYPE],
                var_name="risk_col",
                value_name="value"
            )
            risk_tuples = risk_gdf["risk_col"].apply(extract_hazard_info)
            risk_info = pd.DataFrame(
                risk_tuples.tolist(),
                columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
            )
            risk_gdf = risk_gdf.join(risk_info).drop(columns=["risk_col"])
            # ! end of new

            print(f"  Rows in df: {len(df)}")
            print(f"  Risk columns: {len(risk_cols)}")
            print(f"  Rows after melt: {len(risk_gdf)}")

            if risk_gdf["value"].max() == 0:
                print(f"  No values for hazard: {HAZARD}, asset: {ASSET_GEOM}, "\
                      f"subregion: {SUBREGION if SUBREGION else 'national'}")
                continue

            # ! start of old
            # risk_gdf = risk_gdf.set_index("id")
            # risk_gdf = risk_gdf.join(df[ASSET_TYPE], how="inner")
            # risk_gdf = risk_gdf.reset_index()
            # ! end of old

            # print all the unique combinations of columns that have negative values
            negatives = risk_gdf[risk_gdf["value"] < 0].copy()
            if not negatives.empty:
                print(f"  Found {len(negatives)} negative values for hazard: {HAZARD}, asset: {ASSET_GEOM}, "\
                      f"subregion: {SUBREGION if SUBREGION else 'national'}")
                risk_gdf = risk_gdf[risk_gdf["value"] >= 0].copy()
            else:
                print(f"  ✅ No negative values for hazard: {HAZARD}, asset: {ASSET_GEOM}, "
                      f"metric: {METRIC}, subregion: {SUBREGION if SUBREGION else 'national'}")

            # ! start of old
            # group_cols = [ASSET_TYPE, "metric", "hazard", "epoch", "scenario", "rp", "range"]
            # risk_grouped = risk_gdf.groupby(group_cols)[["value"]]
            # totals = risk_grouped.sum().reset_index()
            # ! end of old

            # ! start of new
            totals = risk_gdf
            # ! end of new

            # After the new code produces totals
            print(f"totals shape: {totals.shape}")
            print(totals[totals['range'] == RANGE].groupby([ASSET_TYPE, 'epoch', 'rp'])['value'].sum().head(20))

            EPOCHS = sorted(list(totals['epoch'].unique()), reverse=True) # biggest to smallest
            assets = sorted(list(totals[ASSET_TYPE].unique()))
            nassets = len(assets)
            max_values = totals["value"].max()

            fig, axs = plt.subplots(
                1, nassets + 1,
                figsize=((nassets * 2) + 1, 4),
                sharey=True,
                gridspec_kw={
                    'wspace': 0, 'width_ratios': [1]*nassets + [0.5]
                }
            )

            axs = axs.flatten()
            legend_ax = axs[-1]
            axs = axs[:-1]
            epoch_patches = []

            max_asset_value = SCALE_FACTOR * totals["value"].max()
            print(f"   Max {METRIC} for asset: {max_asset_value:.2f} {SCALE_FACTOR} {METRIC_UNIT}")

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
                    cmap = create_white_to_color_cmap(
                        base_col, white="#ffffff"
                    )
                    colors = [cmap(i/len(returnperiods)) for i in range(len(returnperiods))]
                    palette_dict = dict(zip(returnperiods, colors))
                    legend_flag = (i_EPOCH == len(EPOCHS) - 1) & (i == len(assets) - 1)
                    epoch_flag = (i_EPOCH < len(EPOCHS) - 1) & (i == 0)

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
                        errorbar=('pi', 100),
                        capsize=0.0,
                        err_kws={
                            'linewidth': 0.5,
                            'color': 'k',
                            'linestyle': 'dashed'
                        }
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
                    
                    upper = FRAMEWORK["upper"]
                    lower = FRAMEWORK["lower"]
                    centre = FRAMEWORK["centre"]

            formatter = FuncFormatter(clean_sci_formatter)

            for ax in axs:
                ax.tick_params(axis='y', which='major', labelsize=8)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.yaxis.set_ticks_position('left')
                ax.tick_params(axis='x', which='both', bottom=False, top=False)
                ax.tick_params(axis='y', which="both", direction="in")
                ax.set_xlim(-0.35, 0.35)
                labels = [format_asset_type(label.get_text(), asset_geom=ASSET_GEOM) for label in ax.get_xticklabels()]
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
                handles=epoch_patches,
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

            outfile = f"{outdir}/{ASSET_GEOM}_{HAZARD}_{METRIC}_{RANGE}_{SUBREGION if SUBREGION else 'national'}_{EPOCH}.png"
            fig.savefig(outfile, dpi=300, bbox_inches='tight', transparent=True)
            print(f"  Saved figure to: {outfile}")
            plt.show()

            print("Dry run. Breaking.")
            break #! debugging
        break

# %%
