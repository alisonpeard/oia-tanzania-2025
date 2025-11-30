"""Functions to create bar charts for direct damages by country."""
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib as mpl
import matplotlib.patches as mpatches

from . import core
from . import plot
from . import providers

# %% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def admin0_by_type(provider, meancols, mincols, maxcols,
                   HAZARD, EPOCH, SCENARIO, RPS,
                   var="asset_type", aggfun="sum",
                   cmap="YlGnBu"):
    # subset meancols, mincols, maxcols
    gdf      = provider.gdf.copy()
    meancols = plot.subset_columns(meancols, hazards=HAZARD, scenarios=SCENARIO, epochs=EPOCH, rps=RPS)
    mincols  = plot.subset_columns(mincols,  hazards=HAZARD, scenarios=SCENARIO, epochs=EPOCH, rps=RPS)
    maxcols  = plot.subset_columns(maxcols,  hazards=HAZARD, scenarios=SCENARIO, epochs=EPOCH, rps=RPS)

    assert len(meancols) == len(mincols) == len(maxcols), \
        f"Number of columns do not match: {len(meancols)} != {len(mincols)} != {len(maxcols)}"

    # group by variable of interest
    means = gdf.groupby(var)[meancols].agg(aggfun)
    mins  = gdf.groupby(var)[mincols].agg(aggfun)
    maxs  = gdf.groupby(var)[maxcols].agg(aggfun)

    # standardise column names
    RPS = [provider.format_rp(RP) for RP in RPS]
    means.columns = RPS
    mins.columns = RPS
    maxs.columns = RPS

    upper = maxs - means
    lower = means - mins
    upper = upper.T.values
    lower = lower.T.values
    yerr = np.stack([lower, upper], axis=1)

    # make color list
    cmap = plt.get_cmap(cmap)
    N    = len(RPS)
    cmaplist = [cmap(i) for i in range(cmap.N)]
    cmap = mcolors.LinearSegmentedColormap.from_list(cmap, cmaplist, cmap.N)
    colors = [cmap(i / N) for i in range(N)]

    ncategories = gdf[var].nunique()
    width       = 2 + ncategories * 2
    # create a barchart
    fig, ax = plt.subplots(figsize=(width, 4))
    means.plot.bar(ax=ax,
                   yerr=yerr, capsize=2,
                   color=colors,
                   edgecolor='k', linewidth=0.5,
                   error_kw={'elinewidth': 0.5, 'capthick': 0.5}
                   )

    # aesthetics
    ax.set_yscale("linear")
    ax.set_ylabel("Exposed to direct flood damages\n(million USD)", fontsize=14)
    ax.set_xlabel("", fontsize=14)
    ax.set_title(f"{EPOCH} {plot.format_scenario(SCENARIO)}", fontsize=18)

    ax.yaxis.set_major_formatter(plot.dollar_format)
    ax.set_xticklabels([plot.format_types(x, var) for x in means.index], fontsize=12, rotation=0)
    plt.tight_layout()

    return fig, ax

