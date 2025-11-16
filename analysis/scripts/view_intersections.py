# %%
import geopandas as gpd


# replace with path to file
subregion = ["dar_es_salaam", "pwani", "morogoro"][2]
exposure_file = f"../../results/exposure_unsplit/tza_road/{subregion}.geoparquet"

# helper functions for working with hazard columns
def list_hazcols(exposure:gpd.GeoDataFrame) -> list[str]:
    """List hazard columns in exposure dataframe."""
    hazcols = [c for c in exposure.columns if c.startswith("hazard-")]
    return hazcols

def get_hazcol(hazard:str, epoch:int, scenario:str, rp:int) -> str:
    """Get hazard column name."""
    hazcol = f"hazard-{hazard}_{epoch}_{scenario}_rp{str(rp).zfill(5)}"
    return hazcol

def extract_hazard_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract hazard, epoch, scenario, and return period from hazard column name."""
    parts = hazcol.replace("hazard-", "").split("_")
    hazard = parts[0]
    epoch = parts[1]
    scenario = parts[2]
    rp = int(parts[3].replace("rp", ""))
    return hazard, epoch, scenario, rp

def get_available_scenarios(exposure):
    """Get available hazards, epochs, scenarios, and return periods in exposure dataframe."""
    hazcols = list_hazcols(exposure)
    epochs = set()
    scenarios = set()
    hazards = set()
    rps = set()
    for hazcol in hazcols:
        hazard, epoch, scenario, rp = extract_hazard_info(hazcol)
        hazards.add(hazard)
        epochs.add(epoch)
        scenarios.add(scenario)
        rps.add(rp)
    return {
        "hazards": sorted(hazards),
        "epochs": sorted(epochs),
        "scenarios": sorted(scenarios),
        "rps": sorted(rps),
    }


# %% code starts here
exposure = gpd.read_parquet(exposure_file)
exposure = exposure.to_crs(epsg=4326)  # ensure in WGS84

print("see all the hazard options:")
print(get_available_scenarios(exposure))

print("\nget a list of all the hazard columns:")
hazcols = list_hazcols(exposure)
print(hazcols[:5])  # print first 5 for brevity

print("\nsee what non-hazard columns are present:")
non_hazard_cols = [c for c in exposure.columns if c not in hazcols and c != "geometry"]
print(non_hazard_cols)

print("\nget the hazard info for the first column:")
print(extract_hazard_info(hazcols[0]))

print("\nview results a specific hazard column:")
hazcol = get_hazcol("hd35", 2050, "ssp126", 100)
print(exposure[hazcol].head(3))


# (optional) plot the hazard column
if True:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(subplot_kw={"projection": ccrs.PlateCarree()})

    exposure.plot(hazcol, cmap="YlOrRd", ax=ax, legend=True)
    ax.add_feature(cfeature.OCEAN, zorder=10)
    ax.add_feature(cfeature.COASTLINE, zorder=11)
    ax.add_feature(cfeature.LAND)
 

# %%