# %%
import os
import pandas as pd
from functools import partial

path = "/Users/alison/Local/data/oia-tanzania-2025/input/protection/protection_standards_flooding.csv"
df = pd.read_csv(path)

epoch = 2020
scenario = "historical"
hazards = ["fluvial", "pluvial", "coastal"]
hazard = "fluvial"

def format_design_standard(rp, hazard, scenario, epoch):
    if rp == 0:
        return None
    return '_'.join([
        hazard,
        str(epoch),
        scenario,
        f"rp{str(rp).zfill(5)}"
    ])

for hazard in hazards:
    df_hazard = df.copy()
    outfile = f"../../config/design_standards/{hazard}.csv"
    format_design_hazard = partial(
        format_design_standard,
        hazard=hazard, scenario=scenario, epoch=epoch
    )
    df_hazard["design_hazard"] = df_hazard["design_return_period"].apply(format_design_hazard)
    df_hazard = df_hazard[["asset_type", "design_hazard"]].copy()
    df_hazard.to_csv(outfile, index=False)

# now for hazards without protection
hazards = ["landslide", "cyclone", "heat"]
for hazard in hazards:
    df_hazard = df.copy()
    outfile = f"../../config/design_standards/{hazard}.csv"
    df_hazard["design_hazard"] = None
    df_hazard = df_hazard[["asset_type", "design_hazard"]].copy()
    df_hazard.to_csv(outfile, index=False)
# %%
