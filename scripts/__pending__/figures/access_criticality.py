"""
Plot EAL for each road segment in terms of accessibility indices.

There are some spurious duplicates in the data that need to be
investigated further.
"""
# %%
from glob import glob
from tqdm import tqdm
import numpy as np
import pandas as pd
import geopandas as gpd
import cartopy.crs as ccrs
import matplotlib.pyplot as plt

import sys
sys.path.append("..")

import utils.plot as pu

service = "school"
hazards = ["pluvial", "fluvial", "coastal", "landslide"] # ! sum across all hazards later

crit_dir = f"/Users/alison/Local/github/oia-tanzania-2025/results/{service}_access/tza_roads_edges"
road_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"
admin0 = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_0.gpkg"

crit_files = []
for hazard in hazards:
    hazard_crit_files = glob(f"{crit_dir}/{hazard}/*/annual.parquet")
    crit_files.extend(hazard_crit_files)

crit_df_list = []
for crit_file in tqdm(crit_files):
    crit_subregion = pd.read_parquet(crit_file)
    crit_subregion = crit_subregion.drop_duplicates()
    crit_df_list.append(crit_subregion)

id_cols = ["id", "base_flux", "epoch", "scenario", "range"]

if service == "school":
    zeta = 1.0
    total_flux = 18_567_485 # from school_criticality.py
    total_weighted_flux = 718_021_545
elif service == "health":
    zeta = 0.00214
    total_flux = 61_567_247 # from health_criticality.py
    total_weighted_flux = 1_091_705_149
else:
    raise ValueError("Unknown service")

crit_df = (
    pd.concat(crit_df_list)
    .drop_duplicates()
    .groupby(id_cols + ["hazard", "metric"])
    .agg({"expected": "max"}) # ! spurious zero-value duplicates: take max
    .reset_index()
    .groupby(id_cols + ["metric"])
    .agg({"expected": "sum"})  # sum across hazards
    .reset_index()
    .pivot(index=id_cols, columns="metric", values="expected")
    .reset_index()
    .set_index("id")
)

crit_df["isolated"] = zeta * crit_df["isolated"]
crit_df["detoured"] = zeta * crit_df["detoured"]
crit_df["wdetoured"] = zeta * crit_df["wdetoured"] / 60

# add geospatial info
admin_gdf = gpd.read_file(admin0)

road_gdf = gpd.read_parquet(road_path)
road_gdf = road_gdf.set_index("id")
road_gdf = road_gdf.to_crs(4326)

print(set(crit_df.index).difference(set(road_gdf.index)), "new ids")
print(len(set(road_gdf.index).difference(set(crit_df.index))), "missing ids")

crit_gdf = crit_df.join(road_gdf[["geometry"]], how="left").reset_index()
crit_gdf = gpd.GeoDataFrame(crit_gdf, geometry="geometry", crs=road_gdf.crs)
crit_gdf = crit_gdf.set_index("id")


# %% subset to the scenario of interest and re-order by criticality
import mapclassify as mc
import matplotlib.lines as mlines
from matplotlib.legend import Legend
import cartopy.feature as cfeature

variable_labels = {
    "isolated": "access loss",
    "detoured": "rerouted",
    "wdetoured": "travel time loss",
    "base_flux": "using road",
}

unit_labels = {
    "isolated": "persons",
    "detoured": "persons",
    "wdetoured": "person-hours",
    "base_flux": "persons",
}

variable = "isolated"

base_scenario = "historical"
base_epoch = "2020"
base_range = "mean"

scenario = "ssp245"
epoch = '2030'
scen_range = "mean"

crit_scenario = crit_gdf[
    (crit_gdf["scenario"] == scenario)
    & (crit_gdf["epoch"] == epoch)
    & (crit_gdf["range"] == scen_range)
].copy()

crit_base = crit_gdf[
    (crit_gdf["scenario"] == base_scenario)
    & (crit_gdf["epoch"] == base_epoch)
    & (crit_gdf["range"] == base_range)
].copy()

if True:
    crit_base[variable] = 0.0 # to just look at raw values

crit_diff = crit_scenario.join(
    crit_base[[variable]],
    how="left",
    rsuffix="_base"
)
crit_diff[variable] = crit_diff[variable] - crit_diff[f"{variable}_base"]
crit_diff[variable] = crit_diff[variable].fillna(0.0)

print(crit_diff[variable].describe())

# %%
crit_diff = crit_diff.sort_values(by=variable, ascending=True)
crit_disrupted = crit_diff[crit_diff[variable] > 0.1].copy()
crit_disrupted = crit_disrupted.drop_duplicates()

