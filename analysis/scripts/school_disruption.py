#%%
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import analysis.scripts.traffic as traffic

# parameters
traffic_dir = "/Users/alison/Downloads/flows/road_traffic"

traffic = gpd.read_file(os.path.join(traffic_dir, "dar_es_salaam.gpkg"))
traffic.head()
# %%
print(traffic.columns.tolist())
# %%
