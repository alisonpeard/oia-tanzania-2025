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
simplified = "/Users/alison/Downloads/flows/tza_road_simplifications.csv"
crit_dir = f"/Users/alison/Local/github/oia-tanzania-2025/results/{service}_access/tza_roads_edges"
road_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"
admin1 = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_1.gpkg"

id_cols = ["id", "base_flux", "hazard", "epoch", "scenario", "range"]

crit_dfs = {}
for hazard in hazards:
    print(f"Loading criticality data for hazard {hazard}...")
    hazard_crit_files = glob(f"{crit_dir}/{hazard}/*/annual.parquet")
    crit_df_list = []
    for crit_file in tqdm(hazard_crit_files, leave=False):
        crit_subregion = pd.read_parquet(crit_file)
        crit_subregion = crit_subregion.drop_duplicates()
        crit_df_list.append(crit_subregion)
    print(f"All files loaded for hazard {hazard}. Combining...")
    crit_df = (
        pd.concat(crit_df_list)
        .drop_duplicates()
        .groupby(id_cols + ["metric"])
        .agg({"expected": "max"}) # ! spurious zero-value duplicates: take max
        .reset_index()
        .pivot(index=id_cols, columns="metric", values="expected")
        .reset_index()
        .set_index("id")
    )
    crit_df["wdetoured"] = crit_df["wdetoured"] / 60 # minutes to hours
    crit_dfs[hazard] = crit_df

print(len(crit_dfs[hazard]), "road segments with criticality data for hazard", hazard)

# %%
variable = "wdetoured"
scenario = "historical"
epoch = ["2015", "2020"]
range_str = "mean"

list_for_concat = []
for hazard, crit_df in crit_dfs.items():
    df_sub = (
        crit_df[
            (crit_df["scenario"] == scenario) &
            (crit_df["epoch"].isin(epoch)) &
            (crit_df["range"] == range_str)
        ][[variable]]
        .groupby(level=0).max()  # or .sum() — dedupe by index
        .rename(columns={variable: hazard})
    )
    list_for_concat.append(df_sub)

full_df = pd.concat(list_for_concat, axis=1, join="inner")
full_df["total"] = full_df.sum(axis=1)

# %% load roads to get road details by id
def format_subregion_name(subregion:str) -> str:
    subregion = subregion.lower()
    subregion = subregion.replace(" ", "_")
    subregion = subregion.replace("/", "-")
    return subregion

roads = gpd.read_parquet(road_path).set_index("id")
segments = pd.read_csv("/Users/alison/Downloads/flows/tza_road_simplifications.csv", index_col="id")
roads = roads.join(segments[["segment_id"]], how="left")
admin = gpd.read_file(admin1)
admin["province"] = admin["shapeName"].apply(format_subregion_name)

# %% top five with road details (comparing hazard contribution)
print(f"{len(full_df)=}")
N = 1000
top_N = full_df.nlargest(N, "total").sort_values("total", ascending=False)
top_N = top_N.join(roads[["road_class", "geometry", "length_m"]], how="left")
top_N = gpd.GeoDataFrame(top_N, geometry="geometry").to_crs(admin.crs)
top_N = top_N.sjoin(admin[["province", "geometry"]], how="left", predicate="intersects")
top_N = top_N.drop(columns=["index_right"])
top_N[["road_class", "province"] + hazards + ["total"]].to_csv(
    f"/Users/alison/Desktop/top_{N}_{service}_{variable}.csv",
    float_format="%.0f"
)

# %%
top_N["main_hazard"] = top_N[hazards].idxmax(axis=1)
# %%
print(top_N["main_hazard"].value_counts() / N * 100)
# %%
print(top_N["province"].value_counts())
# %%
print(top_N["road_class"].value_counts())
# %%
print(top_N["length_m"].describe())

# %%

import cartopy.crs as ccrs
import cartopy.feature as cfeature

top_N = top_N.sort_values("total", ascending=True)
sizes = top_N["total"].values
top_N["geometry"] = top_N["geometry"].centroid

fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection": ccrs.PlateCarree()})

background_col = "lightgrey"
foreground_col = "#bdbdbd" # "#F0EEE9"
water = "#c6e0ff"
borders = "white"
cmap = {"fluvial": "blue", "pluvial": "darkblue", "coastal": "turquoise", "landslide": "brown"}
colors = top_N["main_hazard"].map(cmap).values
top_N["plot_color"] = colors
top_N["plot_size"] = sizes

