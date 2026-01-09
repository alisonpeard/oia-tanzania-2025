# %%
import pandas as pd
import geopandas as gpd
import sys 
sys.path.append("..")

# import utils.data as du
import utils.plot as pu

ead_path = "/Users/alison/Downloads/flows/school_disruption/ead_by_province.csv"
admin_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/admin/tza_admin_1.gpkg"
ead_results = pd.read_csv(ead_path)

ead_results = ead_results.pivot(
    index=["hazard", "epoch", "scenario", "subregion", "stat", "base_flux"],
    columns="metric",
    values="expected"
).reset_index()

ead_results["total_disrupted"] = ead_results["total_isolated"] + ead_results["total_rerouted"]
ead_results["total_weighted_detour_hrs"] = ead_results["total_weighted_detour"] / 60  # to walking hrs

# %%
admin = gpd.read_file(admin_path)
admin["province"] = admin["shapeName"].str.lower()

ead_results = ead_results.merge(
    admin[["province", "geometry"]],
    left_on="subregion",
    right_on="province",
    how="left",
)
ead_gdf = gpd.GeoDataFrame(ead_results, geometry="geometry", crs=admin.crs)
# %%
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
# import FuncFormatter
from matplotlib.ticker import FuncFormatter

hazard = "pluvial"
epoch = 2050
scenario = "ssp245"


plot_data = ead_gdf[
    (ead_gdf["hazard"] == hazard) &
    (ead_gdf["epoch"] == epoch) &
    (ead_gdf["scenario"] == scenario)
].copy()

def millions(x, pos):
    return '%1.0f' % (x * 1e-6)

def thousands(x, pos):
    return '%1.0f' % (x * 1e-3)

def percent(x, pos):
    return '%1.1f' % (x)

metrics = ["base_flux","perc_disrupted", "total_isolated", "total_weighted_detour_hrs"]
labels = ["Total school traffic\n(millions of commuters)", "Traffic at-risk of disruption\n(%)",
          "Access at-risk\n(1000s of commuters)", "Additional travel time\n(1000s of hours)"]
formatters = [millions, percent, thousands, thousands]

fig, axs = plt.subplots(1, len(metrics),
                        figsize=(2.5 * len(metrics), 3),
                        subplot_kw={'projection': ccrs.PlateCarree()})

for ax, metric, label, formatter in zip(axs, metrics, labels, formatters):

    if plot_data.empty:
        raise ValueError("No data for the selected parameters.")

    plot_data.plot(
        column=metric,
        ax=ax,
        legend=True,
        edgecolor='k',
        linewidth=0.1,
        cmap="OrRd",
        legend_kwds={
            "label": label,
            "orientation": "horizontal",
            "pad": 0.025,
            "format": FuncFormatter(formatter)
        },
        missing_kwds={"color": "lightgrey", "label": "No data"},
    )
    ax.axis("off")
    pu.add_geofeatures(ax)
plt.show()
# %%