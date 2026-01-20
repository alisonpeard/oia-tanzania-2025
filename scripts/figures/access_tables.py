"""
Create tables of top N most critical road segments for each service,
scenario, and variable.

NOTE: There are some spurious zeros in the data that need to be
investigated further.
"""
# %%
from glob import glob
from tqdm import tqdm
import numpy as np
import pandas as pd
import geopandas as gpd

def format_subregion_name(subregion:str) -> str:
    subregion = subregion.lower()
    subregion = subregion.replace(" ", "_")
    subregion = subregion.replace("/", "-")
    return subregion


service = "school"
hazards = ["pluvial", "fluvial", "coastal", "landslide"] # ! sum across all hazards later
simplified = "/Users/alison/Downloads/flows/tza_road_simplifications.csv"
crit_dir = f"/Users/alison/Local/github/oia-tanzania-2025/results/{service}_access/tza_roads_edges"
road_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"
admin1 = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_1.gpkg"

# additional flow information
if service == "school":
    # from school_criticality.py
    zeta = 1.0
    total_flux = 18_567_485
    total_weighted_flux = 718_021_545
elif service == "health":
    # from health_criticality.py
    zeta = 0.00214
    total_flux = 61_567_247
    total_weighted_flux = 1_091_705_149
else:
    raise ValueError("Unknown service")

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
statistic = "mean"
N = 1000
variables = ["isolated", "detoured", "wdetoured"]
scenarios = ["historical", "ssp245"]

for variable in variables:
     print(f"Processing variable: {variable}")
     for scenario in scenarios:
        print(f"  Scenario: {scenario}")

        if scenario == "historical":
            # landslides and floods have different baselines
            epoch = ["2015", "2020"]
            outscen = "historical"
        else:
            epoch = ["2050"]
            outscen = "2050_" + scenario

        list_for_concat = []
        for hazard, crit_df in crit_dfs.items():
            df_sub = (
                crit_df[
                    (crit_df["scenario"] == scenario) &
                    (crit_df["epoch"].isin(epoch)) &
                    (crit_df["range"] == statistic)
                ][[variable]]
                .groupby(level=0).max()  # or .sum() — dedupe by index
                .rename(columns={variable: hazard})
            )
            list_for_concat.append(df_sub)

        full_df = pd.concat(list_for_concat, axis=1, join="inner")
        full_df["total"] = full_df.sum(axis=1)

        roads = gpd.read_parquet(road_path).set_index("id")
        segments = pd.read_csv("/Users/alison/Downloads/flows/tza_road_simplifications.csv", index_col="id")
        roads = roads.join(segments[["segment_id"]], how="left")
        admin = gpd.read_file(admin1)
        admin["province"] = admin["shapeName"].apply(format_subregion_name)

        columns = ['id', 'segment_id', 'road_agency_link_id', 'province', 'road_class', 'length_m'] + hazards + ['total']

        top_N = full_df.nlargest(N, "total").sort_values("total", ascending=False)
        top_N = top_N.join(roads[["road_class", "geometry", "length_m", "road_agency_link_id", "segment_id"]], how="left")
        top_N = gpd.GeoDataFrame(top_N, geometry="geometry").to_crs(admin.crs)
        top_N = top_N.sjoin(admin[["province", "geometry"]], how="left", predicate="intersects")
        top_N = top_N.reset_index()[columns]

        for col in hazards + ["total"]:
            top_N[col] = top_N[col] * zeta
            if variable in ["isolated", "detoured"]:
                top_N[f"{col}_pct"] = top_N[col] / total_flux * 100
            elif variable == "wdetoured":
                top_N[f"{col}_pct"] = top_N[col] / total_weighted_flux * 100
            else:
                raise ValueError("Unknown variable")

        top_N = top_N.sort_values("total_pct", ascending=False)
        outpath = f"/Users/alison/Desktop/accessibility_tables/raw/{service}_{outscen}_{variable}_top{N}.csv"
        top_N.round(4).to_csv(outpath, index=False)
        print(f"Saved top {N} to {outpath}.")

        # top_N with road_agency_link_id only
        def sum_unique(x:pd.Series) -> float:
            x = np.unique(x)
            return x.sum()

        def concat_unique(x:pd.Series) -> str:
            x = np.unique(x)
            return " / ".join(x)

        outpath = f"/Users/alison/Desktop/accessibility_tables/grouped/{service}_{outscen}_{variable}_top{N}.csv"

        top_N_grouped = top_N.groupby("road_agency_link_id").agg({
            'province': concat_unique,
            'road_class': concat_unique,
            'length_m': sum_unique,
            'pluvial': sum_unique,
            'fluvial': sum_unique,
            'coastal': sum_unique,
            'landslide': sum_unique,
            'total': sum_unique,
            "total_pct": sum_unique
        }).reset_index().sort_values("total", ascending=False).round(4)

        top_N_grouped["road_class"] = top_N_grouped["road_class"].replace(" Road", "", regex=True)

        top_N_grouped.to_csv(
            outpath, index=False
        )
        print(f"Saved grouped top {N} to {outpath} .")

        top_N["main_hazard"] = top_N[hazards].idxmax(axis=1)
        # print some summary statistics
        print(f"\nSummary statistics for top {N}")
        print(f"Most critical under {service} {outscen} {variable}:")
        print("----------------------------------")
        print("Main hazard value counts:", top_N["main_hazard"].value_counts() / N * 100)
        print("Province value counts", top_N["province"].value_counts())
        print("Road class value counts", top_N["road_class"].value_counts())
        print("Length (m) statistics", top_N["length_m"].describe())
# %% 