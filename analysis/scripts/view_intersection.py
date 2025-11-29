# %%
import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

path = "../../results/risk/tza_railway_edges/kilimanjaro/pluvial.geoparquet"
gdf = gpd.read_parquet(path)
print(gdf.info())
# %%
gdf.describe()
# %%
hazcols = [c for c in gdf.columns if c.startswith("hazard-")]
hazcol = hazcols[0]

fig, ax = plt.subplots(1, 1, figsize=(10, 10))
gdf.plot(column=hazcol, cmap='viridis', legend=True, ax=ax)
ax.set_title(hazcol)

# %%
damcols = [c for c in gdf.columns if c.startswith("damage-")]
damcol = damcols[0]

fig, ax = plt.subplots(1, 1, figsize=(10, 10))
gdf.plot(column=damcol, cmap='Reds', legend=True, ax=ax)
ax.set_title(damcol)
# %%
