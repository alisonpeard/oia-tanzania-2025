
"""
Get national summaries in terms of accessibility indices.

NOTE: uses a simplified road network to reduce any risk of double-counting
disruptions. All degree-2 nodes are assigned a "segment_id". Simplified road
network script is provided separately in the network analysis workflow.
"""
# %%
import numpy as np
import pandas as pd
import seaborn as sns
from tqdm import tqdm
from glob import glob
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.ticker import EngFormatter

from oi_risk import config as cfg

# script parameters
sns.set_style("whitegrid")
idx = pd.IndexSlice
service = ["school", "health"][0]
hazards = ["coastal", "pluvial", "fluvial", "landslide"]
id_cols = ["id", "base_flux", "hazard", "epoch", "scenario", "range"]
params  = {"school": {
    "zeta": 1.0,
    "total_flux": 18_567_485, # from school_criticality.py
    "total_weighted_flux": 718_021_545
}, "health": {
    "zeta": 0.00214,
    "total_flux": 61_567_247, # from health_criticality.py
    "total_weighted_flux": 1_091_705_149
}}
variables = ["isolated", "wdetoured"]
units = ["persons", "person-hours"]
baseline_map = {
            "2015": "baseline",
            "2020": "baseline"
}


def load_criticality_data(hazard, crit_dir, zeta, filename="annual"):
    """Load all files for a given hazard."""
    print(f"Loading criticality data for hazard {hazard}...")
    hazard_crit_files = glob(f"{crit_dir}/{hazard}/*/{filename}.parquet")
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
    crit_df["isolated"] = zeta * crit_df["isolated"]  # persons
    crit_df["detoured"] = zeta * crit_df["detoured"]  # person-hours
    crit_df["wdetoured"] = zeta * crit_df["wdetoured"] / 60 # minutes to hours
    print(len(crit_df), "road segments with criticality data for hazard", hazard)
    return crit_df


def simplify_crit_df(crit_df, simplifications):
    crit_df = crit_df.join(simplifications, how="left")
    group_cols = ["hazard", "epoch", "scenario", "range", "segment_id"]
    print(f"Length before grouping segments:", len(crit_df))
    simplified_df = crit_df.reset_index().groupby(group_cols).agg({variable: "max"})
    print(f"Length after grouping segments:", len(simplified_df))
    return simplified_df


def get_national_totals(simplified_df, variable):
    group_cols = ["hazard", "epoch", "scenario", "range"]
    totals = simplified_df.reset_index().groupby(group_cols).agg({variable: "sum"})
    totals = totals.rename(columns={variable: hazard})
    return totals


