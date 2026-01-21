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

```bash
rclone sync '/Users/alison/Library/CloudStorage/OneDrive-SharedLibraries-OxfordInfrastructureAnalyticsLimited/WBG Tanzania transport resilience - Project/4 Data/incoming_data/hazards' "/Volumes/Expansion/02_oia/oia-tanzania-2025/incoming_data/hazards" \
  --dry-run \
  --checksum \
  --progress \
  -v
```