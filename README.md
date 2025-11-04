[Ref. Somalia repository](https://github.com/alisonpeard/oia-somalia-2025)

1. Load hazard data into standard format
2. Load any asset data into standard format
3. Do slicing as necessary
    1. rasters
    2. vectors
4. Run vector-raster intersections
    1. points
    2. lines
    3. polygons
5. Calculate direct damages using damage curves
6. Calculate rehabilitation costs using rehab costs
7. Re-concatenate results as necessary
8. Save a results file similar to original Open-GIRA output structure (maybe a bit simpler)

## Data structure

| Data type       | Format       | Location                                      |
|-----------------|--------------|-----------------------------------------------|
| Hazard     | GeoTIFF      | `/results/input/hazards/{source}/{hazard_type}/{epoch}/{scenario}/rp{rp}.tif` |
| Assets         | GeoParquet   | |
| Damage curves  | CSV          | `config/damage_curves/{hazard}/{asset}.csv` |
| Rehabilitation costs | CSV     | `config/damage_curves/{hazard}/{asset}.csv`|


## Possibly useful scripts and rules from open-gira

## Hazard data

All processed hazard files are stored as `/results/input/hazards/{source}/{hazard_type}/{epoch}/{scenario}/rp{rp}.tif`

### Fathom flood data

The Fathom data is provided in 1° rasters, in separate (nested) folders for each flood-driver, time horizon, climate scenario, and return period. Original files are in 1 arc second resolution (~30 m), which is very high and slow, we resample to 3 arc second (~90 m) for processing efficiency.

Input tiles should be organised as follows:

```bash
fathom/{floodtype}/{epoch}/{scenario}/1in{rp}/*.tif
```

with categories

| Variable   | Values (TBC)              |
|------------|---------------------------|
| flood type | pluvial, fluvial, coastal |
| epoch      | 2020, 2050, 2080          |
| scenario   | historical, SSP2-4p5, SSP5-8p5 |
| return period (rp) | 00005, 00010, 00100, 00200, 00500, 01000 |

To process them with open-gira, run:

```bash
snakemake --rerun-incomplete --cores 6 -- fathom_all_historical
snakemake --rerun-incomplete --cores 6 -- fathom_all_scenario
```

## Infrastructure data

We currently have 
- network.gpkg
- edges.parquet
- nodes.parquet

Previously, on Open-GIRA

```bash

snakemake --rerun-incomplete --cores 4 -- results/direct_damages/somalia-latest_filter-road-residential/hazard-fathom-pluvial/EAD_and_cost_per_RP/slice-{0..63}.geoparquet
```

i.e., the syntax is

```bash
snakemake --rerun-incomplete --cores <N> -- results/direct_damages/<INFRA>/<HAZARD>/<METRIC>/slice-{0..<NUM_SLICES-1>}.geoparquet
```

## Damage curves

## Rehabilitation costs

These are nuanced because they depend on the hazard type. Extreme heat buckles tracks, so rehabilitation costs only include the cost of replacing the buckled tracks. Flooding washes away the track bed, so rehabilitation costs include rebuilding the track bed as well as replacing the tracks.