# %% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
def admin0_scenarios(provider, meancols,
                     SCENARIOS, EPOCHS, RPS):
    gdf = provider.gdf.copy()
    meancols = plot.subset_columns(meancols, scenarios=SCENARIOS, epochs=EPOCHS, rps=RPS)
    sum = gdf[meancols].sum()
    sum_means = pd.DataFrame(sum).reset_index()
    sum_means.columns = ['hazard_code', 'usd']

    split_codes = sum_means["hazard_code"].str.split('_', expand=True)
    sum_means['hazard']   = split_codes[0].apply(provider.format_hazard_slug)
    sum_means['scenario'] = split_codes[1].apply(provider.format_scenario)
    sum_means['epoch']    = split_codes[2].apply(provider.format_epoch)
    sum_means['returnperiod'] = split_codes[3].apply(provider.format_rp)

    sum_means = sum_means.drop(columns=['hazard_code'])

    river_means = sum_means.copy()
    returnperiods = sorted(list(sum_means['returnperiod'].unique()))
    epochs = list(sum_means['epoch'].unique())
    norm = mcolors.BoundaryNorm(returnperiods, 256)

    # start plotting
    ncols = ((len(SCENARIOS) - 1 ) * len(EPOCHS)) - 1
    fig, axs = plt.subplots(1, ncols, figsize=(ncols * 3, 4), sharey=True,
                            gridspec_kw={'wspace': 0})
    axs = plot.ensure_list(axs)
    river_means['scenario'] = river_means['scenario'].str.replace('rcp', 'RCP ').str.replace('p','.')
    river_means['scenario'] = river_means['scenario'].str.replace('historical', ' ').str.replace('hist', ' ')
    river_means.columns = ["USD", "Hazard", "Scenario", "Epoch", "Return period"]
    river_means['USD (million)'] = river_means['USD'] * 1e-6

    river_means = river_means.sort_values(by=['Epoch', 'Scenario', 'Return period'])

    cmaps = {}
    for i, scenario in enumerate(river_means['Scenario'].unique()):
        cmap = plot.create_white_to_color_cmap(core.npg[i])
        cmaps[scenario] = cmap

    i = 0
    for epoch in sorted(epochs):
        epoch_data = river_means[river_means['Epoch'] == epoch]
        scenarios = list(epoch_data['Scenario'].unique())
        
        for scenario in sorted(scenarios):
            try:
                data = epoch_data[epoch_data['Scenario'] == scenario]
                cmap = cmaps[scenario]
                add_legend = "full" if (i in [0, 1, 2]) else False
                sns.barplot(x=data['Scenario'], y=data['USD (million)'],
                            hue=data['Return period'], ax=axs[i],
                            palette=cmap, legend=add_legend, hue_norm=norm,
                            edgecolor='black', linewidth=0.5)
                if add_legend == "full":
                    sns.move_legend(axs[i], "upper left")
                axs[i].set_xlabel(epoch, fontweight='bold', x=0.5)
            except Exception as e:
                print(e)
            i += 1

    # turn off top and right spines
    for ax in axs:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    for j in list(np.arange(2, len(axs), 2)):
        ax = axs[j]
        ax.spines['left'].set_visible(False)
        ax.yaxis.set_ticks_position('none')  # no ticks on the left
        ax.set_xlim(-0.4, 0.6)
        ax.set_xlabel("")

    # shift xlabels for scenarios
    for epoch, j in zip(sorted(epochs)[1:], np.arange(1, ncols, 2)):
        ax = axs[j]
        ax.set_xlim(-0.55, 0.45)
        ax.set_xlabel(epoch, fontsize=12, fontweight='bold', x=1)

    # axs[0].set_xlabel("Historical", fontsize=12, fontweight='bold')

    return fig, axs

# %% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
def admin1_roadlength(provider,
                      meancols,
                      HAZARD, EPOCH, SCENARIO, RP,
                      SORTBY = "length_km",
                      CMAP = "YlOrRd"):
    """Vertical bar chart of road length exposed to flood hazard by state."""
    gdf = provider.gdf.copy()
    COLORBY = f'{provider.format_rp(RP)}-year'

    # filter to hazard type
    meancol= plot.subset_columns(meancols, hazards=HAZARD, scenarios=SCENARIO, epochs=EPOCH, rps=RP)
    assert len(meancol) == 1, f"Multiple columns found for {HAZARD} {EPOCH} {SCENARIO} {RP}: {meancols}"

    # replace depths with lengths flooded
    gdf = gdf.copy()
    gdf[meancol[0]] = np.where(gdf[meancol[0]] > 0, gdf['length_km'], 0)

    # group by state and get totals
    means = gdf.groupby("state")[meancol].agg('sum')
    totals = gdf.groupby("state")['length_km'].sum()

    assert np.isclose(totals.sum(), gdf['length_km'].sum()), \
        f"Total length of roads does not match: {totals.sum()} != {gdf['length_km'].sum()}"

    means['length_km'] = totals

    # now get fraction of road length exposed
    means[meancol] = means[meancol].div(means['length_km'], axis=0)
    means = means.drop(columns='length_km')

    # rename columns so names match
    RPS = [COLORBY]
    means = means[meancol]
    means.columns = RPS

    # subset means to what we want to plot
    means['length_km'] = totals
    means_rp = means[[SORTBY, COLORBY]].dropna(axis=0)

    # create colormap
    cmap = plt.get_cmap(CMAP)
    vmax = 1.05 # means_rp[COLORBY].max()
    vmin = 0    # means_rp[COLORBY].min()
    cmaplist = [cmap(i) for i in range(cmap.N)]
    cmap = mpl.colors.LinearSegmentedColormap.from_list(COLORBY, cmaplist, cmap.N)
    bounds = np.arange(vmin, vmax, .05)
    norm = mpl.colors.BoundaryNorm(bounds, cmap.N)
    colors = [cmap((length - vmin) / (vmax - vmin)) for length in means_rp[COLORBY]]

    # make figure
    fig, ax = plt.subplots(figsize=(4, 8))
    sorting = np.argsort(means_rp[SORTBY].values)
    means_rp.iloc[sorting,:].plot.barh(
        ax=ax, y=SORTBY,
        width=0.7,
        color=np.array(colors)[sorting], edgecolor='black', linewidth=0.5,
        legend=False
        )

    ax.set_xlabel(f"Length (km)", fontsize=14)
    ax.set_ylabel("", fontsize=18)
    ax2 = fig.add_axes([0.95, 0.15, 0.03, 0.65])
    cb = mpl.colorbar.ColorbarBase(ax2, cmap=cmap, norm=norm, spacing='proportional',
                                ticks=bounds, boundaries=bounds,
                                format=mpl.ticker.PercentFormatter(xmax=1, decimals=0, symbol='%')
                                )
    cb.set_label(f'%length exposed to {RP}-year flood')
    ax.set_title(f"{EPOCH} {plot.format_scenario(SCENARIO)}", fontsize=18);

    return fig, ax

