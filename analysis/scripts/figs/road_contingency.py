# %%
import numpy as np
import seaborn as sns
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt


path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"

gdf = gpd.read_parquet(path)
# gdf["condition"] = gdf["asset_type"].str.split("_").str[-1]
# gdf["asset_type"] = gdf["asset_type"].str.split("_").str[0]

conditions = ['bad', 'poor', 'fair', 'good']

def extract_condition(asset_type):
    for condition in conditions:
        if asset_type.endswith(f"_{condition}"):
            return condition
    return pd.NA

def remove_condition(asset_type):
    for condition in conditions:
        suffix = f"_{condition}"
        if asset_type.endswith(suffix):
            return asset_type[:-len(suffix)]
    return asset_type

def format_road_type(colname):
    """Format road type column name for display."""
    if colname not in ["dbst", "sbst"]:
        colname = colname.replace("_", " ").replace(" ", "\n")
        colname = colname.capitalize()
    else:
        colname = colname.upper()
    return colname

gdf["condition"] = gdf["asset_type"].apply(extract_condition)
gdf["asset_type"] = gdf["asset_type"].apply(remove_condition)
# %%
assert gdf.crs == "EPSG:32735"
gdf["length_km"] = gdf.geometry.length / 1000.0

# %%
def roadtypes(gdf, colA, colB):
    """Calculate road types contingency table (in km)."""
    # gdf = provider.gdf.copy()
    df = gdf[[colA, colB, "length_km"]].copy()
    # counts = df.groupby(['asset_type','paved']).size().reset_index(name='count')
    counts = df.groupby([colA, colB])[["length_km"]].sum().reset_index()
    counts.rename(columns={"length_km": "count"}, inplace=True)

    D = counts[colB].nunique()
    H = counts[colA].nunique()

    # same plot as in previous cell but transpose
    g = sns.jointplot(data=counts, x=colA, y=colB, kind='hist', bins=(H, D))
    g.ax_marg_y.cla()
    g.ax_marg_x.cla()

    sns.heatmap(data=counts['count'].to_numpy().reshape(H, D).T, ax=g.ax_joint, cbar=False,
                cmap='YlGnBu', linewidths=0.5, linecolor='k')
    g.ax_marg_y.barh(np.arange(0.5, D), counts.groupby([colB])['count'].sum().to_numpy(), color='k', fill=False, linewidth=0.5)
    g.ax_marg_x.bar(np.arange(0.5, H), counts.groupby([colA])['count'].sum().to_numpy(), color='k', fill=False, linewidth=0.5)

    # add counts to bar plots
    g.ax_marg_x.bar_label(g.ax_marg_x.containers[0])
    g.ax_marg_y.bar_label(g.ax_marg_y.containers[0])
    g.ax_joint.set_xticks(np.arange(0.5, H))
    yticklabels = [rtype.split('_')[-1].capitalize() for rtype in counts[colA].unique()]
    g.ax_joint.set_xticklabels(yticklabels, rotation=0)
    g.ax_joint.set_yticks(np.arange(0.5, D))
    g.ax_joint.set_yticklabels(["Unpaved", "Paved"], rotation=0)

    # make sure all spines are visible
    g.ax_joint.spines['right'].set_visible(True)
    g.ax_joint.spines['bottom'].set_visible(True)

    # # remove ticks between heatmap and histograms
    g.ax_marg_x.tick_params(axis='x', bottom=False, labelbottom=False)
    g.ax_marg_y.tick_params(axis='y', left=False, labelleft=False)

    # # remove ticks showing the heights of the histograms
    g.ax_marg_x.tick_params(axis='y', left=False, labelleft=False)
    g.ax_marg_y.tick_params(axis='x', bottom=False, labelbottom=False)

    # resize
    fig = plt.gcf()
    fig.set_size_inches(8, 4)

    return fig, g

def roadtypes(gdf, colA, colB, cmap="PuBu"):
    """Calculate road types contingency table (in km) with marginal totals."""
    df = gdf[[colA, colB, "length_km"]].copy()
    
    # Create the pivot table to handle missing combinations (sparse data)
    pivot_df = df.groupby([colB, colA])["length_km"].sum().unstack(fill_value=0)
    
    D, H = pivot_df.shape  # D = rows (condition), H = columns (asset_type)

    # Initialize jointplot
    g = sns.jointplot(data=df, x=colA, y=colB, kind='hist', bins=(H, D))
    g.ax_marg_y.cla()
    g.ax_marg_x.cla()

    # Heatmap in the center
    sns.heatmap(data=pivot_df, ax=g.ax_joint, cbar=False,
                cmap=cmap, linewidths=0.5, linecolor='k')

    # Marginal bar plots (Total km)
    g.ax_marg_y.barh(np.arange(0.5, D), pivot_df.sum(axis=1), color='k', fill=False, linewidth=0.5)
    g.ax_marg_x.bar(np.arange(0.5, H), pivot_df.sum(axis=0), color='k', fill=False, linewidth=0.5)

    # Add count labels to marginal bars
    g.ax_marg_x.bar_label(g.ax_marg_x.containers[0], fmt='%.0f', padding=3)
    g.ax_marg_y.bar_label(g.ax_marg_y.containers[0], fmt='%.0f', padding=3)

    # Styling the axes
    g.ax_joint.set_xticks(np.arange(0.5, H))
    # Capitalize type labels for cleaner look
    # xticklabels = [str(x).replace("_", " ").capitalize() for x in pivot_df.columns]
    xticklabels = [format_road_type(x) for x in pivot_df.columns]
    g.ax_joint.set_xticklabels(xticklabels, rotation=0, ha='center')
    
    g.ax_joint.set_yticks(np.arange(0.5, D))
    yticklabels = [str(y).capitalize() for y in pivot_df.index]
    g.ax_joint.set_yticklabels(yticklabels, rotation=0)

    # Ensure all spines are visible for a boxed look
    for spine in g.ax_joint.spines.values():
        spine.set_visible(True)

    # Clean up marginal ticks
    g.ax_marg_x.tick_params(axis='both', which='both', bottom=False, left=False, labelbottom=False, labelleft=False)
    g.ax_marg_y.tick_params(axis='both', which='both', bottom=False, left=False, labelbottom=False, labelleft=False)

    # Set overall labels
    g.ax_joint.set_xlabel("Asset type", fontweight='bold') 
    g.ax_joint.set_ylabel("Condition", fontweight='bold')

    # Resize figure
    fig = plt.gcf()
    fig.set_size_inches(10, 6)
    plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.2)

    return fig, g
# %%
roadtypes(gdf, colA="asset_type", colB="condition", cmap="PuBu")
# %%
