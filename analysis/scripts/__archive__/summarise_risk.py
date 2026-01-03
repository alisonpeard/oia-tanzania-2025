# %%
import os
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
import utils.data as du


print("Checking risk results...")
risk_dir = "/Users/alison/Local/github/oia-tanzania-2025/results/risk"

results = []

missing = ("pluvial", 2080, "ssp245", 200)
missing = ("coastal", 2050, "ssp585", 50)

assets = os.listdir(risk_dir)
assets = [asset for asset in assets if not asset.startswith(".")]
for asset in assets[:1]:
    hazards = os.listdir(os.path.join(risk_dir, asset))
    hazards = [hazard for hazard in hazards if not hazard.startswith(".")]
    for hazard in hazards:
        subregions = os.listdir(os.path.join(risk_dir, asset, hazard))
        subregions = [subregion for subregion in subregions if not subregion.startswith(".")]
        for subregion in (pbar := tqdm(subregions)):
            pbar.set_postfix({"asset": asset, "hazard": hazard, "subregion": subregion}) 
            filepath = os.path.join(risk_dir, asset, hazard, subregion, "profile.geoparquet")
            df = gpd.read_parquet(filepath)
            hazcols = [col for col in df.columns if col.startswith("hazard-")]
            for hazcol in hazcols:
                _, haz, epoch, scenario, rp, _ = du.extract_hazard_info(hazcol)
                assert haz == hazard, f"Mismatch hazard: {haz} vs {hazard}"
                epoch, rp = int(epoch), int(rp)
                mean = df[hazcol].mean()
                results.append((asset, haz, subregion, epoch, scenario, rp, mean))

# %%
results_df = pd.DataFrame(results, columns=["asset", "hazard", "subregion", "epoch", "scenario", "return_period", "mean_hazard"])
results_df = results_df.drop_duplicates()
results_df = results_df.sort_values(by=["asset", "hazard", "subregion", "epoch", "scenario", "return_period"])
results_df = results_df.groupby(["asset", "hazard", "epoch", "scenario", "subregion"]).agg({"return_period": list, "mean_hazard": list})
# %%
def check_for_rp(series, rp):
    values = series.values
    values_ref = values[0]
    assert rp in values_ref, f"Missing return period {rp} in {values_ref}"
    for v in values[1:]:
        if v != values_ref:
            print(f"Non-unique return periods: {values}")
            return False
    return True

idx = pd.IndexSlice

# apparently missing RP200
missing = results_df.loc[idx[:, "pluvial", 2080, "ssp245", :]]
assert check_for_rp(missing["return_period"], 200)
rps = missing["return_period"].values.tolist()
values = missing["mean_hazard"].values.tolist()
missing_values = pd.DataFrame(values, columns=rps[0])
missing_values.mean(axis=0).plot.bar()
# %%
# apparently missing RP50
missing = results_df.loc[idx[:, "coastal", 2050, "ssp585", :]]
assert check_for_rp(missing["return_period"], 50)
rps = missing["return_period"].values.tolist()
values = missing["mean_hazard"].values.tolist()
missing_values = pd.DataFrame(values, columns=rps[0])
missing_values.mean(axis=0).plot.bar()
# %%