def linewidth_func(x, breaks):
    lw = np.ones_like(x) * 1
    for i in range(len(breaks)-1):
        lw[(x >= breaks[i]) & (x < breaks[i+1])] = 1 + i * 0.5
    lw[x >= breaks[-1]] = 1 + (len(breaks)-1) * 0.5
    return lw


def cmap_func(x, breaks, cmap_name="YlOrRd"):
    n_colors = len(breaks)
    cmap = plt.get_cmap(cmap_name, n_colors)
    colors = np.zeros((len(x), 4))
    for i in range(len(breaks)-1):
        colors[(x >= breaks[i]) & (x < breaks[i+1])] = cmap(i)
    colors[x >= breaks[-1]] = cmap(n_colors - 1)
    return colors


values = crit_disrupted[variable].values

def pretty_round(x):
    """Round to 1-2 significant figures"""
    if x == 0:
        return 0
    magnitude = 10 ** np.floor(np.log10(np.abs(x)))
    return np.round(x / magnitude) * magnitude

def make_breaks(values, method="fisherjenks", k=7):
    if method == "naturalbreaks":
        breaks = mc.NaturalBreaks(values, k=k).bins
    elif method == "quantiles":
        breaks = mc.Quantiles(values, k=k).bins
    elif method == "fisherjenks":
        breaks = mc.FisherJenks(values, k=k).bins
    breaks = [pretty_round(b) for b in breaks]
    breaks = np.unique(breaks)
    return np.concatenate([[0], breaks])

k = 5
breaks = make_breaks(values, method="quantiles", k=k)
# breaks = [0, 1, 5, 20]
quants = np.linspace(0, 1, num=k+1) * 100
print(f"Quantile breaks: {breaks}")

# %%

fig, ax = plt.subplots(
    figsize=(15, 15), subplot_kw={"projection": ccrs.PlateCarree()}
)
print(f"Plotting {len(road_gdf)} total road segments")
print(f"Plotting {len(crit_disrupted)} disrupted road segments")


cmap = "YlOrRd"
background_col = "lightgrey"
foreground_col = "#bdbdbd" # "#F0EEE9"
water = "#c6e0ff"
borders = "white"
admin_gdf.plot(ax=ax, color=foreground_col, edgecolor=borders, linewidth=1)
ax.add_feature(cfeature.LAND, facecolor=background_col, edgecolor=borders, linewidth=0.5)
ax.add_feature(cfeature.BORDERS, edgecolor=borders, linewidth=1)
ax.add_feature(cfeature.OCEAN, facecolor=water, edgecolor=borders, linewidth=1)
ax.add_feature(cfeature.LAKES, facecolor=water, edgecolor=borders, linewidth=1)


linewidths = linewidth_func(values, breaks)
colors = cmap_func(values, breaks, cmap_name=cmap)

road_gdf.plot(
    ax=ax,
    color="darkgrey", # "darkgrey"
    linewidth=0.75
)
crit_disrupted.plot(
    ax=ax,
    linewidth=linewidths,
    legend=True,
    color=colors
)


line_examples = []
for i, flux in enumerate(breaks):
    lw = linewidth_func(np.array([flux]), breaks)[0]
    color = cmap_func(np.array([flux]), breaks, cmap_name=cmap)[0]
    if i == 0:
        continue
    if i == 1:
        label = f"{'<' + f'{breaks[i]:,.1f}':<12}(q{quants[i]:.0f})"
    elif i == len(breaks) - 1:
        label = f"{'>' + f'{breaks[i-1]:,.1f}':<12}(q{quants[i-1]:.0f})"
    else:
        label = f"{f'{breaks[i-1]:,.1f} - {breaks[i]:,.1f}':<12}(q{quants[i-1]:.0f} - q{quants[i]:.0f})"
    line = mlines.Line2D([], [], color=color, linewidth=lw, label=label)
    line_examples.append(line)

legend = Legend(ax, line_examples, [line.get_label() for line in line_examples],
                title=f"Expected annual\n{variable_labels[variable]} ({unit_labels[variable]})", loc="lower left",
                fontsize=12,
                title_fontproperties={"weight": "bold", "size": 14},
                prop={'family': 'monospace', 'size': 10})

ax.add_artist(legend)

print("Some statistics:")
print("----------------------")
print(f"Max {variable}: {crit_disrupted[variable].max():,.2f}")
print(f"Id of max {variable}: {crit_disrupted[variable].idxmax()}")
print("----------------------")
print(f"Mean {variable}: {crit_disrupted[variable].mean():,.2f}")
print(f"Median {variable}: {crit_disrupted[variable].median():,.2f}")
print(f"Total {variable}: {crit_disrupted[variable].sum():,.2f}")
print("----------------------")
# %%
# fig.savefig("/Users/alison/Desktop/quicklook.pdf")
# %%
