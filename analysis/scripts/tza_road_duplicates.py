# %% check input vector data for duplicates
import os
import geopandas as gpd
import matplotlib.pyplot as plt

input_asset_dir = "../../results/input/assets/tza_road/"
subregions = os.listdir(input_asset_dir)
subregions = [s for s in subregions if s.endswith(".geoparquet")]

for subregion in subregions:
    gdf_ref = gpd.read_parquet(os.path.join(input_asset_dir, subregion))
    gdf_ref = gdf_ref.set_index("id").sort_index()
    duplicates = gdf_ref.index[gdf_ref.index.duplicated()]

    if len(duplicates) > 0:
        print(f"Found {len(duplicates)} duplicates for {subregion}: {duplicates}")
        duplicates = list(set(duplicates))

        fig, axs = plt.subplots(2, 4, figsize=(15, 8))
        
        axs = axs.flatten()
        for i, ax in enumerate(axs):
            sample_duplicate = gdf_ref[gdf_ref.index == duplicates[i]]
            sample_duplicate = sample_duplicate.reset_index().reset_index(drop=False)
            sample_duplicate.plot('index', ax=ax, categorical=True, legend=True)
            ax.set_title(f"{duplicates[i]}")

        fig.savefig(f"../figures/tza_road_duplicates_{subregion}.png")
    else:
        print(f"No duplicates found for {subregion}.")
# %%