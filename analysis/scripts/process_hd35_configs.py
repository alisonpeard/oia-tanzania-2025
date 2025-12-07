"""
Make dummy config files for hd35 and tasmax. These hazard need a
seperate damage assessment.
"""
# %%
import os
import pandas as pd

def remove_hidden_files(file_list):
    return [f for f in file_list if not f.startswith(".")]

vars = ["hd35", "tasmax"]
config_dir = os.path.join("..", "..", "config")

#%% design standards

for var in vars:
    ref_path = os.path.join(config_dir, "design_standards", "pluvial.csv")
    out_path = os.path.join(config_dir, "design_standards", var + ".csv")
    df = pd.read_csv(ref_path, comment='#')
    df["design_hazard"] = pd.NA
    df.to_csv(out_path, index=False)

#%% damage curves
for var in vars:
    ref_dir = os.path.join(config_dir, "damage_curves", "pluvial")
    out_dir = os.path.join(config_dir, "damage_curves", var)

    os.makedirs(out_dir, exist_ok=True)

    asset_types = os.listdir(ref_dir)
    asset_types = remove_hidden_files(asset_types)

    for asset in asset_types:
        ref_path = os.path.join(ref_dir, asset)
        out_path = os.path.join(out_dir, asset)

        df = pd.read_csv(ref_path, comment='#').iloc[[0]]
        df.iloc[:, 1:-1] = -9999.
        df.to_csv(out_path, index=False)

#%% rehab costs
for var in vars:
    ref_path = os.path.join(config_dir, "rehab_costs", "pluvial.csv")
    out_path = os.path.join(config_dir, "rehab_costs", var + ".csv")
    df = pd.read_csv(ref_path, comment='#')
    df[["mean_cost_usd", "min_cost_usd", "max_cost_usd"]] = 0.0
    df.to_csv(out_path, index=False)

# %%
