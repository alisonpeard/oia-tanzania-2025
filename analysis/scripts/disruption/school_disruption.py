#%%
import os
from glob import glob
import numpy as np
import pandas as pd
import geopandas as gpd
from tqdm import tqdm


relevant_hazards = ["pluvial", "fluvial", "coastal", "landslide"]
crit_path = "~/Desktop/tza_school_roads_edge_criticality.csv"

#! note temporary rename of risk directory
hazdir_base = "/Users/alison/Local/github/oia-tanzania-2025/results/risk_nohd35base/tza_roads_edges"

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
    # Fix: Expand tilde for the path
    crit_path = os.path.expanduser("~/Desktop/tza_school_roads_edge_criticality.csv")
    criticality = pd.read_csv(crit_path, index_col="id")
    
    summary_dfs = []
    for hazard_type in (pbar := tqdm(relevant_hazards)):
        pbar.set_postfix({"hazard": hazard_type})
        hazdir = f"{hazdir_base}/{hazard_type}/*/profile.geoparquet"
        hazfiles = glob(hazdir)

        for hazfile in hazfiles:
            hazdf = pd.read_parquet(hazfile)
            subregion = os.path.basename(os.path.dirname(hazfile))
            
            # --- CRITICAL FIX: JOIN ONCE PER SUBREGION ---
            hazdf = hazdf.join(criticality[["base_flux", "detoured_flux", "isolated_flux", "weighted_detour"]], how="left").fillna(0.0)
            
            damage_cols = [col for col in hazdf.columns if col.startswith("damage-")]
            
            # Calculate the subregion constant once
            base_flux_sum = hazdf["base_flux"].sum()
            
            # Temporary storage for scenario data
            scenario_rows = []

            for col in damage_cols:
                # Use boolean indexing on the already-joined hazdf
                # This is much faster than joining inside the loop
                mask = hazdf[col] > 0
                
                # If 'damaged = hazdf.copy()' is your goal, remove the 'mask' filter below
                iso = hazdf.loc[mask, "isolated_flux"].sum()
                rer = hazdf.loc[mask, "detoured_flux"].sum()
                w_detour = hazdf.loc[mask, "weighted_detour"].sum()
                
                perc = 100 * ((iso + rer) / base_flux_sum) if base_flux_sum > 0 else 0.0
                perc = min(100.0, perc) # Simple cap
                
                prefix, haz, epoch, scenario, rp, stat = extract_hazard_info(col)
                
                scenario_rows.append({
                    "subregion": subregion,
                    "hazard": haz,
                    "epoch": epoch,
                    "scenario": scenario,
                    "rp": rp,
                    "stat": stat,
                    "base_flux": base_flux_sum,
                    "total_isolated": iso,
                    "total_rerouted": rer,
                    "perc_disrupted": perc,
                    "total_weighted_detour": w_detour
                })

            summary_dfs.append(pd.DataFrame(scenario_rows))

    summary_final = pd.concat(summary_dfs)
    output_path = os.path.expanduser("~/Desktop/tza_school_roads_hazard_disruption_summary.csv")
    summary_final.to_csv(output_path, index=False)
    # %%
    summary_final.head()