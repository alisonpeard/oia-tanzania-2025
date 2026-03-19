"""Now that I know the issue (see notes)
try to find out *why* it's happening.
"""
# %%
import os
from glob import glob
from tqdm import tqdm
from pathlib import Path
import pandas as pd
import geopandas as gpd
from warnings import warn
from itertools import product

import ttra
from oi_risk import config as cfg


def parent_id(x:str) -> str:
    return "_".join(x.split("_")[:-1])

def child_id(x:str) -> str:
    return x.split("_")[-1]


idx = "raile_666602220209"
hazard = "pluvial"
asset = "tza_railway_edges"
subregion = "singida"

config = cfg.load_config()
indir = Path(config['paths']['snakemake']) / "input"
tmpdir  = Path(config["paths"]["snakemake"]) / "temp"
outdir = Path(config['paths']['snakemake']) / "results" / "intersections" / asset / hazard
resdir = Path(config['paths']['results']) / "intersections" / asset / hazard

tmpdir1 = Path('/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/snakemake/__backup__/temp (backup)')
outdir1 = Path('/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/results/__backup__/intersections (20-01-2026)') / asset / hazard
resdir1 = Path('/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/results/__backup__/intersections (20-01-2026)') / asset / hazard
path = Path(f'/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/snakemake/input/admin/level01.geoparquet')
admin = gpd.read_parquet(path).to_crs(epsg=4326)


# %% inspect the input data
inpath = indir / "assets" / (asset + ".geoparquet")
inp = gpd.read_parquet(inpath).to_crs(epsg=4326)
inp = inp[inp['id'] == idx].copy()
print(f"{len(inp[inp['id'] == idx])} features with id = {idx} in the input data")

# %% inspect data split along subregions
tmpfiles = glob(str(tmpdir / "assets" / asset / "*.geoparquet"))
tmps = []
for f in tqdm(tmpfiles):
    tmp = gpd.read_parquet(f)
    tmp["subregion"] = Path(f).stem
    tmps.append(tmp)
tmp0 = pd.concat(tmps, ignore_index=True)
tmp0["child_id"] = tmp0["id"].apply(child_id)
tmp0["parent_id"] = tmp0["id"].apply(parent_id)
print(f"\n{len(tmp0[tmp0['id'] == idx])} features with id = {idx} in the temp data")
print(f"{len(tmp0[tmp0['parent_id'] == idx])} features with parent_id = {idx} in the temp data")
tmp0 = tmp0[tmp0["parent_id"] == idx].copy().reset_index(drop=True)
print(f"{tmp0.duplicated().sum()} duplicated rows in the backup temp data")
tmp0.plot("subregion")
# ^^ NOTE: It was split... so why does it have "_0" for both child ids?

tmpfiles = glob(str(tmpdir1 / "assets" / asset / "*.geoparquet"))
for f in tqdm(tmpfiles):
    tmp = gpd.read_parquet(f)
    tmp["subregion"] = Path(f).stem
    tmps.append(tmp)
tmp1 = pd.concat(tmps, ignore_index=True)
tmp1["child_id"] = tmp1["id"].apply(child_id)
tmp1["parent_id"] = tmp1["id"].apply(parent_id)

print(f"\n{len(tmp1[tmp1['id'] == idx])} features with id = {idx} in the backup temp data")
print(f"{len(tmp1[tmp1['parent_id'] == idx])} features with parent_id = {idx} in the backup temp data")
tmp1 = tmp1[tmp1["parent_id"] == idx].copy()
print(f"{tmp1.duplicated().sum()} duplicated rows in the backup temp data")
tmp1 = tmp1.drop_duplicates().reset_index(drop=True)
tmp1.plot("subregion")

# check equality of the two dataframes
if tmp0.equals(tmp1):
    print("The two dataframes are identical.")
else:
    print("The two dataframes are NOT identical.")

"""
So at least down to to here, the data is identical.
"""
# %% inspect the intersected data
outfiles = glob(str(outdir / "*" / "profile.geoparquet"))
outs = []
for f in tqdm(outfiles):
    out = gpd.read_parquet(f).reset_index(drop=False)
    out["subregion"] = Path(f).parent.stem
    outs.append(out)
out0 = pd.concat(outs, ignore_index=True)
out0["child_id"] = out0["id"].apply(child_id)
out0["parent_id"] = out0["id"].apply(parent_id)
out0 = out0[out0["parent_id"] == idx].copy()
out0.plot("subregion")
print(f"{len(out0)} features with id = {idx} in the output data")
# ^^ NOTE: Some hazards are nan, which is strange; they shouldn't be.

# load older data
outfiles = glob(str(outdir1 / "*" / "profile.geoparquet"))
outs = []
for f in tqdm(outfiles):
    out = gpd.read_parquet(f).reset_index(drop=False)
    out["subregion"] = Path(f).parent.stem
    outs.append(out)
