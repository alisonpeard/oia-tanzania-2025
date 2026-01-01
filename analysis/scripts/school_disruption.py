#%%
import os
from glob import glob
import numpy as np
import pandas as pd
import geopandas as gpd
from tqdm import tqdm


relevant_hazards = ["pluvial", "fluvial", "coastal", "landslide"]#, "cyclone"]
crit_path = "~/Desktop/tza_school_roads_edge_criticality.csv"
hazdir_base = "/Users/alison/Local/github/oia-tanzania-2025/results/risk/tza_roads_edges"

def extract_hazard_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract hazard, epoch, scenario, and return period from hazard column name."""
    prefix, parts = hazcol.split("-")
    parts = parts.split("_")
    hazard = parts[0]
    epoch = parts[1]
    scenario = parts[2]
    rp = str(int(parts[3].replace("rp", "")))
    if len(parts) > 4:
        stat = "_".join(parts[4:])
    else:
        stat = ""
    return prefix, hazard, epoch, scenario, rp, stat


if __name__ == "__main__":
    criticality = pd.read_csv(crit_path, index_col="id")
    summary_dfs = []
    for hazard in (pbar := tqdm(relevant_hazards)):
        pbar.set_postfix({"hazard": hazard})
        hazdir = f"{hazdir_base}/{hazard}/*/profile.geoparquet"
        hazfiles = glob(hazdir)

        haz_dfs = []
        for file in hazfiles:
            print(file)
            df = gpd.read_parquet(file)
            subregion = os.path.basename(os.path.dirname(file))
            df["subregion"] = subregion
            damage_cols = [col for col in df.columns if col.startswith("damage-")]

            hazards = []
            epochs = []
            scenarios = []
            rps = []
            stats = []
            total_isolated = np.zeros(len(damage_cols), dtype=float)
            total_rerouted = np.zeros(len(damage_cols), dtype=float)
            total_weighted_detour = np.zeros(len(damage_cols), dtype=float)

            for i, col in enumerate(damage_cols):
                print(f"Processing columnn {i} / {len(damage_cols)} for {subregion}: {col}")
                damaged = df[df[col] > 0].copy()
                disrupted = damaged[[col]].join(
                    criticality[["base_flux", "detoured_flux", "isolated_flux", "weighted_detour"]],
                    how="left"
                )
                prefix, hazard, epoch, scenario, rp, stat = extract_hazard_info(col)
                hazards.append(hazard)
                epochs.append(epoch)
                scenarios.append(scenario)
                rps.append(rp)
                stats.append(stat)

                total_isolated[i] = disrupted["isolated_flux"].sum()
                total_rerouted[i] = disrupted["detoured_flux"].sum()
                total_weighted_detour[i] = disrupted["weighted_detour"].sum()

            summary = pd.DataFrame({
                "subregion": subregion,
                "hazard": hazards,
                "epoch": epochs,
                "scenario": scenarios,
                "rp": rps,
                "stat": stats,
                "total_isolated": total_isolated,
                "total_rerouted": total_rerouted,
                "total_weighted_detour": total_weighted_detour
            })
            summary = summary.sort_values(by=["subregion", "hazard", "epoch", "scenario", "rp", "stat"])
            summary_dfs.append(summary)
    
    summary_final = pd.concat(summary_dfs)
    summary_final.to_csv("~/Desktop/tza_school_roads_hazard_disruption_summary.csv", index=False)
    summary_final.head()
    # %%
