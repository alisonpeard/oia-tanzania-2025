"""Rough work for network edges."""
# %% Make edges subregion
import os
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

def add_context(ax):
    ax.add_feature(cfeature.LAND, zorder=0, facecolor="lightgray")
    ax.add_feature(cfeature.OCEAN, zorder=0, facecolor="lightblue")
    ax.add_feature(cfeature.COASTLINE, zorder=1)
    ax.add_feature(cfeature.RIVERS, zorder=1, edgecolor="lightblue")


fig_kws = {"transparent": True, "bbox_inches": "tight", "dpi": 300}

datadir = "/Users/alison/Local/data/oia-tanzania-2025/input/assets/geoparquets"
figdir = "../figures/inputs"
os.listdir(datadir)
os.makedirs(figdir, exist_ok=True)

# %% railway
edges = gpd.read_parquet(os.path.join(datadir, "tza_railway_edges.parquet")).to_crs(4326)
nodes = gpd.read_parquet(os.path.join(datadir, "tza_railway_nodes.parquet")).to_crs(4326)

fig, ax = plt.subplots(figsize=(5, 5), subplot_kw={"projection": ccrs.PlateCarree()})
edges.plot(ax=ax, color="blue")
nodes.plot(ax=ax, color="red")
ax.set_title("Railway Network")
add_context(ax)
fig.savefig(os.path.join(figdir, "tza_railway_network.png"), **fig_kws)

# %% roads
edges = gpd.read_parquet(os.path.join(datadir, "tza_roads_edges.parquet")).to_crs(4326)
nodes = gpd.read_parquet(os.path.join(datadir, "tza_roads_nodes.parquet")).to_crs(4326)

fig, ax = plt.subplots(figsize=(5,5), subplot_kw={"projection": ccrs.PlateCarree()})
edges.plot(ax=ax, color="blue")
nodes.plot(ax=ax, color="red")
ax.set_title("Road Network")
add_context(ax)
fig.savefig(os.path.join(figdir, "tza_road_network.png"), **fig_kws)

# %% maritime_ports
edges = gpd.read_parquet(os.path.join(datadir, "tza_maritime_ports_edges.parquet")).to_crs(4326)
nodes = gpd.read_parquet(os.path.join(datadir, "tza_maritime_ports_nodes.parquet")).to_crs(4326)
polygons = gpd.read_parquet(os.path.join(datadir, "tza_maritime_ports_polygons.parquet")).to_crs(4326)


fig, ax = plt.subplots(figsize=(5, 5), subplot_kw={"projection": ccrs.PlateCarree()})
nodes.plot(ax=ax, color="red")
edges.plot(ax=ax, color="blue")
ax.set_title("Maritime Ports Network")
add_context(ax)
fig.savefig(os.path.join(figdir, "tza_maritime_ports_network.png"), **fig_kws)
plt.show()

fig, ax = plt.subplots(figsize=(5, 5), subplot_kw={"projection": ccrs.PlateCarree()})
polygons.iloc[[0]].plot(ax=ax, color="blue", alpha=0.5, edgecolor="black")
ax.set_title("Maritime Ports Polygon")
add_context(ax)
fig.savefig(os.path.join(figdir, "tza_maritime_ports_polygon_sample.png"), **fig_kws)

# %% airports
polygons = gpd.read_parquet(os.path.join(datadir, "tza_airports_polygons.parquet")).to_crs(4326)

fig, ax = plt.subplots(figsize=(5, 5), subplot_kw={"projection": ccrs.PlateCarree()})
polygons.iloc[[0]].plot(ax=ax, color="blue", alpha=0.5, edgecolor="black")
ax.set_title("Airport Polygon")
add_context(ax)
fig.savefig(os.path.join(figdir, "tza_airport_polygon_sample.png"), **fig_kws)

# %% iww_ports
nodes = gpd.read_parquet(os.path.join(datadir, "tza_iww_ports_nodes.parquet")).to_crs(4326)
edges = gpd.read_parquet(os.path.join(datadir, "tza_iww_ports_edges.parquet")).to_crs(4326)
polygons = gpd.read_parquet(os.path.join(datadir, "tza_iww_ports_polygons.parquet")).to_crs(4326)

fig, ax = plt.subplots(figsize=(5, 5), subplot_kw={"projection": ccrs.PlateCarree()})
nodes.plot(ax=ax, color="red")
edges.plot(ax=ax, color="blue")
ax.set_title("IWW Ports Network")
add_context(ax)
fig.savefig(os.path.join(figdir, "tza_iww_ports_network.png"))
plt.show()

fig, ax = plt.subplots(figsize=(5, 5), subplot_kw={"projection": ccrs.PlateCarree()})
polygons.iloc[[0]].plot(ax=ax, color="blue", alpha=0.5,  edgecolor="black")
ax.set_title("IWW Ports Polygon")
add_context(ax)
fig.savefig(os.path.join(figdir, "tza_iww_ports_polygon_sample.png"), **fig_kws)
# %%
