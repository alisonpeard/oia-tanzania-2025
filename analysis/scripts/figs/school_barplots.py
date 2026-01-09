#%%
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import integrate
from tqdm import tqdm

summary_path = "~/Desktop/tza_school_roads_hazard_disruption_summary.csv"

summary = pd.read_csv(summary_path)

hazard = "pluvial"
epoch = 2050
scenario = "ssp245"
rp = 100

summary.head()
# %%