# %% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
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

    # make color list
    colors = core.npg

    # sort by total value exposed
    sorting = np.argsort(means_rp.sum(axis=1).values)

    # make figure
    fig, ax = plt.subplots(figsize=(8, 8))
    means_rp.iloc[sorting,:].plot.barh(
        ax=ax,
        stacked=True,
        legend=True,
        color=colors,
        linewidth=.5,
        edgecolor='#666666',
        width=0.7,
        )

    ax.set_ylabel("")
    ax.set_xlabel(f"Exposed to {RP}-year flood hazard (million USD)", fontsize=18)
    ax.set_title(f"{EPOCH} {provider.format_scenario(SCENARIO)}", fontsize=20)

    legend = ax.legend(loc='lower right')
    texts  = legend.get_texts()
    for text in texts:
        original_text = text.get_text()
        formatted_text = original_text.split('_')[-1].capitalize()
        text.set_text(formatted_text)

    return fig, ax

# %% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
def make_color_dict(gdf, field, colors):
    assets = list(gdf[field].unique())
    color_dict = {}
    for i, asset in enumerate(assets):
        color_dict[asset] = colors[i]
    return color_dict


def assetlevel_damages(provider, rankcols,
                       HAZARD, EPOCH, SCENARIO, RP,
                       N=30,
                       cmap_index=2,
                       COLORBY="asset_type") -> tuple:
    """
    rankcol: column to rank by (EAD or exposure)
    """
    gdf = provider.gdf.copy()
    # filter to scenario
    rankcols = plot.subset_columns(rankcols, hazards=HAZARD, scenarios=SCENARIO, epochs=EPOCH, rps=RP)
    assert len(rankcols) > 0, f"No columns found for {HAZARD} {EPOCH} {SCENARIO} {RP}"
    assert len(rankcols) == 1, f"Multiple columns found for {HAZARD} {EPOCH} {SCENARIO} {RP}: {rankcols}"
    rankcol = rankcols[0]

    exposed_roads = gdf[gdf[rankcol] > 0].copy()
    exposed_roads = exposed_roads.sort_values(by=rankcol, ascending=True)
    top_roads = exposed_roads.tail(N).copy()

    top_roads["paved"] = top_roads["paved"].apply(lambda x: "Paved" if x else "Unpaved")

    from random import shuffle, seed
    seed(42)
    shuffle(core.npg)
    color_dict = make_color_dict(top_roads, COLORBY, core.npg)

    fig, axs = plt.subplots(1, 2, figsize=(8, 6), sharey=True, gridspec_kw={'wspace': 0.})

    top_roads['color'] = top_roads[COLORBY].map(color_dict)
    top_roads.plot.barh(x='id', y=rankcol, color=top_roads['color'], ax=axs[0],
                        edgecolor='black', linewidth=0.5, legend=False)
    axs[0].set_xlabel("EAD (USD)")

    # Create legend patches
    color_dict = {asset_type.split("_")[-1].capitalize(): color for asset_type, color in color_dict.items()}
    legend_patches = [mpatches.Patch(color=color, label=asset_type) 
                    for asset_type, color in color_dict.items()]

    # Add the legend to the figure
    fig.legend(handles=legend_patches, loc='lower center', bbox_to_anchor=(0.5, -0.1),
            ncol=min(top_roads[COLORBY].nunique(), 4))  # Adjust ncol as needed

    top_roads.plot.barh(x='osm_way_id', y='length_km', color=top_roads['color'], ax=axs[1],
                        edgecolor='black', linewidth=0.5, legend=False)
    axs[1].set_xlabel("Length (km)")
    axs[0].set_ylabel("OSM Way ID")

    return fig, axs, top_roads