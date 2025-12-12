
# %%
import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.colors as mcolors

HAZARDS   = ["pluvial", "fluvial", "coastal", "cyclone", "landslide"]
ASSET_GEOMS = [
    "tza_roads_edges", "tza_railway_edges", "tza_roads_bridges_and_culverts_nodes",
    "tza_airports_polygons", "tza_maritime_ports_polygons", "tza_iww_ports_polygons"
]
METRIC = "cost"
METRIC_UNIT = "$"
range_str = "mean_mean"
SUBREGION = [None, "kilimanjaro"][0]
SCENARIO = "ssp245"
EPOCH = "2050"
WD = "../../results"
LOCAL_CRS = 32735
CMAP = npg = ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4', '#91D1C2', '#DC0000', '#7E6148', '#B09C85']
SCALE_FACTOR = 1e-3


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


if __name__ == "__main__":
    outdir = "../figures/admn1"
    os.makedirs(outdir, exist_ok=True)

    # for HAZARD in HAZARDS:
    #     for ASSET_GEOM in ASSET_GEOMS:

    HAZARD = "pluvial"
    ASSET_GEOM = "tza_railway_edges"
    print(f"Processing hazard: {HAZARD}, asset: {ASSET_GEOM}, subregion: {SUBREGION if SUBREGION else 'national'}")

    if SUBREGION:
        asset_path = os.path.join(
            WD, "risk", ASSET_GEOM, HAZARD, SUBREGION, "annual.parquet"
        )
        asset = pd.read_parquet(asset_path)
        asset["subregion"] = SUBREGION
    else:
        base_dir = os.path.join(WD, "risk", ASSET_GEOM, HAZARD)
        subregions = os.listdir(base_dir)
        asset_files = [os.path.join(base_dir, subregion, "annual.parquet") for subregion in
                        subregions if os.path.isdir(os.path.join(base_dir, subregion))]
        asset_dfs = []
        for f in asset_files:
            df = pd.read_parquet(f).reset_index()
            df['subregion'] = os.path.basename(os.path.dirname(f))
            asset_dfs.append(df)

        asset = pd.concat(asset_dfs, axis=0)
        # asset = asset.groupby("id").mean().reset_index() # need to do later
    df = asset.copy()
    df.head()
    # %%
    SUBGROUP = "asset_type"
    df = df[df["metric"] == METRIC].copy()
    df = df[df["range"] == range_str].copy()
    df = df[df["scenario"] == SCENARIO].copy()
    df = df[df["epoch"] == EPOCH].copy()
    grouped = df.groupby(["subregion", SUBGROUP])["expected"].sum().reset_index()
    grouped["expected"] = grouped["expected"] * SCALE_FACTOR
    pivoted = grouped.pivot(index="subregion", columns=SUBGROUP, values="expected").fillna(0)


    # %%
    import numpy as np
    sorting = np.argsort(pivoted.sum(axis=1).values)
    # %%
    fig, ax = plt.subplots(figsize=(8, 8))
    pivoted.iloc[sorting, ].plot.barh(
        stacked=True,
        color=CMAP,
        width=0.7,
        edgecolor='#666666',
        linewidth=0.5,
        ax=ax,
        legend=True
    )

        # make color list

    ax.set_ylabel("")
    ax.set_xlabel(fr"Expected annual {METRIC} ({SCALE_FACTOR}*{METRIC_UNIT})", fontsize=12)
    ax.set_title(f"{EPOCH} - {SCENARIO} - {ASSET_GEOM} - {HAZARD}", fontsize=12)
    def ylabelformatting(x):
        x = x.replace("_", " ").title()
        return x
    
    yticklabels = [ylabelformatting(label.get_text()) for label in ax.get_yticklabels()]
    ax.set_yticklabels(yticklabels, fontsize=10)
    plt.tight_layout()

    legend = ax.legend(loc='lower right')
    texts  = legend.get_texts()

    def format_legend_texts(texts):
        splits = texts.split('_')
        a = splits[0].upper()
        b = " ".join(splits[1:]).capitalize()
        return f"{a} {b}"
    
    for text in texts:
        original_text = text.get_text()
        formatted_text = format_legend_texts(original_text)
        text.set_text(formatted_text)
    
# %%


"""
Reference code:
"""

def admin1_roadtype(provider, meancols, mincols, maxcols,
                    HAZARD, EPOCH, SCENARIO, RP,
                    SUBGROUP="asset_type"):
    gdf = provider.gdf.copy()
    # filter to scenario
    meancols = plot.subset_columns(meancols, hazards=HAZARD, scenarios=SCENARIO, epochs=EPOCH, rps=RP)
    mincols  = plot.subset_columns(mincols,  hazards=HAZARD, scenarios=SCENARIO, epochs=EPOCH, rps=RP)
    maxcols  = plot.subset_columns(maxcols,  hazards=HAZARD, scenarios=SCENARIO, epochs=EPOCH, rps=RP)
    assert len(meancols) == len(mincols) == len(maxcols), \
        f"Number of columns do not match: {len(meancols)} != {len(mincols)} != {len(maxcols)}"

    # group by state and get totals
    means = gdf.groupby(["state", SUBGROUP])[meancols].apply('sum')
    means[meancols] = means[meancols] / 1e6 # convert USD to million USD
    # means = means.join(admin1)
    means

    mins = gdf.groupby(["state", SUBGROUP])[mincols].agg('sum')
    mins[mincols] = mins[mincols] / 1e6

    maxs = gdf.groupby(["state", SUBGROUP])[maxcols].agg('sum')
    maxs[maxcols] = maxs[maxcols] / 1e6

    # rename columns so names match
    # RPS = [f"{core.format_rp(RP)}-year" for RP in RPS]
    RPS = [f"{provider.format_rp(RP)}-year"]

    means.columns = RPS #+ ['geometry']
    mins.columns = RPS
    maxs.columns = RPS

    upper = maxs - means[RPS]
    lower = means[RPS] - mins
    upper = upper.T.values
    lower = lower.T.values
    yerr = np.stack([lower, upper], axis=1)
    yerr.shape

    # settings
    # subset means to what we want to plot
    means_rp = means[[f'{provider.format_rp(RP)}-year']].reset_index()
    if means_rp[SUBGROUP].dtype == bool:
        means_rp[SUBGROUP] = means_rp[SUBGROUP].replace({True: SUBGROUP.capitalize(), False: f'Not {SUBGROUP}'})
    means_rp = means_rp.pivot(index='state', columns=SUBGROUP, values=f"{core.format_rp(RP)}-year").dropna(axis=1, how="all").replace(np.nan, 0)



    return fig, ax