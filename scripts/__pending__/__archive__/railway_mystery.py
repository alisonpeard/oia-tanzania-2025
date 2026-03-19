"""
NOTE: roughwork, delete this once solved.
Why are railway results different in the new results. Luckily I made a backup of 
the old results data, so I can compare the two... 🤞
"""
# %%
import pandas as pd
import geopandas as gpd
from pathlib import Path
from glob import glob
import os
from ttra import helpers


asset = "tza_railway_edges"
hazard = "pluvial"

old_dir = Path(f'/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/results/__backup__/intersections (20-01-2026)/{asset}')
new_dir = Path(f'/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/results/intersections/{asset}')

old_dir = old_dir / hazard
new_dir = new_dir / hazard

old = helpers.load_risk_profile(old_dir, verbose=True)
new = helpers.load_risk_profile(new_dir, verbose=True)

def format_id(id):
    return '_'.join(id.split('_')[:2])

new["id"] = new["id"].apply(format_id)
old["id"] = old["id"].apply(format_id)
# %%
old_ids = set(old["id"])
new_ids = set(new["id"])

len(old_ids), len(new_ids)
# %%
old_only = old_ids - new_ids
new_only = new_ids - old_ids

len(old_only), len(new_only)

shared_ids = old_ids.intersection(new_ids)
# %% compare columns
metric = ["hazard"]#, "defended", "damage", "cost"]

sums = []
for m in metric:
    mcols_new = set([col for col in new.columns if col.startswith(m)])
    mcols_old = set([col for col in old.columns if col.startswith(m)])

    if mcols_new != mcols_old:
        print(f"{m} columns don't match between old and new results")
        print(f"old only: {mcols_old - mcols_new}")
        print(f"new only: {mcols_new - mcols_old}")

    mcols = list(mcols_new.intersection(mcols_old))

    for col in mcols:
        oldsum = old[col].sum()
        newsum = new[col].sum()
        newsubold = newsum - oldsum
        sums.append((col, oldsum, newsum, newsubold))

# so they are all the same :)
df = pd.DataFrame(sums, columns=["metric", "oldsum", "newsum", "diff"]).round(2)
df = df[df["diff"] != 0].sort_values(by="diff", ascending=False)
# %%
hazcol = df["metric"].iloc[-1]

old_haz = old.set_index('id')[[hazcol]].sort_index()
new_haz = new.set_index('id')[[hazcol]].sort_index()

old_ids = set(old_haz.index)
new_ids = set(new_haz.index)
shared_ids = old_ids.intersection(new_ids)

old_haz = old_haz.loc[list(shared_ids)]
new_haz = new_haz.loc[list(shared_ids)]

old_haz = old_haz.groupby("id")[hazcol].sum()
new_haz = new_haz.groupby("id")[hazcol].sum()

print(f"Old hazard sums: {len(old_haz)}, New hazard sums: {len(new_haz)}")

diff_haz = new_haz - old_haz
diff_haz = diff_haz[diff_haz != 0]
if len(diff_haz) == 0:
    print("No differences in hazard sums between old and new results")

# %%
diff_haz.sort_values(ascending=True)
# %% plot the diffs
path = Path(f'/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/snakemake/input/assets/{asset}.geoparquet')
gdf = gpd.read_parquet(path).to_crs(epsg=4326)

path = Path(f'/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/snakemake/input/admin/level01.geoparquet')
admin = gpd.read_parquet(path).to_crs(epsg=4326)

hazdir = Path('/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/snakemake/input/hazards')

# %%
import xarray as xr
from rioxarray.xarray_plugin import RasterioBackend

hazfile = hazcol.replace("hazard-", "") + ".tif"
haz = xr.open_dataset(hazdir / hazfile, engine=RasterioBackend)
# haz = haz.coarsen(x=50, y=50, boundary="trim").max()
# %%
vmax = max(diff_haz.max(), -diff_haz.min())
vmin = -vmax
gdf = gdf.set_index("id").loc[diff_haz.index].reset_index()
gdf["diff_haz"] = diff_haz.values

import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cmocean.cm as cmo

idx = gdf.sort_values("diff_haz", ascending=True).id[0]
print(f"Plotting id: {idx} with diff: {gdf.set_index('id').loc[idx, 'diff_haz']}")

new_sub = new.set_index("id").loc[idx]
old_sub = old.set_index("id").loc[idx]

print(type(new.set_index("id").loc[idx]))

if isinstance(new_sub, pd.Series):
    new_sub = new.set_index("id").loc[[idx]]

if isinstance(old_sub, pd.Series):
    old_sub = old.set_index("id").loc[[idx]]

new_sub = new_sub.to_crs(epsg=4326)
old_sub = old_sub.to_crs(epsg=4326)
extent = new_sub.geometry.total_bounds

xmin, ymin, xmax, ymax = extent
xmin -= 0.1
xmax += 0.1
ymin -= 0.1
ymax += 0.1

# clip haz to the extent of the road segment
haz_clipped = haz.rio.clip_box(xmin, ymin, xmax, ymax)

haz_vmin = haz_clipped.band_data.min().item()
haz_vmax = haz_clipped.band_data.max().item()

line_vmin = min(old_sub[hazcol].min(), new_sub[hazcol].min())
line_vmax = max(old_sub[hazcol].max(), new_sub[hazcol].max())

# add proportional buffer to line limits
line_vmin -= 0.5 * abs(line_vmax - line_vmin)
line_vmax += 0.5 * abs(line_vmax - line_vmin)

fig, axs = plt.subplots(2, 1, figsize=(10, 7), subplot_kw={"projection": ccrs.PlateCarree()})

for ax in axs:
    ax.set_extent([xmin, xmax, ymin, ymax], crs=ccrs.PlateCarree())
    admin.boundary.to_crs(4326).plot(ax=ax, color="k", linewidth=0.1, zorder=1)
    haz_clipped.band_data.plot(ax=ax, cmap=cmo.deep, alpha=1.0, add_colorbar=True, zorder=0, vmin=haz_vmin, vmax=haz_vmax)

ax = axs[0]
gdf.to_crs(4326).set_index("id").loc[[idx]].plot(color="k", ax=ax, zorder=4, lw=3)
gdf.to_crs(4326).set_index("id").loc[[idx]].plot(color="crimson", ax=ax, zorder=5, lw=1.5)
old_sub.plot(hazcol, cmap=cmo.deep, zorder=6, ax=ax, lw=2, legend=True, vmin=line_vmin, vmax=line_vmax)

ax = axs[1]
gdf.to_crs(4326).set_index("id").loc[[idx]].plot(color="k", ax=ax, zorder=4, lw=3)
gdf.to_crs(4326).set_index("id").loc[[idx]].plot(color="crimson", ax=ax, zorder=5, lw=1.5)
new_sub.plot(hazcol, cmap=cmo.deep, zorder=6, ax=ax, lw=2, legend=True, vmin=line_vmin, vmax=line_vmax)

plt.tight_layout()

print(f"Old value: {old_haz.loc[idx]}, New value: {new_haz.loc[idx]}")
# %%

old_haz.loc[idx]
# %%
new_haz.loc[idx]
# %%
new_sub
# %%
old_sub
# %%
