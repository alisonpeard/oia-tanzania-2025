# %%
import numpy as np
import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import CenteredNorm
import cartopy.feature as cfeature
import sys 
sys.path.append("..")

import utils.data as du
import utils.plot as pu


import os
from tqdm import tqdm
import pandas as pd
import geopandas as gpd


adm1_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_1.gpkg"


def admin1_damages(gdf, adm, cost_col, damage_col, asset="road",
                   unit="km", bbox=None, cmap="OrRd") -> tuple:

    # columns needed: length_km, length_km_exposed, fraction_exposed, meancol
    state_data = gdf[['unit', damage_col, cost_col, "subregion"]].groupby("subregion").sum()

    state_data["exposed_fraction"] = state_data[damage_col] / state_data['unit']

    # add state geometries to the data frame
    state_data = state_data.join(adm.set_index("subregion")[["geometry"]])
    state_data = gpd.GeoDataFrame(state_data, geometry='geometry')
    state_data = state_data.set_crs(epsg=4326)
    
    fig, axs = plt.subplots(1, 4, figsize=(10, 3),
                            subplot_kw={'projection': ccrs.PlateCarree()})

    
    ax = axs[0] # plot overall road lengths
    state_data.plot('unit', cmap=cmap, legend=True, ax=ax,
                    edgecolor='k', linewidth=0.1,
                    legend_kwds={
                        'label': f"Total {asset}\n({units})",
                        "shrink": 0.9, "aspect": 15, "orientation": "horizontal",
                        "pad": 0.02
                    }
    )
    print(f"Max total {asset} for {asset}: {state_data['unit'].max():.2f} {unit}")
    print(f"Province with max total {asset} for {asset}: {state_data['unit'].idxmax()}")
    print(f"Mean total {asset} for {asset}: {state_data['unit'].mean():.2f} {unit}")
    print(f"Total {asset} in country: {state_data['unit'].sum():.2f} {unit}")


    ax = axs[1] # plot exposed road lengths
    state_data.plot(damage_col, cmap=cmap, legend=True, ax=ax,
                    edgecolor='k', linewidth=0.1,
                    legend_kwds={
                        'label': f"Exposed ({units})",
                        "shrink": 0.9, "aspect": 15, "orientation": "horizontal",
                        "pad": 0.02
                    }
    )
    print(f"Max exposed {asset} for {asset}: {state_data[damage_col].max():.2f} {unit}")
    print(f"Province with max exposed {asset} for {asset}: {state_data[damage_col].idxmax()}")
    print(f"Mean exposed {asset} for {asset}: {state_data[damage_col].mean():.2f} {unit}")
    print(f"Median exposed {asset} for {asset}: {state_data[damage_col].median():.2f} {unit}")

    ax = axs[2] # plot exposed road lengths as a fraction of total road length
    state_data.plot('exposed_fraction', cmap=cmap, legend=True, ax=ax,
                    edgecolor='k', linewidth=0.1,
                    vmin=0, vmax=1,
                    legend_kwds={
                        'label': f"Exposed fraction",
                        "shrink": 0.9, "aspect": 15, "orientation": "horizontal",
                        'ticks': [0, 0.25, 0.5, 0.75, 1.0],
                        "pad": 0.02
                    }
    )
    print(f"Max exposed fraction for {asset}: {state_data['exposed_fraction'].max():.2f}")
    print(f"Province with max exposed fraction for {asset}: {state_data['exposed_fraction'].idxmax()}")
    print(f"Mean exposed fraction for {asset}: {state_data['exposed_fraction'].mean():.2f}")
    print(f"Median exposed fraction for {asset}: {state_data['exposed_fraction'].median():.2f}")
    
    ax = axs[3] # plot exposure in USD per province using exposed_column var
    state_data_rescaled = state_data.copy()
    if state_data_rescaled[cost_col].max() > 1e6:
        state_data_rescaled[cost_col] = state_data_rescaled[cost_col] * 1e-6
        scale_label = " (million USD)"
    elif state_data_rescaled[cost_col].max() > 1e3:
        state_data_rescaled[cost_col] = state_data_rescaled[cost_col] * 1e-3
        scale_label = " (k USD)"
    else:
        scale_label = " (USD)"
    if state_data_rescaled[cost_col].min() > 10:
        vmin = np.round(state_data_rescaled[cost_col].min(), -1)
        vmax = np.round(state_data_rescaled[cost_col].max(), -1)
        ticks = list(np.linspace(vmin, vmax, 5, dtype=int))
    else:
        vmin = np.round(state_data_rescaled[cost_col].min(), 1)
        vmax = np.round(state_data_rescaled[cost_col].max(), 1)
        # make ticks with one decimal place
        ticks = list(np.round(np.linspace(vmin, vmax, 5), 1))

    state_data_rescaled.plot(cost_col, cmap=cmap, legend=True, ax=ax,
                    edgecolor='k', linewidth=0.1,
                    legend_kwds={
                        'label': f"Exposure{scale_label}",
                        "shrink": 0.9, "aspect": 15, "orientation": "horizontal",
                        "ticks": ticks,
                        "pad": 0.02
                    }
    )
    print(f"Max exposure for {asset}: {state_data_rescaled[cost_col].max():.2f}{scale_label}")
    print(f"Province with max exposure for {asset}: {state_data_rescaled[cost_col].idxmax()}")
    print(f"Mean exposure for {asset}: {state_data_rescaled[cost_col].mean():.2f}{scale_label}")
    print(f"Median exposure for {asset}: {state_data_rescaled[cost_col].median():.2f}{scale_label}")

    for ax in axs.flatten():
        ax = pu.add_geofeatures(ax);
        if bbox:
            ax.set_extent(bbox)

    plt.tight_layout()
    return fig, axs

# %% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

ASSET_GEOM = "tza_roads_bridges_and_culverts_nodes"
HAZARD = "fluvial"
WD = "/Users/alison/Local/github/oia-tanzania-2025/results"

assets = [
    "tza_roads_edges",
    "tza_roads_bridges_and_culverts_nodes",
    "tza_railway_edges",
    "tza_hubs_polygons"
]

hazards = [
    "fluvial",
    # "pluvial",
    # "coastal",
    # "cyclone",
    # "landslide"
]

for hazard in hazards:
    for asset_geom in assets:
        if hazard == "cyclone":
            damage_col = f"damage-{hazard}_2050_ssp245_rp00250_max"
            cost_col = f"cost-{hazard}_2050_ssp245_rp00250_max"
        else:
            damage_col = f"damage-{hazard}_2050_ssp245_rp00100_max"
            cost_col = f"cost-{hazard}_2050_ssp245_rp00100_max"
        base_dir = os.path.join(WD, "risk_cleaned", asset_geom, hazard)

        asset = du.load_asset_data(
            asset_dir=base_dir,
            metric_type="profile.geoparquet"
        )
        units = asset["unit_type"].unique().item()

        if units == 'm':
            asset['unit'] = asset['unit'] / 1000  # convert to km
            asset[damage_col] = asset[damage_col] / 1000
            units = 'km'
        if units == "sqm":
            asset['unit'] = asset['unit'] / 1e6  # convert to sqkm
            asset[damage_col] = asset[damage_col] / 1e6
            units = 'sq km'
            
        adm1 = gpd.read_file(adm1_path)
        adm1["subregion"] = adm1["shapeName"].str.lower().copy()
        bbox = [29, 41, -12, -1]
        asset_label = " ".join(asset_geom.split("_")[1:-1])

        df = admin1_damages(asset, adm1, cost_col, damage_col, asset=asset_label, unit=units, bbox=bbox)
# %%
