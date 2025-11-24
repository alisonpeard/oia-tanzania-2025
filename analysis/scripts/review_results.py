"""
This script is for manually verifying that the intersection results look right.
"""

# %%
import os

import pandas as pd
import geopandas as gpd
import numpy as np
import xarray as xr
import rioxarray as rxr
from rasterio.features import shapes

from pprint import pprint
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature



# helper functions for working with hazard columns
def list_hazcols(exposure:gpd.GeoDataFrame) -> list[str]:
    """List hazard columns in exposure dataframe."""
    hazcols = [c for c in exposure.columns if c.startswith("hazard-")]
    return hazcols

def get_hazcol(hazard:str, epoch:int, scenario:str, rp:int) -> str:
    """Get hazard column name."""
    hazcol = f"hazard-{hazard}_{epoch}_{scenario}_rp{str(rp).zfill(5)}"
    return hazcol


def get_defendedcol(hazard:str, epoch:int, scenario:str, rp:int) -> str:
    """Get defended column name."""
    hazcol = f"defended-{hazard}_{epoch}_{scenario}_rp{str(rp).zfill(5)}"
    return hazcol

def extract_hazard_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract hazard, epoch, scenario, and return period from hazard column name."""
    parts = hazcol.replace("hazard-", "").split("_")
    hazard = parts[0]
    epoch = parts[1]
    scenario = parts[2]
    rp = int(parts[3].replace("rp", ""))
    return hazard, epoch, scenario, rp

def get_available_scenarios(exposure):
    """Get available hazards, epochs, scenarios, and return periods in exposure dataframe."""
    hazcols = list_hazcols(exposure)
    epochs = set()
    scenarios = set()
    hazards = set()
    rps = set()
    for hazcol in hazcols:
        hazard, epoch, scenario, rp = extract_hazard_info(hazcol)
        hazards.add(hazard)
        epochs.add(epoch)
        scenarios.add(scenario)
        rps.add(rp)
    return {
        "hazards": sorted(hazards),
        "epochs": sorted(epochs),
        "scenarios": sorted(scenarios),
        "rps": sorted(rps),
    }


def raster_to_geodataframe(raster:xr.DataArray) -> gpd.GeoDataFrame:
    data = raster[0].data
    transform = raster.rio.transform()
    mask = ~np.isnan(data)
    results = (
        {"properties": {"value": v}, "geometry": s}
        for i, (s, v) in enumerate(
            shapes(data, mask=mask, transform=transform)
        )
    )
    gdf = gpd.GeoDataFrame.from_features(results, crs="EPSG:4326")
    gdf = gdf.fillna(0.)
    # gdf = gdf[gdf["value"] > 0]
    return gdf


def verify_asset_geometries(idx, gdf, ref):
    assert gdf.crs.equals(ref.crs), "CRS do not match"
    segment = gdf.loc[idx]
    segment_ref = ref.loc[idx]
    assert segment.geometry.equals(segment_ref.geometry), "Geometries do not match"
    print("Geometries match.")


def verify_asset_exposure(idx, gdf, hazard, hazcol):
    segment = gdf.loc[[idx]]
    x0, y0, x1, y1 = segment.total_bounds
    hazard = hazard.rio.clip_box(minx=x0, miny=y0, maxx=x1, maxy=y1, allow_one_dimensional_raster=True)
    hazard = raster_to_geodataframe(hazard)
    intersection = gpd.overlay(segment, hazard, how="intersection")
    max_result_value = gdf.loc[idx, hazcol]
    max_raster_value = intersection["value"].max()
    assert np.isclose(max_raster_value, max_result_value), \
      f"Max hazard values do not match: {max_raster_value} (raster) != {max_result_value} (result)"
    print(f"Hazard values match. {max_raster_value} (raster) == {max_result_value} (result)")


def clip_da_to_asset(hazard, gdf):
    x0, y0, x1, y1 = gdf.total_bounds
    hazard = hazard.rio.clip_box(minx=x0, miny=y0, maxx=x1, maxy=y1, allow_one_dimensional_raster=True)
    return hazard

def mask_zero_values(da:xr.DataArray) -> xr.DataArray:
    da = da.where(da > 0)
    return da


# %% code starts here
# replace with path to file
subregion = "kilimanjaro"

profile = [
    ("nodes", "tza_roads_bridges_and_culverts", "masonry_arch_culvert_good"),
    ("edges", "tza_railway", "mgr_track_open"),
    ("polygons", "tza_airports", "airport"),
][0]

geometry, asset, asset_type = profile

hazard = "pluvial"
epoch = 2020
scenario = "historical"
rp = 200
plot = True


# %%
if __name__ == "__main__":
    # define the asset input files
    risk_file = f"../../results/risk/{geometry}/{asset}/{subregion}.geoparquet"
    ref_file = f"../../results/assets/{geometry}/{asset}/{subregion}.geoparquet"

    # load data
    risk = gpd.read_parquet(risk_file).to_crs(epsg=4326)  # ensure in WGS84
    ref = gpd.read_parquet(ref_file).set_index("id").to_crs(epsg=4326)
    print("Available hazards:")
    pprint(get_available_scenarios(risk))

    print("\nview results a specific hazard column:")
    hazcol = get_hazcol(hazard, epoch, scenario, rp)
    print(f"hazard column: {hazcol}")
    print(risk[hazcol].head(3))

    # define the hazard raster file
    hazard_file = hazcol.replace('hazard-', '') + '.tif'
    hazard_path = f"../../results/hazards/aligned/{hazard_file}"

    # load the hazard raster and verify inherent exposure
    hazard_da = rxr.open_rasterio(hazard_path, masked=True)
    hazard_da = clip_da_to_asset(hazard_da, ref)
    hazard_da = mask_zero_values(hazard_da)

    idx = risk.sort_values(by=hazcol, ascending=False).index[0]
    verify_asset_geometries(idx, risk, ref)
    verify_asset_exposure(idx, risk, hazard_da, hazcol)

    # %% (optional) plot the hazard column
    if plot:

        fig, ax = plt.subplots(figsize=(15,15),subplot_kw={"projection": ccrs.PlateCarree()})

        risk.plot(hazcol, cmap="YlOrRd", ax=ax, legend=True)
        hazard_da.plot(ax=ax, cmap="Blues", alpha=1.)
        ax.add_feature(cfeature.OCEAN, zorder=10)
        ax.add_feature(cfeature.COASTLINE, zorder=11)
        ax.set_title(f"{asset} exposure to {hazcol}")

    # verify design standards applied correctly for asset_tyope
    print("Available asset types")
    asset_types = list(risk["asset_type"].unique())
    print(asset_types)

    configdir = f"../../config/"
    design_standards_file = os.path.join(configdir, "design_standards", f"{hazard}.csv")
    design_standards = pd.read_csv(design_standards_file, index_col="asset_type")
    design_standards.head()

    risk.head()
    # %%
    risk = risk[risk["asset_type"] == asset_type].copy()
    design_hazard_base = design_standards.loc[asset_type, "design_hazard"]
    design_hazard_col = "hazard-" + design_hazard_base 
    design_hazard_file = design_hazard_base + ".tif"
    print(f"Design hazard for {asset_type} under {scenario}: {design_hazard_file}")
    risk.head()
    # %%
    design_hazard_path = f"../../results/hazards/aligned/{design_hazard_file}"
    design_hazard_da = rxr.open_rasterio(design_hazard_path, masked=True)

    design_hazard_da = clip_da_to_asset(design_hazard_da, ref)
    design_hazard_da = mask_zero_values(design_hazard_da)
    # %%
    residual_hazard = hazard_da - design_hazard_da

    defendedcol = hazcol.replace("hazard-", "defended-")

    idx = risk.sort_values(by=defendedcol, ascending=False).index[0]
    verify_asset_exposure(idx, risk, residual_hazard, defendedcol)
    # %%
    # plot hazard, design hazard, and residual hazard with asset
    vmin = 0
    print(f"{hazcol=}, {defendedcol=}")
    fig, axs = plt.subplots(2, 3, figsize=(10,10),subplot_kw={"projection": ccrs.PlateCarree()})
    risk.plot(hazcol, cmap="YlOrRd", ax=axs[0, 0], legend=True)
    risk.plot(design_hazard_col, cmap="YlOrRd", ax=axs[0, 1], legend=True)
    risk.plot(defendedcol, cmap="YlOrRd", ax=axs[0, 2], legend=True)
    hazard_da.plot(ax=axs[1, 0], cmap="Blues", alpha=1., vmin=vmin)
    design_hazard_da.plot(ax=axs[1, 1], cmap="Blues", alpha=1., vmin=vmin)
    residual_hazard.plot(ax=axs[1, 2], cmap="Blues", alpha=1., vmin=vmin)

    # %%
    # print cost and damages for first asset
    damage_col = hazcol.replace("hazard-", "damage-") + "_mean"
    cost_col = hazcol.replace("hazard-", "cost-") + "_mean_mean"
    risk_cols = [hazcol, damage_col, cost_col]
    risk.loc[idx, risk_cols]

# %%