if __name__ == "__main__":
    # define all paths
    config = cfg.load_config()
    access_dir = Path(config["paths"]["access"])
    input_dir  = Path(config["paths"]["snakemake"]) / "input"
    smk_dir    = Path(config["paths"]["snakemake"])
    simplified = access_dir / "tza_road_simplifications.csv"
    crit_dir = access_dir / service
    road_path = input_dir / "assets" / "tza_roads_edges.parquet"
    admin1 = smk_dir / "input" / "admin" / "level01.geoparquet"

    # add traffic scaling post-hoc
    zeta = params[service]["zeta"]
    total_flux = params[service]["total_flux"]
    total_weighted_flux = params[service]["total_weighted_flux"]

    crit_dfs = {}
    for hazard in hazards:
        crit_dfs[hazard] = load_criticality_data(hazard, crit_dir, zeta)

    simplified = pd.read_csv(simplified, index_col="id").drop(columns=["Unnamed: 0"])

    first_row = True
    for variable, unit in zip(variables, units):

        totals_df = {}
        for hazard, crit_df in crit_dfs.items():
            crit_df["epoch"] = crit_df["epoch"].replace(baseline_map)
            simplified_df = simplify_crit_df(crit_df, simplified)
            totals_df[hazard] = get_national_totals(simplified_df, variable)

        # plotting starts here
        fig, axs = plt.subplots(1, 4, figsize=(12, 2), sharey=False)
        i = 0
        for ax, hazard in zip(axs, hazards):
            totals_df_hazard = totals_df[hazard]
            totals_df_hazard = totals_df_hazard.loc[idx[hazard, :, :, :], :]

            baseline = totals_df_hazard.loc[(hazard, 'baseline', 'historical', 'mean'), hazard]
            epochs = ['baseline', '2030', '2050', '2080']
            scenarios = ['ssp126', 'ssp245', 'ssp585']
            scenario_labels = {
                "historical": "Historical",
                "ssp126": "SSP1-2.6",
                "ssp245": "SSP2-4.5",
                "ssp585": "SSP5-8.5"
            }
            
            # define the colormap
            colors_sns = sns.color_palette("Spectral_r", n_colors=4)
            colors = {
                'historical': colors_sns[0],
                'ssp126': colors_sns[1],
                'ssp245': colors_sns[2],
                'ssp585': colors_sns[3]
            }

            # add some readable labels
            variable_labels = {
                "isolated": "access loss",
                "detoured": "rerouted",
                "wdetoured": "travel time loss",
                "base_flux": "using road",
            }

            x = np.arange(len(epochs))
            rows = [{"epoch": "baseline", "scenario": "historical", "value": baseline}]
            for ssp in scenarios:
                for e in epochs[1:]:
                    rows.append({
                        "epoch": e,
                        "scenario": ssp,
                        "value": totals_df_hazard.loc[(hazard, e, ssp, 'mean'), hazard]
                    })
            plot_df = pd.DataFrame(rows)
            plot_df["scenario"] = plot_df["scenario"].map(scenario_labels)

            sns.barplot(data=plot_df, x="epoch", y="value", hue="scenario",
                        ax=ax, palette=list(colors.values()), dodge=True,
                        width=0.8,
                        edgecolor="k", linewidth=0.5, order=epochs,
                        hue_order=list(scenario_labels.values()))

            ax.set_xticks(x)
            ax.set_xticklabels(epochs)
            ax.yaxis.set_major_formatter(EngFormatter())
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.yaxis.grid(True, alpha=0.5, zorder=0)
            ax.get_legend().remove()

            if not first_row:     
                ax.set_xlabel(f'{hazard.title()}', fontweight="bold")
            else:
                ax.set_xlabel('')

            if i != 0:
                ax.set_ylabel("")
            else:
                ax.set_ylabel(f"Expected Annual\n{variable_labels[variable].title()}\n({unit})", fontweight="bold")
            i += 1
        
        if first_row:
            handles, lbels = ax.get_legend_handles_labels()
            fig.legend(
                handles,lbels,
                loc='upper center', 
                bbox_to_anchor=(0.5, 1.105),
                ncol=len(lbels),
                frameon=False,
            )
            plt.subplots_adjust(bottom=0.8)

        fig.tight_layout()
        first_row = False
        # break #! while dev
# %%

# ttra_dir = Path("/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data")



# simplified = ttra_dir / "accessibility" / "tza_road_simplifications.csv"
# crit_dir = ttra_dir / "accessibility" / service
# road_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"
# admin1 = ttra_dir / "snakemake" / "input" / "admin" / "level01.geoparquet"





# # load the criticality dfs (a little slow)
# crit_dfs = {}
# for hazard in hazards:
#     print(f"Loading criticality data for hazard {hazard}...")
#     hazard_crit_files = glob(f"{crit_dir}/{hazard}/*/annual.parquet")
#     crit_df_list = []
#     for crit_file in tqdm(hazard_crit_files, leave=False):
#         crit_subregion = pd.read_parquet(crit_file)
#         crit_subregion = crit_subregion.drop_duplicates()
#         crit_df_list.append(crit_subregion)
#     print(f"All files loaded for hazard {hazard}. Combining...")
#     crit_df = (
#         pd.concat(crit_df_list)
#         .drop_duplicates()
#         .groupby(id_cols + ["metric"])
#         .agg({"expected": "max"}) # ! spurious zero-value duplicates: take max
#         .reset_index()
#         .pivot(index=id_cols, columns="metric", values="expected")
#         .reset_index()
#         .set_index("id")
#     )
#     crit_df["isolated"] = zeta * crit_df["isolated"]  # persons
#     crit_df["detoured"] = zeta * crit_df["detoured"]  # person-hours
#     crit_df["wdetoured"] = zeta * crit_df["wdetoured"] / 60 # minutes to hours
#     crit_dfs[hazard] = crit_df

# print(len(crit_dfs[hazard]), "road segments with criticality data for hazard", hazard)

