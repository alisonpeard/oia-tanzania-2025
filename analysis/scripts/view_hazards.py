# %%
import os
import matplotlib.pyplot as plt
import cmocean.cm as cmo
import cartopy.crs as ccrs
import xarray as xr
import rioxarray as rxr
import cartopy.feature as cfeature

import utils

hazdir = os.path.join("..", "..", "results", "hazards", "aligned")
hazfiles = os.listdir(hazdir)

fluvial = [f for f in hazfiles if f.startswith('fluvial')]
pluvial = [f for f in hazfiles if f.startswith('pluvial')]
coastal = [f for f in hazfiles if f.startswith('coastal')]
landslide = [f for f in hazfiles if f.startswith('landslide')]
cyclone = [f for f in hazfiles if f.startswith('cyclone')]
tasmax = [f for f in hazfiles if f.startswith('tasmax')]
hd35 = [f for f in hazfiles if f.startswith('hd35')]

hazards = [fluvial, pluvial, coastal, landslide, cyclone, tasmax, hd35]
cmaps = ["Blues", "Blues", "Blues", cmo.amp, cmo.speed, "YlOrRd", "YlOrRd"]

# %%


config = utils.load_config()
bbox = config["bbox"]


fig, axs = plt.subplots(2, 4, figsize=(12, 6),
                        subplot_kw={'projection': ccrs.PlateCarree()})

for ax, hazlist, cmap in zip(axs.flat, hazards, cmaps):
    haz = sorted(hazlist)[-1]
    hazpath = os.path.join(hazdir, haz)
    hazstem = haz.replace('.tif', '')
    hazinfo = utils.extract_hazard_info(hazstem)
    print(' '.join(hazinfo))

    # plot in compatibile way with rioxarray
    data = rxr.open_rasterio(hazpath, masked=True).squeeze()
    data = data.coarsen(x=500, y=500, boundary='trim').mean()
    
    data.plot(ax=ax, cmap=cmap, add_colorbar=True, 
                cbar_kwargs={'fraction':0.046, 'pad':0.04},
                rasterized=True)
    
    ax.set_title(' '.join(hazinfo))

for ax in axs.flat:
    ax.label_outer()
    ax.add_feature(cfeature.BORDERS, linestyle=':')
    ax.add_feature(cfeature.COASTLINE)
    ax.set_extent(bbox)
    ax.add_feature(cfeature.OCEAN)

fig.savefig("/Users/alison/Desktop/tza_aligned_hazards.pdf", bbox_inches='tight')
# %%


aoi = [38.5, 40.0, -8.5, -6.0]

fig, axs = plt.subplots(2, 4, figsize=(12, 6),
                        subplot_kw={'projection': ccrs.PlateCarree()})

for ax, hazlist, cmap in zip(axs.flat, hazards, cmaps):
    haz = sorted(hazlist)[-1]
    hazpath = os.path.join(hazdir, haz)
    hazstem = haz.replace('.tif', '')
    hazinfo = utils.extract_hazard_info(hazstem)
    print(' '.join(hazinfo))

    # plot in compatibile way with rioxarray
    data = rxr.open_rasterio(hazpath, masked=True).squeeze()
    data = data.rio.clip_box(minx=aoi[0], miny=aoi[2], maxx=aoi[1], maxy=aoi[3])
    data = data.coarsen(x=100, y=100, boundary='trim').mean()
    
    data.plot(ax=ax, cmap=cmap, add_colorbar=True, 
                cbar_kwargs={'fraction':0.046, 'pad':0.04},
                rasterized=True)
    
    ax.set_title(' '.join(hazinfo))

for ax in axs.flat:
    ax.set_extent(aoi)
    ax.label_outer()
    ax.add_feature(cfeature.BORDERS, linestyle=':')
    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.OCEAN)

fig.savefig("/Users/alison/Desktop/tza_aligned_hazards_zoom.pdf", bbox_inches='tight')
# %%
