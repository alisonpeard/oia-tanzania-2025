# %%
import os
import pandas as pd
import matplotlib.pyplot as plt
import cmocean.cm as cmo
import cartopy.crs as ccrs
import xarray as xr
import rioxarray as rxr
import cartopy.feature as cfeature

import yaml

def load_config(path=None):
    path = path or os.path.join("..", "..", "workflow", "config.yaml")
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg

def extract_hazard_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract hazard, epoch, scenario, and return period from hazard column name."""
    # prefix, parts = hazcol.split("-")
    parts = hazcol.split("_")
    hazard = parts[0]
    epoch = parts[1]
    scenario = parts[2]
    rp = str(int(parts[3].replace("rp", "")))
    if len(parts) > 4:
        stat = "_".join(parts[4:])
    else:
        stat = ""
    return "hazard", hazard, epoch, scenario, rp, stat


def find_hazard(hazlist, epochs, scenarios, rps):
    for haz in hazlist:
        hazstem = haz.replace('.tif', '')
        hazinfo = extract_hazard_info(hazstem)
        for epoch in epochs:
            for scenario in scenarios:
                for rp in rps:
                    if hazinfo[2] == epoch and hazinfo[3] == scenario and hazinfo[4] == str(rp):
                        return haz
    print(f"WARNING: no hazard found for epochs {epochs}, scenarios {scenarios}, rps {rps} in list {hazlist}")
    return None

# hazdir = os.path.join("..", "..", "results", "hazards", "input")
hazdir = "/Volumes/Expansion/02_oia/oia-tanzania-2025/intermediate/hazards/input"
admin_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_0.gpkg"

hazfiles = os.listdir(hazdir)

fluvial   = [f for f in hazfiles if f.startswith('fluvial')]
pluvial   = [f for f in hazfiles if f.startswith('pluvial')]
coastal   = [f for f in hazfiles if f.startswith('coastal')]
landslide = [f for f in hazfiles if f.startswith('landslide')]
cyclone   = [f for f in hazfiles if f.startswith('cyclone')]
tasmax    = [f for f in hazfiles if f.startswith('tasmax')]
hd35      = [f for f in hazfiles if f.startswith('hd35')]

scenarios = ["ssp245", "rcp45"]
epochs = ["2050"]
rps = [100, 250]

fluvial   = [find_hazard(fluvial, epochs, scenarios, rps)]
pluvial   = [find_hazard(pluvial, epochs, scenarios, rps)]
coastal   = [find_hazard(coastal, epochs, scenarios, rps)]
landslide = [find_hazard(landslide, epochs, scenarios, rps)]
cyclone   = [find_hazard(cyclone, epochs, scenarios, rps)]
tasmax    = [find_hazard(tasmax, epochs, scenarios, rps)]
hd35      = [find_hazard(hd35, epochs, scenarios, rps)]

print(f"Extracted hazards: {fluvial}, {pluvial}, {coastal}, {landslide}, {cyclone}, {tasmax}, {hd35}")

hazards = [
    fluvial, pluvial, coastal,
    landslide,
    cyclone,
    tasmax, hd35
]
cmaps = [
    "Blues", "Blues", "Blues",
    cmo.amp,
    cmo.speed,
    "OrRd", "OrRd"
]

units = [
    "flood depth (m)", "flood depth (m)", "flood depth (m)",
    "hazard score (0-0.7)",
    "wind speed (m/s)",
    "temperature (°C)", "days above 35°C"
]


config = load_config()
# bbox = config["bbox"]


import geopandas as gpd
from shapely.geometry import box

def aspect(hazard:str) -> float:
    # make it fatter and taller for coastal flooding
    if hazard == "coastal":
        return 8
    return 20

admin = gpd.read_file(admin_path).to_crs(epsg=4326)

for hazlist, cmap, unit in zip(hazards, cmaps, units):
    haz = sorted(hazlist)[-1]
    cmap = cmap

    fig, ax = plt.subplots(
        1, 1, figsize=(6, 4),
        subplot_kw={'projection': ccrs.PlateCarree()}
    )
    
    hazpath = os.path.join(hazdir, haz)
    hazstem = haz.replace('.tif', '')
    hazinfo = extract_hazard_info(hazstem)
    print(' '.join(hazinfo))

    # plot in compatibile way with rioxarray
    data = rxr.open_rasterio(hazpath, masked=True).squeeze()
    bbox = data.rio.bounds()
    left, bottom, right, top = bbox

    if hazinfo[1] in ["landslide", "pluvial", "fluvial", "coastal"]:
        data = data.coarsen(x=500, y=500, boundary='trim').mean()

    # mask out zero values
    data = data.where(data > 0)

    # data.plot.contourf(ax=ax, cmap=cmap, add_colorbar=True, levels=12,
    im = data.plot(ax=ax, cmap=cmap, add_colorbar=True, #levels=10,
                cbar_kwargs={'fraction':0.046, 'pad':0.04, 'label': unit,
                             'orientation':'horizontal', 'shrink': 0.8,
                             "aspect": aspect(hazinfo[1]),
                             },
                rasterized=True)
    # plt.setp(im.colorbar.ax.get_xticklabels(), rotation=20, ha='center')
    ax.set_title(f"{hazinfo[4]}-yr {hazinfo[1]} hazard\n({hazinfo[2]}, {hazinfo[3]})")

    # difference between admin and bbox
    bbox_geom = box(left, bottom, right, top)
    bbox_gdf = gpd.GeoDataFrame(geometry=[bbox_geom], crs="EPSG:4326")
    mask = gpd.overlay(bbox_gdf, admin, how='difference')
    mask.plot(ax=ax, color='lightgrey', alpha=1, zorder=998)

    # for ax in axs.flat:
    ax.label_outer()
    ax.set_extent(bbox)
    ax.add_feature(cfeature.BORDERS, linestyle=':', color="#666666", zorder=999)
    ax.add_feature(cfeature.COASTLINE, color="#666666", zorder=999)
    ax.add_feature(cfeature.LAND, color='lightgray')
    ax.add_feature(cfeature.OCEAN, zorder=1000)
    ax.add_feature(cfeature.LAKES, zorder=1000, linewidth=0.5, edgecolor="steelblue")
    ax.add_feature(cfeature.RIVERS, zorder=1000, linewidth=0.5, edgecolor="steelblue")

    # clip axis to raster extent
    left, bottom, right, top = data.rio.bounds()
    ax.set_xlim(left, right)
    ax.set_ylim(bottom, top)

    plt.tight_layout()

    os.makedirs("/Users/alison/Desktop/hazards/gridded", exist_ok=True)
    fig.savefig(
        f"/Users/alison/Desktop/hazards/gridded/{hazinfo[1]}.png",
        dpi=300, bbox_inches='tight', transparent=True
    )
    # break
    if hazinfo[1] == "coastal":
        break
# %%