#%%
import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd
import seaborn as sns

summary_path = "/Users/alison/Desktop/tza_school_roads_hazard_disruption_summary.csv"
admin_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_1.gpkg"
crit_path = "/Users/alison/Desktop/tza_school_roads_edge_criticality.csv" # use this to get % lost access
roads_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"

def identify_variation_source(df, group_cols, value_cols):
    # df = df.drop(columns=value_cols).copy()
    counts = df.groupby(group_cols).nunique().max()
    counts = counts.drop(labels=value_cols)
    counts = counts[counts > 1].copy()
    print(f"Variation across {len(counts)} columns: {dict(counts)}")
    for col in counts.index:
        std = df.groupby(col)[value_cols].std().mean()
        max = df.groupby(col)[value_cols].max().mean()
        min = df.groupby(col)[value_cols].min().mean()
        range_ = max - min
        print(f"  - {col}: {dict(range_)}")

#%%
admin = gpd.read_file(admin_path)
admin["province"] = admin["shapeName"].str.lower()
admin.head()

# %%

# assign each road to a province
roads = gpd.read_parquet(roads_path)
roads = roads.to_crs(admin.crs)

roads_with_admin = gpd.sjoin(roads, admin[["province", "geometry"]], how="left", predicate="intersects")
roads_subregion_dict = roads_with_admin.set_index("id")["province"].to_dict()
del roads, roads_with_admin

base = pd.read_csv(crit_path)
base["subregion"] = base["id"].map(roads_subregion_dict)
# %%
base = base.groupby("subregion")[["base_flux"]].sum().reset_index()
base.head()

# %%

summary = pd.read_csv(summary_path)
summary["total_weighted_detour_hrs"] = summary["total_weighted_detour"] / 60  # to walking mins
summary.head()
summary["subregion"].nunique()
# %%
summary_national = summary.groupby(["hazard", "epoch", "scenario", "rp", "stat"]).agg({
    "total_isolated": "sum",
    "total_rerouted": "sum",
    "total_weighted_detour_hrs": "sum"

}).reset_index()
summary_national.head()
# %%


# error bar represents ssps and min/max damage curves
hazard = "fluvial"
summary_hazard = summary_national[summary_national["hazard"] == hazard].copy()


def minmax(x):
    return (x.min(), x.max())

sns.catplot(
    data=summary_hazard,
    x="epoch",
    y="total_isolated",
    hue="rp",
    edgecolor="k",
    linewidth=0.25,
    kind="bar",
    palette="Blues",
    errorbar=("pi", 100),
    height=6,
    aspect=2
)
plt.yscale("log")
plt.title(f"School journeys at-risk of isolation from {hazard}")
plt.ylabel("Total loss of access")
plt.xlabel("Hazard type")
plt.tight_layout()


sns.catplot(
    data=summary_hazard,
    x="epoch",
    y="total_rerouted",
    hue="rp",
    edgecolor="k",
    linewidth=0.25,
    kind="bar",
    palette="Blues",
    errorbar=("pi", 100),
    height=6,
    aspect=2
)
plt.yscale("log")
plt.title(f"School journeys at-risk of rerouting from {hazard}")
plt.ylabel("Total rerouted journeys")
plt.xlabel("Hazard type")
plt.tight_layout()

# %% barplot of all detoured time
sns.catplot(
    data=summary_hazard,
    x="epoch",
    y="total_weighted_detour_hrs",
    hue="rp",
    edgecolor="k",
    linewidth=0.25,
    kind="bar",
    palette="Blues",
    errorbar=("pi", 100),
    height=6,
    aspect=2,
)

ax = plt.gca()
ax.legend(title="Return Period", frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))

plt.yscale("log")
plt.title(f"Aggregate detour time across all at-risk school journeys from {hazard}")
plt.ylabel("Aggregate detour time (walking hrs)")
plt.xlabel("Hazard type")
plt.tight_layout()

