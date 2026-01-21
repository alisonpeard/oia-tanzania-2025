### Pre-processing

Script to pre-process data for the direct damage and network analyses.

#### Asset data

- Format: `"{processed_data}/assets/{asset}_{geom}.geoparquet"` with `geom` in [`edges`, `nodes`, `polygons`]
- Remove disused-status railway assets
- Save as geoparquet rather than parquet for compat with direct damages

#### Hazard data

All hazards processed to standard format.

```
"{processed_data}/hazards/cleaned/{type}_{year}_{scenario}_rp{rp.zfill(5)}.tif
```

- Fathom floods: `fathom.py` to resample 30 m to 90 m and mosaic tiles.
- CHAZ tropical cyclones: `chaz.py` script to rename files and add assumptions (check docstring for details).
- Extreme heat: Created by Alison in correct format, copy manually to cleaned directory.
- Landslides: `landslides.py` script to rename files
- NB: Create a copy of a pluvial fathom file called `_reference.tif` with the desired grid.

#### Config files

- Additional processing on top of Raghav's stuff

#### Administrative boundaries / subregions

- Create file `"{processed_data}/admin/{ADMIN_LEVEL}.gpkg"` with CRS [ENTER] and field "subregion" with admin names.

### Post-processing

### Analysis and visualisations


# Hazard map creation

## d-GPD (for count data)

### Stationary (simplest) model

Steps:
- Choose 30-year windows around the epoch-of-interest
- Choose a threshold of zero (days of extreme temperatures)
- Fit a d-GPD to each 30-year window
- Calculate return levels

Limitations:
- Does not account for trend within the 30-year window
- Threshold of zero may be too low for GPD to be justified

### De-trended model

Steps:
- Fit a time-varying Poisson or Binomial GLM to the data
- Use it to subtract the time-varying expected value and obtain stationary residuals
- Choose a threshold of zero
- Fit a d-GPD to this
- Calculate return levels
- Re-add the time-varying expected values

Advantages:
- Can use all data for fits and extract more exceedances

Limitations:
- Threshold of zero may be inappropriate
- Doesn't account for multiplicative seasonality

### Non-stationary model

Steps:
- Same as detrended model
- Except time-varying scale parameter

Limitations:
- Threshold may be inappropriate

## References
- https://arxiv.org/abs/1707.05033

```bash
rclone sync '/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/snakemake_data' "/Volumes/Expansion/02_oia/oia-tanzania-2025/snakemake_data" \
  --checksum \
  --progress \
  -v
```