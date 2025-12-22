# %%
import os
import pandas as pd
import matplotlib.pyplot as plt
import cmocean.cm as cmo
import cartopy.crs as ccrs
import xarray as xr
import rioxarray as rxr
import cartopy.feature as cfeature
import geopandas as gpd
from shapely.geometry import box
from matplotlib.colors import CenteredNorm


def add_geofeatures(ax):
    ax.add_feature(cfeature.BORDERS, color='k', linestyle=':', alpha=0.5, linewidth=0.5)
    ax.add_feature(cfeature.LAND, color="#D9D7D3")
    ax.add_feature(cfeature.LAKES, color='#7ABAEC', zorder=100)
    ax.add_feature(cfeature.RIVERS, edgecolor='#7ABAEC', zorder=100)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, zorder=100)
    ax.add_feature(cfeature.OCEAN, color='#7ABAEC', zorder=100)
    gl = ax.gridlines(draw_labels=True, linewidth=.1, color='#7D6E63', alpha=0.5, x_inline=False, y_inline=False)
    gl.top_labels = False
    gl.right_labels = False
    return ax


HAZARD = "hd35"
hazA = f"/Volumes/Expansion/02_oia/oia-tanzania-2025/results/hazards/aligned/{HAZARD}_2030_rcp85_rp00100.tif"
hazB = f"/Volumes/Expansion/02_oia/oia-tanzania-2025/results/hazards/aligned/{HAZARD}_2080_rcp85_rp00100.tif"
admin_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_0.gpkg"

cmaps = {
    "pluvial": cmo.delta_r,
    "fluvial": cmo.delta_r,
    "coastal": cmo.delta_r,
    "landslide": "coolwarm",
    "cyclone": "coolwarm",
    "hd35": "OrRd",
    "tasmax": "OrRd",
}
cmap = cmaps[HAZARD]

print("Loading data...")
admin = gpd.read_file(admin_path).to_crs(epsg=4326)
datA = rxr.open_rasterio(hazA, masked=True).squeeze()
datB = rxr.open_rasterio(hazB, masked=True).squeeze()

print("Resampling data...")
# resample so it doesn't take forever to plot
datA = datA.coarsen(x=500, y=500, boundary='trim').mean()
datB = datB.coarsen(x=500, y=500, boundary='trim').mean()

print("Calculating delta...")
delta = datB - datA

print("Preparing data for plotting...")
datA = datA.where(datA != 0)
datB = datB.where(datB != 0)
delta = delta.where(delta != 0)

print("Plotting data...")
bbox = datA.rio.bounds()
left, bottom, right, top = bbox
fig, ax = plt.subplots(
    1, 1, figsize=(6, 4),
    subplot_kw={'projection': ccrs.PlateCarree()}
)

nrm = CenteredNorm(vcenter=0, halfrange=max(abs(delta.min()), abs(delta.max())))

im = delta.plot(
    ax=ax, cmap=cmap, norm=nrm, add_colorbar=True,
    cbar_kwargs={
        'fraction':0.046, 'pad':0.04, 'label': "days",
        'orientation':'horizontal', 'shrink': 0.8,
    },
    rasterized=True
)
ax = add_geofeatures(ax)
ax.set_extent([left, right, bottom, top], crs=ccrs.PlateCarree())
plt.setp(im.colorbar.ax.get_xticklabels(), rotation=20, ha='center')
# %%