identify_variation_source(summary_hazard, ["epoch", "rp"], ["total_isolated", "total_rerouted", "total_weighted_detour_hrs"])
# %% barplot of all isolated (by subregion)
summary_hazard = summary[summary["hazard"] == hazard].copy()
summary_hazard_rp100 = summary_hazard[summary_hazard["rp"] == 100].copy()

sns.catplot(
    data=summary_hazard_rp100,
    x="subregion",
    y="total_isolated",
    hue="epoch",
    edgecolor="k",
    linewidth=0.25,
    kind="bar",
    palette="Blues",
    errorbar=("pi", 100),
    height=6,
    aspect=2, # make horizontal
    orient="x"
)
# %%
summary_single = summary_hazard_rp100[
    (summary_hazard_rp100["scenario"] == "ssp245") & \
    (summary_hazard_rp100["epoch"] == 2050) & \
    (summary_hazard_rp100["stat"] == "mean")
]

#! check this is == 1
summary_single.groupby(["subregion", "hazard", "epoch", "scenario", "rp", "stat"]).nunique().max().max()
summary_single.head()
# %%
# first assign a province to each subregion
summary_gdf = pd.merge(summary_single, admin[["province", "geometry"]],
                       left_on="subregion", right_on="province", how="inner")
summary_gdf.groupby(["subregion", "hazard", "epoch", "scenario", "rp", "stat"]).nunique().max().max()
# %%
summary_gdf = pd.merge(summary_gdf, base[["base_flux", "subregion"]], on="subregion", how="left")
summary_gdf.groupby(["subregion", "hazard", "epoch", "scenario", "rp", "stat"]).nunique().max().max()
# %% sanity check fluxes
summary_gdf["total_disrupted"] = summary_gdf["total_isolated"] + summary_gdf["total_rerouted"]
summary_gdf["percent_disrupted"] = 100 * (summary_gdf["total_disrupted"] / summary_gdf["base_flux"])
summary_gdf["percent_disrupted"].max() <= 100.0

# %%
summary_gdf = gpd.GeoDataFrame(summary_gdf, geometry="geometry", crs=admin.crs)
summary_gdf.head()
# %%
import cartopy.crs as ccrs
import cartopy.feature as cfeature

import sys
sys.path.append("..")
import utils.plot as pu

fig, axs = plt.subplots(1, 3, figsize=(8, 3),
                        subplot_kw={"projection": ccrs.PlateCarree()})

variables = ["percent_disrupted", "total_isolated", "total_weighted_detour_hrs"]
titles = ["Percent at-risk\nof disruption", "Percent at-risk\nof isolation", "Pooled detour hrs\n(walking)"]

def add_geofeatures(ax):
    ax.add_feature(cfeature.BORDERS, color='k', linestyle=':', alpha=0.5, linewidth=0.5)
    ax.add_feature(cfeature.LAND, color="#D9D7D3")
    # ax.add_feature(cfeature.LAKES, color='#7ABAEC', zorder=0)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.OCEAN, color='#7ABAEC', zorder=0)
    gl = ax.gridlines(draw_labels=False, linewidth=.1, color='#7D6E63', alpha=0.5, x_inline=False, y_inline=False)
    gl.top_labels = False
    gl.right_labels = False
    return ax

from matplotlib.ticker import FuncFormatter

def percent_formatter(x, pos):
    return f"{int(x)}%"

def thousands_formatter(x, pos):
    return f"{int(x/1000)} k"

formatters = [percent_formatter, thousands_formatter, thousands_formatter]

for i, var in enumerate(variables):
    ax = axs[i]
    summary_gdf.plot(column=var, ax=ax, legend=True,
                     vmin=0,
                     cmap="OrRd",
                     linewidth=0.5,
                     edgecolor="k",
                     legend_kwds={
                         "shrink": 1.0, "orientation": "horizontal",
                         "pad": 0.025,
                         "format": FuncFormatter(formatters[i])
                     }
    )
    add_geofeatures(ax);
    ax.set_title(titles[i])
# %%
summary_gdf['subregion'].unique()
# %%
