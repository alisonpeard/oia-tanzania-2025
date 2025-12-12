
"""
One figure for each hazard, asset, and epoch.
scenarios represented by error bars
barcharts clustered by 
- asset_type
- road_type
- port_type

To do 
- more flexible scenario handling
- road types
- port types
- same colour and one legend
"""
# %%
import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.colors as mcolors
from matplotlib.ticker import FuncFormatter


HAZARDS   = ["fluvial", "pluvial", "coastal", "cyclone", "landslide"]
ASSET_GEOMS = [
    "tza_railway_edges", "tza_roads_edges", "tza_roads_bridges_and_culverts_nodes",
    "tza_airports_polygons", "tza_maritime_ports_polygons", "tza_iww_ports_polygons"
]
METRIC = "damage"
range_str = "mean"
SUBREGION = [None, "kilimanjaro"][0]
WD = "../../results"
LOCAL_CRS = 32735
CMAP = npg = ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4', '#91D1C2', '#DC0000', '#7E6148', '#B09C85']
SCALE_FACTOR = [1e-6, 1][1]


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


if __name__ == "__main__":
    outdir = "../figures/asset_type_profiles"
    os.makedirs(outdir, exist_ok=True)

    for HAZARD in HAZARDS[:1]:
        for ASSET_GEOM in ASSET_GEOMS[:1]:

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
                                subregions if os.path.isdir(os.path.join(base_dir, subregion))]
                asset_dfs = [gpd.read_parquet(f).reset_index() for f in asset_files]
                asset = pd.concat(asset_dfs, axis=0)
                # asset = asset.groupby("id").mean().reset_index() # need to do later

            df = asset.copy()
            METRIC_UNIT = df["unit_type"].unique()[0]

            # %% 
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


            risk_gdf = risk_gdf.set_index("id")
            # inner join with df["asset_type"]
            risk_gdf = risk_gdf.join(df["asset_type"], how="inner")
            risk_gdf = risk_gdf.reset_index()

            risk_grouped = risk_gdf.groupby(
                ["asset_type","metric", "hazard", "epoch", "scenario", "rp", "range"]
            )[["value"]]

            totals = risk_grouped.sum().reset_index()

            # %%
            EPOCHS = sorted(list(totals['epoch'].unique()))

            for i_EPOCH, EPOCH in enumerate(EPOCHS):
                print(f"  Epoch: {EPOCH}")

                totals_epoch = totals[totals['epoch'] == EPOCH].copy()

                totals_epoch = totals_epoch[totals_epoch['range'] == range_str].copy()
                totals_epoch = totals_epoch.drop(columns=["metric", "hazard", "epoch"])


                totals_epoch["rp"] = totals_epoch["rp"].astype(int)
                totals_epoch = totals_epoch.sort_values(by=["asset_type", "rp"])

                ntypes = len(totals_epoch['asset_type'].unique())

                fig, axs = plt.subplots(1, ntypes,
                                        figsize=(ntypes * 4, 4),
                                        # sharey=False,
                                        sharey=True,
                                        gridspec_kw={'wspace': 0})
                
                axs = [axs] if ntypes == 1 else axs.flatten()

                for i, asset_type in enumerate(sorted(totals_epoch['asset_type'].unique())):
                    ax = axs[i]
                    data = totals_epoch[totals_epoch['asset_type'] == asset_type].copy()
                    # data["scenario"] = data["scenario"].astype(str) # NB!

                    returnperiods = sorted(list(data['rp'].unique()), key=lambda x: int(x))
                    cmap = create_white_to_color_cmap(CMAP[i_EPOCH])
                    colors = [cmap(i/len(returnperiods)) for i in range(len(returnperiods))]
                    palette_dict = dict(zip(returnperiods, colors))

                    sns.barplot(
                        x=data['asset_type'].values,
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

                        def create_bounds(df):
                            lower_scenario = "ssp126"
                            mean_scenario = "ssp245"
                            upper_scenario = "ssp585"
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
                
                formatter = FuncFormatter(clean_sci_formatter)

                for ax in axs:
                    ax.yaxis.set_major_formatter(formatter)
                    # make font size tiny for yaxis
                    ax.tick_params(axis='y', which='major', labelsize=8)
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    ax.yaxis.set_ticks_position('left')
                    ax.set_ylim(bottom=1e-6)
                    ax.set_xlabel("")
                    # make the tickers internal
                    ax.tick_params(axis='x', which='both', bottom=False, top=False)
                    ax.tick_params(axis='y', which="both", direction="in")
                    # move labels internal too
                    ax.set_xlim(-0.35, 0.35)

                axs[0].set_ylabel(fr"{METRIC} * {SCALE_FACTOR} [{METRIC_UNIT}]")

                # title is hazard, asset_geom, subregion, range_str
                fig.suptitle(
                    f"hazard: {HAZARD} - asset: {ASSET_GEOM} - epoch : {EPOCH}\n"
                    f"region: {SUBREGION if SUBREGION else 'national'} - range: {range_str}",
                    fontsize=16
                )

                outfile = f"{outdir}/{ASSET_GEOM}_{HAZARD}_{METRIC}_{range_str}_{SUBREGION if SUBREGION else 'national'}.pdf"
                fig.savefig(outfile, dpi=300, bbox_inches='tight', transparent=True)
            # %%