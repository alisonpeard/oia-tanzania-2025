# %%
import os
import pandas as pd
import geopandas as gpd

traffic_path = "~/Desktop/tza_school_roads_edge_criticality.csv"
road_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"
# %%
traffic = pd.read_csv(traffic_path)
roads = gpd.read_parquet(road_path)
# %%
traffic_geo = traffic.merge(
    roads[["id", "geometry"]],
    left_on="id",
    right_on="id",
    how="left"
)
# %%
traffic_geo = gpd.GeoDataFrame(traffic_geo, geometry="geometry", crs=roads.crs)
# %%
import matplotlib.pyplot as plt

import numpy as np
cols_of_interest = ["isolated_flux", "detoured_flux", "weighted_detour"]

linewidths = [0.1, 0.5, 1, 2, 3]
fig, ax = plt.subplots(1, 1, figsize=(10, 10))

col = "weighted_detour"
traffic_col = traffic_geo[[col, "base_flux", "geometry"]].fillna(0).replace(0, 1e-6)
traffic_col = traffic_col.sort_values(by=col, ascending=True)
quantiles = np.quantile(np.log(traffic_col["base_flux"]), [0, 0.25, 0.5, 0.75, 1])
quantiles = np.exp(quantiles)
print(f"{col} quantiles: {quantiles}")
for i, q in enumerate(quantiles):
    print(q)
    traffic_q = traffic_col[traffic_col["base_flux"] > q]
    traffic_q.plot(column=col, cmap="OrRd", ax=ax, linewidth=linewidths[i])
ax.set_title(col)
#%%
fig.savefig(f"/Users/alison/Desktop/tza_school_roads_edge_criticality_{col}.png", dpi=300)
# %%
traffic_geo.to_file("~/Desktop/tza_school_roads_edge_criticality.gpkg", driver="GPKG")
# %%
