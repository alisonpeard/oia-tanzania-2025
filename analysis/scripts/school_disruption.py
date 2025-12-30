#%%
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# parameters
hazcol = "damage-pluvial_2080_ssp585_rp01000_mean"
traffic_dir = "/Users/alison/Downloads/flows/road_traffic"


traffic = gpd.read_file(os.path.join(traffic_dir, "tza_roads_edges.gpkg"))
traffic.head()
# %%
exposure = gpd.read_parquet("../../results/risk/tza_roads_edges/pluvial/dar_es_salaam/profile.geoparquet")
exposure = exposure[exposure[hazcol] > 0].copy()

# %%
disrupted = exposure[[hazcol]].join(
    traffic.set_index("id"),
    how="left"
)

# %%
disrupted.head()
# %%
isolated = disrupted[~np.isfinite(disrupted["detour_cost"])].copy()
rerouted = disrupted[np.isfinite(disrupted["detour_cost"])].copy()

# %%
isolated["traffic"].sum()
# %%
rerouted["traffic"].sum()
# %%
(rerouted["traffic"] * rerouted["detour_cost"]).sum()
# %%
rerouted["detour_cost"].hist(bins=50)
# %%