out1 = pd.concat(outs, axis=0, ignore_index=True)
out1 = out1.sort_values(by="id").reset_index(drop=True)

out1 = out1[out1["id"] == idx].copy()
out1.plot("subregion")
print(f"{len(out1)} features with id = {idx} in the output data")

"""
So here it is clearer, out1 (the older results) have not split the asset.
The older data kept the full asset and duplicated it for each subregion. While
the newer data split the asset and only kept intersection geometries in each
subregion. However, the NaN status doesn't make sense...

Why does the asset in Singida have NaN hazard levels when the hazard is
non-zero?
"""

# %% let's look at the rasters used

import xarray as xr
from rioxarray.xarray_plugin import RasterioBackend

extent = out0.total_bounds
xmin, ymin, xmax, ymax = extent
xmin -= 0.1
xmax += 0.1
ymin -= 0.1
ymax += 0.1

hazstem = "pluvial_2050_ssp126_rp01000"

def load_tiff(path:Path) -> xr.Dataset:
    return xr.open_dataset(path, engine=RasterioBackend)

haz0 = load_tiff(indir / "hazards" / (hazstem + ".tif"))
haz1 = load_tiff(tmpdir / "hazards" / (hazstem + ".tif"))
haz2 = load_tiff(tmpdir1 / "hazards" / (hazstem + ".tif"))

# %%
haz0_clipped = haz0.rio.clip_box(*extent).band_data
haz1_clipped = haz1.rio.clip_box(*extent).band_data
haz2_clipped = haz2.rio.clip_box(*extent).band_data
# %%
import cartopy.crs as ccrs
import matplotlib.pyplot as plt

fig, axs = plt.subplots(
    2, 1, figsize=(8, 4),
    subplot_kw={"projection": ccrs.PlateCarree()}
)

ax = axs[0]
haz0_clipped.plot(ax=ax, cmap="Blues")
# haz1_clipped.plot(ax=ax, cmap="Blues")
out0.plot('hazard-' + hazstem, ax=ax, legend=True)

ax = axs[1]
haz2_clipped.plot(ax=ax, cmap="Blues")
out1.plot('hazard-' + hazstem, ax=ax, legend=True)

for ax in axs:
    ax.set_title("")

print(f"{haz0.rio.bounds()=}")
print(f"{haz1.rio.bounds()=}")
print(f"{haz2.rio.bounds()=}")
print(f"{out0.total_bounds=}")
print(f"{out1.total_bounds=}")
print(f"{extent=}")
print(f"{out0.crs=}")
print(f"{out1.crs=}")
print(f"{haz0.rio.crs=}")
print(f"{haz1.rio.crs=}")
print(f"{haz2.rio.crs=}")
# %%


# %%
# isolate the file
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import xarray as xr
from rioxarray.xarray_plugin import RasterioBackend

path = "/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/snakemake/results/intersections/tza_railway_edges/pluvial/singida/profile.geoparquet"
hazstem = "pluvial_2050_ssp126_rp01000"
tmpdir  = Path(config["paths"]["snakemake"]) / "temp"

gdf = gpd.read_parquet(path).reset_index()
gdf['parent_id'] = gdf['id'].apply(parent_id)
gdf = gdf[gdf['parent_id'] == idx].copy()

extent = gdf.total_bounds
xmin, ymin, xmax, ymax = extent
xmin -= 0.1
xmax += 0.1
ymin -= 0.1
ymax += 0.1

def load_tiff(path:Path) -> xr.Dataset:
    return xr.open_dataset(path, engine=RasterioBackend)

haz0 = load_tiff(tmpdir / "hazards" / (hazstem + ".tif"))

fig, axs = plt.subplots(
    2, 1,figsize=(8, 4),
    subplot_kw={"projection": ccrs.PlateCarree()}
)

ax = axs[0]
haz0_clipped.plot(ax=ax, cmap="Blues")

ax = axs[1]
haz0_clipped.plot(ax=ax, cmap="Blues")
gdf.plot(color='k', lw=3, ax=ax)
gdf.plot('hazard-' + hazstem, lw=2, ax=ax)
ax.set_title("")

print(f"{haz0.rio.bounds()=}")
print(f"{haz1.rio.bounds()=}")
print(f"{haz2.rio.bounds()=}")
print(f"{out0.total_bounds=}")
print(f"{out1.total_bounds=}")
print(f"{extent=}")
print(f"{out0.crs=}")
print(f"{out1.crs=}")
print(f"{haz0.rio.crs=}")
print(f"{haz1.rio.crs=}")
print(f"{haz2.rio.crs=}")

print(gdf['defended-' + hazstem])
# %%

hazcols = [c for c in gdf.columns if c.startswith("hazard-")]
gdf[hazcols]
# %%
