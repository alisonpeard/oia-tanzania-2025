# %%
import os
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import integrate
from tqdm import tqdm

damage_threshold = 0.5
crit_path = "/Users/alison/Desktop/tza_health_roads_edge_criticality.csv"
subregions_path = "/Users/alison/Local/github/oia-tanzania-2025/results/assets/subregions.txt"
risk_dir = "/Users/alison/Local/github/oia-tanzania-2025/results/risk_cleaned_nohd35base" #! remember to change back
disrupt_dir = "/Users/alison/Local/github/oia-tanzania-2025/results/health_access"

def ead(df:pd.DataFrame, method="trapezoid", column="value") -> float:
        """Calculate expected annual damage from damage values and return periods."""
        if df.empty | (df[column] == 0).all():
            return 0.0
        damages = df[column].astype(float).values
        rps = df["rp"].astype(float).values
        probs = 1 / rps
        idx = np.argsort(probs)
        probs = np.insert(probs[idx], 0, 0.0)
        damages = np.insert(damages[idx], 0, 0.0)
        ead_value = getattr(integrate, method)(damages, x=probs)
        return ead_value


if __name__ == "__main__":
    crit = pd.read_csv(crit_path, index_col="id")
    subregions = pd.read_csv(subregions_path, header=None)[0].tolist()

    asset_geom = "tza_roads_edges"
    hazards = ["fluvial", "pluvial", "coastal", "landslide"]


    for subregion in (pbar := tqdm(subregions)):
        for hazard in hazards:
            pbar.set_postfix({"subregion": subregion, "hazard": hazard})

            inpath = os.path.join(risk_dir, asset_geom, hazard, subregion, "profile.geoparquet")
            outpath = os.path.join(disrupt_dir, asset_geom, hazard, subregion, "profile.parquet")
            
            if not os.path.exists(os.path.dirname(outpath)):
                os.makedirs(os.path.dirname(outpath), exist_ok=True)

            hazdf = pd.read_parquet(inpath).set_index("id")

            crit_subregion = crit.join(hazdf, how="inner")
            crit_subregion = crit_subregion.fillna(0.0)

            damage_cols = [col for col in crit_subregion.columns if col.startswith("damage-")]
            isolated_cols = [col.replace("damage-", "isolated-") for col in damage_cols]
            detoured_cols = [col.replace("damage-", "detoured-") for col in damage_cols]
            wdetour_cols = [col.replace("damage-", "wdetoured-") for col in damage_cols]

            # save disruption profiles
            damage_binary = (crit_subregion[damage_cols] > damage_threshold).astype(int)
            isolated = damage_binary.multiply(crit_subregion["isolated_flux"], axis=0).rename(columns=dict(zip(damage_cols, isolated_cols)))
            detoured = damage_binary.multiply(crit_subregion["detoured_flux"], axis=0).rename(columns=dict(zip(damage_cols, detoured_cols)))
            wdetour = damage_binary.multiply(crit_subregion["weighted_detour"], axis=0).rename(columns=dict(zip(damage_cols, wdetour_cols)))

            disruption = pd.concat([isolated, detoured, wdetour], axis=1)
            disruption["base_flux"] = crit_subregion["base_flux"].copy()
            disruption.to_parquet(outpath, index=True)
# %%