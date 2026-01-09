# %%
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import integrate
from tqdm import tqdm

summary_path = "~/Desktop/tza_school_roads_hazard_disruption_summary.csv"

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

# load summary
summary = pd.read_csv(summary_path)
summary["perc_disrupted"].plot.hist()
# %%

risk_cols = ["total_isolated", "total_rerouted", "total_weighted_detour", "perc_disrupted"]

summary_melted = summary.melt(
    id_vars=[
        "subregion",
        "base_flux",
        "hazard",
        "epoch",
        "scenario",
        "stat",
        "rp"
    ],
    value_vars=risk_cols,
    var_name="metric",
    value_name="value",
)

summary_grouped = summary_melted.groupby(
      ["subregion", "hazard", "epoch", "scenario", "stat", "metric", "base_flux"],
)

tqdm.pandas(desc="Calculating EADs")
ead_results = summary_grouped.progress_apply(ead, column="value").reset_index()
ead_results = ead_results.rename(columns={0: "expected"})
ead_results.to_csv("/Users/alison/Downloads/flows/school_disruption/ead_by_province.csv", index=False)
# %%