ax.add_feature(cfeature.BORDERS, color=borders, linewidth=1)
ax.add_feature(cfeature.COASTLINE, color=borders, linewidth=1)
ax.add_feature(cfeature.LAND, facecolor=background_col, edgecolor=borders, linewidth=0.5)
ax.add_feature(cfeature.OCEAN, facecolor=water, edgecolor=borders, linewidth=1)

admin.dissolve().plot(ax=ax, color=foreground_col, edgecolor=borders, linewidth=1)

top_N.plot(
    column="main_hazard",
    categorical=True,
    legend=True,
    ax=ax,
    alpha=0.5,
    edgecolor=colors,
    zorder=100,
    markersize=sizes / sizes.max() * 200,
    legend_kwds={"bbox_to_anchor": (1.3, 1)}
)

top_N.to_file(
    f"/Users/alison/Desktop/top_1000_{service}_{variable}.gpkg",
    driver="GPKG"
)
# %% top five comparing climate change impacts 

# %%
full_df.head()
# %%

# %% other summaries
summary = full_df[hazards].agg(["sum", "mean", "median", "max"])
summary.loc["pct_of_total"] = full_df[hazards].sum() / full_df["total"].sum() * 100
print(summary.round(2))

# %%
summary = pd.DataFrame({
    "Total persons at risk": full_df[hazards].sum(),
    "% of total risk": full_df[hazards].sum() / full_df["total"].sum() * 100,
    "Assets affected": (full_df[hazards] > 0).sum(),
    "Mean per asset": full_df[hazards].mean(),
    "Max (single asset)": full_df[hazards].max()
}).round(1)
print(summary)
# %% Plots start here

full_df_tail = full_df[full_df["total"] > 1000]
full_df_tail = full_df_tail.sort_values("total", ascending=True)
print(len(full_df_tail), "road segments with total isolated > 1000 persons")


# %%
fig, ax = plt.subplots(figsize=(10, 5))


# Sort by total
# full_df_sorted = full_df.sort_values("total").reset_index(drop=True)
x = np.arange(len(full_df_tail))

# Stacked bars
bottom = np.zeros(len(full_df_tail))
for hazard in hazards:
    ax.bar(x, full_df_tail[hazard], bottom=bottom, width=1.0, label=hazard)
    bottom += full_df_tail[hazard].values

ax.set_xlabel("Percentile rank (%)")
ax.set_ylabel("Persons isolated")
ax.legend()

# Convert x-axis to percentile
ax.set_xlim(0, len(full_df_tail))
ax.set_xticks(np.linspace(0, len(full_df_tail), 6))
ax.set_xticklabels([0, 20, 40, 60, 80, 100])
# %%
ax.set_yscale("log")
fig
# %% proportion of total EAD per asset

n_bins = 50
full_df_tail["pct_bin"] = pd.qcut(full_df_tail["total"], n_bins, labels=False)
binned = full_df_tail.groupby("pct_bin")[hazards].mean()

hazards = binned.sum(axis=0).sort_values(ascending=False).index.tolist() # re-order

fig, ax = plt.subplots(figsize=(10, 5))

colors = ["darkblue", "brown", "blue", "turquoise"]
ax.stackplot(
    binned.index,
    [binned[h] for h in hazards],
    colors=colors,
    labels=hazards,
    alpha=0.6,
    edgecolor=colors,
    linewidth=0.5
)
ax.set_xlabel("Percentile rank (%)")
ax.set_ylabel("Mean persons isolated")
ax.legend(title="Hazard", loc="upper left")
ax.set_yscale("log")
# %%

binned_props = binned.div(binned.sum(axis=1), axis=0)

fig, ax = plt.subplots(figsize=(10, 5))
ax.stackplot(
    binned_props.index,
    [binned_props[h] for h in hazards], 
    labels=hazards,
    colors=colors,
    alpha=0.6,
    edgecolor=colors,
    linewidth=0.5
)
ax.set_xlabel("Percentile rank (%)")
ax.set_ylabel("Proportion of risk")
ax.legend(title="Hazard", loc="lower left")
# %% boxplot or violin plot also useful for overall spread
fig, ax = plt.subplots(figsize=(8, 6))
# full_df_tail[hazards].plot.box(ax=ax)
ax.violinplot([full_df_tail[hazard] for hazard in hazards], showmeans=False)
# ax.set_yscale("log")
# %%