# %% simplify road network to avoid double-counting disruptions across degree-2 nodes









# first_row = True
# for variable, unit in zip(variables, units):

#     totals_df = {}
#     for hazard, crit_df in crit_dfs.items():
#         crit_df["epoch"] = crit_df["epoch"].replace(baseline_map)
#         simplified_df = simplify_crit_df(crit_df, simplified)
#         totals_df[hazard] = get_national_totals(simplified_df, variable)
#         # crit_df = crit_df.join(simplified, how="left")

#         # # only take max from continuous segments to avoid double-counting
#         # group_cols = ["hazard", "epoch", "scenario", "range", "segment_id"]
#         # print(f"Length before grouping segments for {hazard}:", len(crit_df))
#         # simplified_df = crit_df.reset_index().groupby(group_cols).agg({variable: "max"})
#         # print(f"Length after grouping segments for {hazard}:", len(simplified_df))
        
#         # # now sum across segments to get national totals per scenario
#         # group_cols = ["hazard", "epoch", "scenario", "range"]
#         # totals = simplified_df.reset_index().groupby(group_cols).agg({variable: "sum"})
#         # totals = totals.rename(columns={variable: hazard})
#         # totals_df[hazard] = totals

    # plotting starts here
    fig, axs = plt.subplots(1, 4, figsize=(12, 2), sharey=False)#, constrained_layout=True)
    i = 0
    for ax, hazard in zip(axs, hazards):
        totals_df_hazard = totals_df[hazard]
        totals_df_hazard = totals_df_hazard.loc[idx[hazard, :, :, :], :]

        baseline = totals_df_hazard.loc[(hazard, 'baseline', 'historical', 'mean'), hazard]
        epochs = ['baseline', '2030', '2050', '2080']
        scenarios = ['ssp126', 'ssp245', 'ssp585']
        scenario_labels = {
            "historical": "Historical",
            "ssp126": "SSP1-2.6",
            "ssp245": "SSP2-4.5",
            "ssp585": "SSP5-8.5"
        }
        
        # sort out the colormap
        colors_sns = sns.color_palette("Spectral_r", n_colors=4)
        colors = {'historical': colors_sns[0], 'ssp126': colors_sns[1], 'ssp245': colors_sns[2], 'ssp585': colors_sns[3]}

        # add some readable labels
        variable_labels = {
            "isolated": "access loss",
            "detoured": "rerouted",
            "wdetoured": "travel time loss",
            "base_flux": "using road",
        }

        x = np.arange(len(epochs))
        rows = [{"epoch": "baseline", "scenario": "historical", "value": baseline}]
        for ssp in scenarios:
            for e in epochs[1:]:
                rows.append({
                    "epoch": e,
                    "scenario": ssp,
                    "value": totals_df_hazard.loc[(hazard, e, ssp, 'mean'), hazard]
                })
        plot_df = pd.DataFrame(rows)
        plot_df["scenario"] = plot_df["scenario"].map(scenario_labels)

        sns.barplot(data=plot_df, x="epoch", y="value", hue="scenario",
                    ax=ax, palette=list(colors.values()), dodge=True,
                    width=0.8,
                    edgecolor="k", linewidth=0.5, order=epochs,
                    hue_order=list(scenario_labels.values()))

        ax.set_xticks(x)
        ax.set_xticklabels(epochs)
        ax.yaxis.set_major_formatter(EngFormatter())
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.yaxis.grid(True, alpha=0.5, zorder=0)
        ax.get_legend().remove()

        if not first_row:     
            ax.set_xlabel(f'{hazard.title()}', fontweight="bold")
        else:
            ax.set_xlabel('')

        if i != 0:
            ax.set_ylabel("")
        else:
            ax.set_ylabel(f"Expected Annual\n{variable_labels[variable].title()}\n({unit})", fontweight="bold")
        i += 1
    
    if first_row:
        handles, lbels = ax.get_legend_handles_labels()
        fig.legend(
            handles,lbels,
            loc='upper center', 
            bbox_to_anchor=(0.5, 1.105),
            ncol=len(lbels),
            frameon=False,
        )
        plt.subplots_adjust(bottom=0.8)

    fig.tight_layout()
    first_row = False # only one legend for pair
    # break #! while dev


# %%