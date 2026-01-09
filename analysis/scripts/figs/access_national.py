
"""
Get national summaries in terms of accessibility indices.

There are some spurious duplicates in the data that need to be
investigated further.
"""
# %%
import numpy as np
import pandas as pd
from glob import glob
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns

import sys
sys.path.append("..")

import utils.plot as pu

service = "school"
hazards = ["pluvial", "fluvial", "coastal", "landslide"] # ! sum across all hazards later
simplified = "/Users/alison/Downloads/flows/tza_road_simplifications.csv"
crit_dir = f"/Users/alison/Local/github/oia-tanzania-2025/results/{service}_access/tza_roads_edges"
road_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"
admin1 = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_1.gpkg"

id_cols = ["id", "base_flux", "hazard", "epoch", "scenario", "range"]

crit_dfs = {}
for hazard in hazards:
    print(f"Loading criticality data for hazard {hazard}...")
    hazard_crit_files = glob(f"{crit_dir}/{hazard}/*/annual.parquet")
    crit_df_list = []
    for crit_file in tqdm(hazard_crit_files, leave=False):
        crit_subregion = pd.read_parquet(crit_file)
        crit_subregion = crit_subregion.drop_duplicates()
        crit_df_list.append(crit_subregion)
    print(f"All files loaded for hazard {hazard}. Combining...")
    crit_df = (
        pd.concat(crit_df_list)
        .drop_duplicates()
        .groupby(id_cols + ["metric"])
        .agg({"expected": "max"}) # ! spurious zero-value duplicates: take max
        .reset_index()
        .pivot(index=id_cols, columns="metric", values="expected")
        .reset_index()
        .set_index("id")
    )
    crit_df["wdetoured"] = crit_df["wdetoured"] / 60 # minutes to hours
    crit_dfs[hazard] = crit_df

print(len(crit_dfs[hazard]), "road segments with criticality data for hazard", hazard)

# %%
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


idx = pd.IndexSlice


def million_formatter(x, pos):
    return f'{x*1e-6:.1f}M'

variable = ["isolated", "wdetoured"]
units = ["persons", "person-hours"]


simplifications = pd.read_csv(simplified, index_col="id").drop(columns=["Unnamed: 0"])

for variable, unit in zip(variable, units):

    totals_df = {}
    for hazard, crit_df in crit_dfs.items():
        crit_df["epoch"] = crit_df["epoch"].replace({
            "2015": "baseline",
            "2020": "baseline"
        })
        crit_df = crit_df.join(simplifications, how="left")

        # only take max from continuous segments to avoid double-counting
        group_cols = ["hazard", "epoch", "scenario", "range", "segment_id"]
        print(f"Length before grouping segments for {hazard}:", len(crit_df))
        simplified_df = crit_df.reset_index().groupby(group_cols).agg({variable: "max"})
        print(f"Length after grouping segments for {hazard}:", len(simplified_df))
        
        # now sum across segments to get national totals per scenario
        group_cols = ["hazard", "epoch", "scenario", "range"]
        totals = simplified_df.reset_index().groupby(group_cols).agg({variable: "sum"})
        totals = totals.rename(columns={variable: hazard})
        totals_df[hazard] = totals

    fig, axs = plt.subplots(1, 4, figsize=(15, 3), sharey=False)
    i = 0
    for ax, hazard in zip(axs, hazards):
        totals_df_hazard = totals_df[hazard]
        totals_df_hazard = totals_df_hazard.loc[idx[hazard, :, :, :], :]

        cmap = plt.get_cmap("Spectral_r")

        baseline = totals_df_hazard.loc[(hazard, 'baseline', 'historical', 'mean'), hazard]
        epochs = ['baseline', '2030', '2050', '2080']
        scenarios = ['historical', 'ssp126', 'ssp245', 'ssp585']
        scenario_labels = {
            "historical": "Baseline",
            "ssp126": "SSP1-2.6",
            "ssp245": "SSP2-4.5",
            "ssp585": "SSP5-8.5"
        }
        colors_sns = sns.color_palette("Spectral_r", n_colors=4) # 4 default
        colors = {'historical': colors_sns[0], 'ssp126': colors_sns[1], 'ssp245': colors_sns[2], 'ssp585': colors_sns[3]}

        variable_labels = {
            "isolated": "loss of access",
            "detoured": "rerouted",
            "wdetoured": "rerouted\n(weighted by detour hrs)",
            "base_flux": "using road",
        }

        x = np.arange(len(epochs))
        width = 0.25

        for j, ssp in enumerate(scenarios):
            if ssp == "historical":
                means = [baseline]
                ax.bar(x, means,
                    width, label=scenario_labels[ssp], color=colors[ssp],
                    linewidth=0.5, edgecolor="k")
            else:
                means = [baseline] + [totals_df_hazard.loc[(hazard, e, ssp, 'mean'), hazard] for e in epochs[1:]]
                ax.bar(x + j * width, means,
                    width, label=scenario_labels[ssp], color=colors[ssp],
                    linewidth=0.5, edgecolor="k")

        ax.set_xticks(x)
        ax.set_xticklabels(epochs)
        ax.yaxis.set_major_formatter(FuncFormatter(million_formatter))
        ax.set_xlabel(f'Epoch ({hazard.title()})', fontweight="bold")
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        # add light gridlines
        ax.yaxis.grid(True, linestyle='--', alpha=0.5)
        if hazard == "coastal":
            ax.legend(loc='upper left', title='SSP scenario', frameon=False)
        if i == 0:
            ax.set_ylabel(f'Expected Annual\n{variable_labels[variable].title()}\n({unit})',
                        fontweight="bold")
            print("hello")
        i += 1

    plt.tight_layout()
    plt.show()


# %%