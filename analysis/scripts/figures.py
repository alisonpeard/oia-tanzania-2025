
# %%
import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.colors as mcolors

HAZARD   = "pluvial"
ASSET_GEOM = "tza_roads_edges"
METRIC = "cost"
range_str = "mean_mean"
SUBREGION = [None, "kilimanjaro"][0]
WD = "../../results"
LOCAL_CRS = 32735
CMAP = npg = ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4', '#91D1C2', '#DC0000', '#7E6148', '#B09C85']
SCALE_FACTOR = 1e-6


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

    if SUBREGION:
        asset_path = os.path.join(
            WD, "risk", ASSET_GEOM, HAZARD, SUBREGION, "profile.geoparquet"
        )
        asset = gpd.read_parquet(asset_path)
    else:
        base_dir = os.path.join(WD, "risk", ASSET_GEOM, HAZARD)
        subregions = os.listdir(base_dir)
        print(subregions)
        asset_files = [os.path.join(base_dir, subregion, "profile.geoparquet") for subregion in
                          subregions if os.path.isdir(os.path.join(base_dir, subregion))]
        asset_dfs = [gpd.read_parquet(f).reset_index() for f in asset_files]
        asset = pd.concat(asset_dfs, axis=0)
        # asset = asset.groupby("id").mean().reset_index() # need to do later

    df = asset.copy()

    # barplot_scenarios(asset)
    risk_cols = [col for col in df.columns if col.startswith(METRIC)]
    risk_gdf = df[risk_cols].copy().T.reset_index()
    risk_tuples = risk_gdf["index"].apply(extract_hazard_info)
    risk_info = pd.DataFrame(
        risk_tuples.tolist(),
        columns=["metric", "hazard", "epoch", "scenario", "rp", "range"]
    )
    risk_info = risk_info[risk_info['range'] == range_str].copy()
    risk_info = risk_info.drop(columns=['metric', 'hazard', 'range'])

    risk_gdf = risk_gdf.drop(columns=['index'])
    total = risk_gdf.sum(axis=1).rename("total")
    total = risk_info.join(total, how="left")

    # risk_gdf["value"] = risk_gdf["value"].fillna(0.0)
    total["epoch"] = total["epoch"].astype(int)
    total["rp"] = total["rp"].astype(int)

    # make scenario categorical with order
    scenario_order = sorted(list(total['scenario'].unique()))
    total['scenario'] = pd.Categorical(total['scenario'], categories=scenario_order, ordered=True)

    means = total.groupby(
        ["epoch", "scenario", "rp"]
    )[["total"]].mean().reset_index()

    summaries = means.groupby(["scenario", "epoch"]).sum()
    valid_pairs = summaries[summaries['total'] > 0].reset_index()
    ncols = len(valid_pairs)

    # subset means to only valid pairs
    means = means.merge(
        valid_pairs[['scenario', 'epoch']],
        on=['scenario', 'epoch'],
        how='inner'
    )

    scenarios = sorted(list(means['scenario'].unique()))
    epochs = sorted(list(means['epoch'].unique()))
    returnperiods = sorted(list(means['rp'].unique()), key=lambda x: int(x))
    norm = mcolors.BoundaryNorm(returnperiods, 256)

    # start plotting
    fig, axs = plt.subplots(1, ncols,
                            figsize=(ncols * 2, 4),
                            sharey=True,
                            gridspec_kw={'wspace': 0})

    axs = [axs] if ncols == 1 else axs.flatten()

    cmaps = {}
    for i, scenario in enumerate(scenarios):
        cmap = create_white_to_color_cmap(CMAP[i])
        cmaps[scenario] = cmap

    i = 0
    for epoch in sorted(epochs):
        epoch_data = means[means['epoch'] == epoch].copy()
        scenarios = list(epoch_data['scenario'].unique())
        first_scenario = True
        for scenario in sorted(scenarios):
            try:
                ax = axs[i]
                data = epoch_data[epoch_data['scenario'] == scenario].copy()
                data["scenario"] = data["scenario"].astype(str) # NB!

                cmap = cmaps[scenario]
                colors = [cmap(i/len(returnperiods)) for i in range(len(returnperiods))]
                palette_dict = dict(zip(returnperiods, colors))

                sns.barplot(
                    x=data['scenario'].values,
                    y=data["total"].values * SCALE_FACTOR,
                    hue=data['rp'].values, ax=ax,
                    palette=palette_dict,
                    legend=first_scenario,
                    edgecolor='black',
                    linewidth=0.5,
                    width=0.6
                )
                if first_scenario:
                    sns.move_legend(ax, "upper left", title="return period", frameon=False)
                    ax.set_xlabel(epoch, fontweight='bold', x=0.5)
                else:
                    ax.set_xlabel("")
            except Exception as e:
                print(f"ERROR: {e}")
            if not first_scenario:
                ax.spines['left'].set_visible(False)
                ax.yaxis.set_ticks_position('none')
                ax.set_xlabel("")

            # DEBUGGING
            for rp in returnperiods:
                data_rp = data[data['rp'] == rp].copy()
                print(f"DEBUG: {epoch} - {scenario} - {rp}: {data_rp['total'].sum() * SCALE_FACTOR}")
            first_scenario = False
            i += 1

    for ax in axs:
        ax.set_xlim(-0.35, 0.35)

    # turn off top and right spines
    for ax in axs:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    axs[0].set_ylabel(f"{METRIC} ({SCALE_FACTOR})")

    # Track epoch boundaries to apply formatting correctly
    epoch_starts = {}
    for idx, ax in enumerate(axs):
        label = ax.get_xlabel()
        if label and label.strip() and label not in epoch_starts:
            epoch_starts[label] = idx
    
    # Format subplots: first of each epoch keeps left spine, rest don't
    for epoch, start_idx in epoch_starts.items():
        # Find all subplots for this epoch (consecutive subplots until next epoch label)
        epoch_indices = [start_idx]
        for idx in range(start_idx + 1, len(axs)):
            if axs[idx].get_xlabel().strip():  # Next epoch starts
                break
            epoch_indices.append(idx)
        
        # Remove left spine and ticks for non-first subplots in epoch
        for idx in epoch_indices[1:]:
            axs[idx].spines['left'].set_visible(False)
            axs[idx].yaxis.set_ticks_position('none')
            axs[idx].set_xlabel("")
        
        # Center the epoch label across all its subplots
        if len(epoch_indices) > 1:
            center_pos = (epoch_indices[-1] - epoch_indices[0]) / 2
            axs[start_idx].set_xlabel(epoch, fontweight='bold', x=0.5 + center_pos)
    
    # title is hazard, asset_geom, subregion, range_str
    fig.suptitle(
        f"{HAZARD} - {ASSET_GEOM} - "
        f"region: {SUBREGION if SUBREGION else 'national'} - {range_str}",
        fontsize=16
    )
    
# %%