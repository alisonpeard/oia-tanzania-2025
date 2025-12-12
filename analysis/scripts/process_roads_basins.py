"""Intersect roads with HydroBASINS and save output."""
# %%
import os
import numpy as np
import geopandas as gpd

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from colours import map_colours

CRS = 32735

roads_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet" # temp
basins_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/basins/basins_clipped_to_admin.gpkg"
basins_unclipped_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/basins/basins_notclipped_to_admin.gpkg"
outpath = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/basins/tza_roads_edges_with_basins.geoparquet"

roads = gpd.read_parquet(roads_path)
basins = gpd.read_file(basins_path)

colnames = basins.columns
colnames = [col.lower() for col in colnames]

def criteria(colname:str) -> bool:
    """Check if column name matches criteria for hybas columns."""
    return colname.startswith("hybas_") or colname in [
        "geometry"
    ]

colnames = ["hybas_" + col if not criteria(col) else col for col in colnames]
basins.columns = colnames
if roads.crs != basins.crs:
    print(f"{roads.crs=} != {basins.crs=}, reprojecting basins to roads CRS.")
    basins = basins.to_crs(roads.crs)
else:
    print("CRS match, no reprojection needed.")

basins["hybas_id"] = basins["hybas_id"].astype(str)

roads_with_basins = gpd.overlay(roads, basins, how="intersection")


roads_with_basins = roads_with_basins.to_crs(CRS)
roads_with_basins.to_parquet(outpath)

basins = basins.to_crs(epsg=4326)
roads_with_basins = roads_with_basins.to_crs(epsg=4326)

fig, axs = plt.subplots(1, 2, figsize=(20,10), subplot_kw={'projection': ccrs.PlateCarree()})

# Create shuffled color mapping
unique_basins = basins['hybas_id'].unique()
np.random.shuffle(unique_basins)
color_map = {basin_id: i for i, basin_id in enumerate(unique_basins)}

# Apply to both datasets
basins['color_id'] = basins['hybas_id'].map(color_map)
roads_with_basins['color_id'] = roads_with_basins['hybas_id'].map(color_map)

# plot the basins
cmap = "gist_earth"
ax = axs[0]
basins.plot(column="color_id", figsize=(10,10), ax=ax, cmap=cmap, legend=False)
ax.set_title("Basins")

ax = axs[1]
roads_with_basins.plot(column="color_id", figsize=(10,10), ax=ax, cmap=cmap, legend=False)

ax.set_title("Roads with Basins")

for ax in axs:
    ax.add_feature(cfeature.BORDERS, color=map_colours["geoboundaries"])
    ax.add_feature(cfeature.COASTLINE, color=map_colours["geoboundaries"])
    ax.add_feature(cfeature.OCEAN, color=map_colours["permwater"])
    ax.add_feature(cfeature.LAND, color=map_colours["background"])
# %%
figdir = "../figures/inputs/tza_roads_basins.png"
fig.savefig(figdir, dpi=300, bbox_inches="tight", transparent=True)
# %%
