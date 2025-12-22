# %%
import numpy as np
import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import CenteredNorm
import cartopy.feature as cfeature

def add_geofeatures(ax):
    ax.add_feature(cfeature.BORDERS, color='k', linestyle=':', alpha=0.5, linewidth=0.5)
    ax.add_feature(cfeature.LAND, color="#D9D7D3")
    ax.add_feature(cfeature.LAKES, color='#7ABAEC', zorder=10)
    ax.add_feature(cfeature.RIVERS, edgecolor='#7ABAEC', zorder=10)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.OCEAN, color='#7ABAEC', zorder=0)
    gl = ax.gridlines(draw_labels=True, linewidth=.1, color='#7D6E63', alpha=0.5, x_inline=False, y_inline=False)
    gl.top_labels = False
    gl.right_labels = False
    return ax


def admin1_damages(gdf, adm, cost_col, damage_col, asset="road", unit="km", bbox=None) -> tuple:

    # columns needed: length_km, length_km_exposed, fraction_exposed, meancol
    state_data = gdf[['unit', damage_col, cost_col, "subregion"]].groupby("subregion").sum()
    state_data["exposed_fraction"] = state_data[damage_col] / state_data['unit']

    # add state geometries to the data frame
    state_data = state_data.join(adm.set_index("subregion")[["geometry"]])
    state_data = gpd.GeoDataFrame(state_data, geometry='geometry')
    state_data = state_data.set_crs(epsg=4326)

    print(state_data.head())
    # return state_data
    
    fig, axs = plt.subplots(2, 2, figsize=(12, 8),
                            subplot_kw={'projection': ccrs.PlateCarree()})

    # plot overall road lengths
    ax = axs[0,0]
    state_data.plot('unit', cmap="YlOrRd", legend=True, ax=ax,
                    edgecolor='k', linewidth=0.1,
                    legend_kwds={'label': f"{asset.capitalize()} length ({unit})", "shrink": 0.5, "aspect": 15})
    ax.set_title(f"Total {unit}s of {asset} per state")

    # plot exposed road lengths
    ax = axs[0,1]
    state_data.plot(damage_col, cmap="YlOrRd", legend=True, ax=ax,
                    edgecolor='k', linewidth=0.1,
                    legend_kwds={'label': f"Exposed {asset} length ({unit})", "shrink": 0.5, "aspect": 15})
    ax.set_title(f"Exposed {asset} ({unit}) per state")

    # plot exposed road lengths as a fraction of total road length
    ax = axs[1,0]
    # state_data['exposed_fraction'] = state_data['length_km_exposed'] / state_data['length_km']
    state_data.plot('exposed_fraction', cmap="YlOrRd", legend=True, ax=ax,
                    edgecolor='k', linewidth=0.1,
                    legend_kwds={'label': f"Exposed {asset} {unit} fraction", "shrink": 0.5, "aspect": 15})
    ax.set_title(f"Exposed fraction of {asset} ({unit}) per state")

    # plot exposure in USD per state using exposed_column var
    ax = axs[1, 1]
    state_data_rescaled = state_data.copy()
    state_data_rescaled[cost_col] = state_data_rescaled[cost_col] * 1e-6
    state_data_rescaled.plot(cost_col, cmap="YlOrRd", legend=True, ax=ax,
                    edgecolor='k', linewidth=0.1,
                    legend_kwds={'label': "Exposure (USD million)", "shrink": 0.5, "aspect": 15})
    ax.set_title(f"Exposure per state")

    # fig.suptitle(f"{core.format_rp(RP)}-year flood ({HAZARD}, {EPOCH} RCP {SCENARIO[-3:].replace('p', '.')})",
    #              fontsize=20, y=1.)
    plt.tight_layout()

    for ax in axs.flatten():
        ax = add_geofeatures(ax);
        if bbox:
            ax.set_extent(bbox)

    return fig, axs

# %% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
import os
from tqdm import tqdm
import pandas as pd
import geopandas as gpd

ASSET_GEOM = "tza_railway_edges"
HAZARD = "pluvial"
WD = "../../results"

base_dir = os.path.join(WD, "risk", ASSET_GEOM, HAZARD)
subregions = os.listdir(base_dir)
subregions = [s for s in subregions if not s.startswith(".")]

assets = []
for subregion in tqdm(subregions):
    file = os.path.join(base_dir, subregion, "profile.geoparquet")
    asset = gpd.read_parquet(file).reset_index()
    asset["subregion"] = subregion
    assets.append(asset)

asset = pd.concat(assets, axis=0)
units = asset["unit_type"].unique().item()
# %%
damage_col = f"damage-{HAZARD}_2050_ssp585_rp00100_max"
cost_col = f"cost-{HAZARD}_2050_ssp585_rp00100_max_max"
# %%
# asset["unit"] = asset["unit"] / 1000
# asset[damage_col] = asset[damage_col] / 1000

adm1_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_1.gpkg"

adm1 = gpd.read_file(adm1_path)
adm1["subregion"] = adm1["shapeName"].str.lower().copy()
bbox = [29, 41, -12, -1]
asset_label = " ".join(ASSET_GEOM.split("_")[1:-1])
df = admin1_damages(asset, adm1, cost_col, damage_col, asset=asset_label, unit=units, bbox=bbox)
# %%
