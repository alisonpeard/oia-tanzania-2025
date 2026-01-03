#%%

import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd

path = "~/Desktop/tza_school_roads_hazard_disruption_summary.csv"
admin_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_1.gpkg"
crit_path = "~/Desktop/tza_school_roads_edge_criticality.csv" # use this to get % lost access

#%%
admin = gpd.read_file(admin_path)
admin["province"] = admin["shapeName"].str.lower()
admin.head()

# %%

# assign each road to a province
roads_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"
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

summary = pd.read_csv(path)
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
import seaborn as sns

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
    aspect=2
)
plt.yscale("log")
plt.title(f"Total detour time for all at-risk school journeys from {hazard}")
plt.ylabel("Aggregate detour time (walking hrs)")
plt.xlabel("Hazard type")
plt.tight_layout()

# %%

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
summary_single.head()
# %%
summary_gdf = pd.merge(summary_single, admin[["province", "geometry"]],
                       left_on="subregion", right_on="province", how="inner")
summary_gdf = pd.merge(summary_gdf, base[["base_flux", "subregion"]], on="subregion", how="left")
# %%
summary_gdf = gpd.GeoDataFrame(summary_gdf, geometry="geometry", crs=admin.crs)
summary_gdf.head()
# %%
import cartopy.crs as ccrs
import cartopy.feature as cfeature

fig, axs = plt.subplots(1, 3, figsize=(12, 3),
                        subplot_kw={"projection": ccrs.PlateCarree()})

variables = ["base_flux", "total_isolated", "total_weighted_detour_hrs"]
titles = ["Base", "Total Isolated", "Total Detour Time (walking hrs)"]

summary_gdf["percent_disrupted"] = (summary_gdf["total_isolated"] + summary_gdf["total_rerouted"]) / summary_gdf["base_flux"] * 100
for i, var in enumerate(variables):
    ax = axs[i]
    admin.boundary.plot(ax=ax, edgecolor="lightgrey")
    summary_gdf.plot(column=var, ax=ax, legend=True,
                     vmin=0,
                     cmap="OrRd")
    # ax.add_feature(cfeature.COASTLINE)
    # ax.add_feature(cfeature.BORDERS, linestyle=':')
    ax.set_title(titles[i])
# %%
summary_gdf['subregion'].unique()
# %%
