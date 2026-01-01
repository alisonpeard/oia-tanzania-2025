#%%

import matplotlib.pyplot as plt
import pandas as pd

path = "~/Desktop/tza_school_roads_hazard_disruption_summary.csv"

summary = pd.read_csv(path)
summary.head()
# %%
import seaborn as sns

# error bar represents ssps and min/max damage curves
hazard = "coastal"
summary_hazard = summary[summary["hazard"] == hazard].copy()

def minmax(x):
    return (x.min(), x.max())

sns.catplot(
    data=summary_hazard,
    x="epoch",
    y="total_isolated",
    hue="rp",
    edgecolor="k",
    linewidth=0.25,
    kind="bar",
    palette="Blues",
    errorbar=("pi", 100),
    height=6,
    aspect=2
)
plt.yscale("log")
plt.title(f"School journeys at-risk of isolation from {hazard}")
plt.ylabel("Total loss of access")
plt.xlabel("Hazard type")
plt.tight_layout()


sns.catplot(
    data=summary_hazard,
    x="epoch",
    y="total_rerouted",
    hue="rp",
    edgecolor="k",
    linewidth=0.25,
    kind="bar",
    palette="Blues",
    errorbar=("pi", 100),
    height=6,
    aspect=2
)
plt.yscale("log")
plt.title(f"School journeys at-risk of rerouting from {hazard}")
plt.ylabel("Total rerouted journeys")
plt.xlabel("Hazard type")
plt.tight_layout()


summary_hazard["total_weighted_detour_hrs"] = summary_hazard["total_weighted_detour"] / 60  # to walking mins
sns.catplot(
    data=summary_hazard,
    x="epoch",
    y="total_weighted_detour_hrs",
    hue="rp",
    edgecolor="k",
    linewidth=0.25,
    kind="bar",
    palette="Blues",
    errorbar=("pi", 100),
    height=6,
    aspect=2
)
plt.yscale("log")
plt.title(f"Total detour time for all at-risk school journeys from {hazard}")
plt.ylabel("Aggregate detour time (walking hrs)")
plt.xlabel("Hazard type")
plt.tight_layout()

# %%

summary_hazard.head()
# %%
summary_hazard[["total_isolated", "total_rerouted", "total_weighted_detour"]].sum(axis=0)