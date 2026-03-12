### Pre-processing scripts for WBG project: Tanzania 2025

Script to pre- and post-process data for the direct damage and network analyses.

**To do:**
- [ ] Make heat hazard maps
- [ ] Pre-process Fathom data
- [ ] Prepare config files
- [ ] Prepare hazard data
- [ ] Prepare admin data
- [ ] Prepare asset data
- [ ] Post-process results
- [ ] Make figures

---

## Notes

Input data is stored in `config.paths.incoming_data` as in `config.json`.

### 

### Asset data

- Format: `"{processed_data}/assets/{asset}_{geom}.geoparquet"` with `geom` in [`edges`, `nodes`, `polygons`]
- Remove disused-status railway assets
- Save as geoparquet rather than parquet for compat with direct damages

### Hazard data

#### General

All hazards processed to standard format.

```
{processed_data}/hazards/cleaned/{type}_{year}_{scenario}_rp{rp.zfill(5)}.tif
```

- Fathom floods: `fathom.py` to resample 30 m to 90 m and mosaic tiles.
- CHAZ tropical cyclones: `chaz.py` script to rename files and add assumptions (check docstring for details).
- Extreme heat: Created by Alison in correct format, copy manually to cleaned directory.
- Landslides: `landslides.py` script to rename files
- NB: Create a copy of a pluvial fathom file called `_reference.tif` with the desired grid.

#### Heat hazard

### Config files

- Additional processing on top of Raghav's stuff

### Administrative boundaries / subregions

- Create file `"{processed_data}/admin/{ADMIN_LEVEL}.gpkg"` with CRS [ENTER] and field "subregion" with admin names.


# Extreme heat hazard map creation

Code to create extreme heat hazard maps is in `scripts/make_heat_hazards/`. The `yearly_stats.py` extracts maps of the annual (a) number of days exceeding 35°C or (b) annual maximum temperatures. Input netCDF files from CORDEX should be in `config['paths']['cordex_data']`.

## Days exceeding 35°C per annum (HD35) hazard maps

This de-trends the data using a generalised linear model (GLM) and fits a discrete GPD (d-GPD; for count data) of Hitz (2024)[^1].

### De-trended model

Script `make_heat_hazards/hd35_hazmaps.py` creates the hazard maps using extreme value theory. Script `make_heat_hazards/hd35_tiffs.py` makes a final tiff file for each scenario by aggregating the results for each CORDEX ensemble member.

**Steps:**
- Fit a time-varying Poisson or Binomial GLM to the data
- Use GLM to predict and subtract the time-varying expected value and obtain stationary residuals
- Choose a threshold above which to define 'extremes values', e.g., the 80th percentile.
- Fit a d-GPD to this.
- Calculate return levels.
- Re-add the time-varying expected values.

**Advantages:**
- Can use all data for fits and extract more exceedances

**Limitations:**
- Threshold choice is subjective
- Doesn't account for multiplicative seasonality

#### References

[^1]: Hitz, Davis and Samorodnitsky (2024). Discrete Extremes. Journal of Data Science, 22(4), 524-536. doi: [10.6339/24-JDS1120](https://doi.org/10.6339/24-JDS1120)


## Annual maximum temperature (TASMAX)

This is almost identical to the HD35 workflow except we use OLS regression to fit the trend model and fit a standard generalised extreme value (GEV) distribution to the annual maximum temperature instead.

## Running the intersections

Modify the following to safely sync the data with your local storage:

```bash
rclone sync '/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/snakemake_data' "/Volumes/Expansion/02_oia/oia-tanzania-2025/snakemake_data" \
  --checksum \
  --progress \
  -v
```


Run intersections with direct damages [workflow](https://github.com/oi-analytics/direct-damages-workflow) with the following config:

```yaml
input: "/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/snakemake_data"
results: "/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/results"
local_crs: 32735
country: "tanzania"
admin_level: "01"
bbox: [29, 41, -12, -1]
asset_geoms:
  - "tza_roads_edges"
  - "tza_roads_bridges_and_culverts_nodes"
  - "tza_railway_edges"
  - "tza_airports_polygons"
  - "tza_iww_ports_polygons"
  - "tza_maritime_ports_polygons"
hazards:
  - "fluvial"
  - "pluvial"
  - "coastal"
  - "cyclone"
  - "landslide"
  - "hd35"
  - "tasmax"
```