## Quickstart

The following code will intersect an asset (vector in `results/input/assets`) with all hazard scenarios (all rasters in `results/input/hazards/`)
and compute damage and rehabilitation costs.

E.g., for roads in Tanzania, `tza_road`:

```bash
snakemake --cores 4 ../results/damage_costs/tza_road/.all
```

The output is a geoparquet file with the following format

| id | hazard-{scenarios} | damage-{scenarios} | cost-{scenarios} | geometry |
|-----|--------------------|--------------------|------------------|----------|
| ... | float32            | float32            | float32          | geometry |

## To do

- Add handling for multiple damage curves per asset+hazard combination (e.g., min, max, different sources)
- Finish unsplitting code (requires no dulpicate IDs in asset files)
- Add handling for the full range of hazard types (e.g., drought, cyclones)

## Input data

Store all input data somewhere local and set `inputs` in `config.yaml` to point to that location. For each new hazard or asset dataset, create a rule and script to process it into the standardised format in `results/input` and place them in the `hazards` or `assets` folders respectively. It doesn't matter how these are coded as long as their outputs have the correct format and location for the workflow. Processing can also be done externally, and the files simply placed in the correct location in `results/input`.

Data stored in `results/input` should have the following format:

| Data type       | Format       | Location                                      |
|-----------------|--------------|-----------------------------------------------|
| Hazard     | GeoTIFF      | `/results/input/hazards/{hazard}/{subcategory}/{epoch}/{scenario}/rp{rp}.tif` |
| Assets         | GeoParquet   | `/results/input/assets/{asset}/{subregion}.geoparquet` |

The `{hazard}` wildcard must match the hazard names used to classify damage curves and rehabilitation costs. Asset files have the following requirements:
- Have a single geometry type per asset, e.g., LineString, Polygon, Point (no MultiLineStrings)
- Have WGS84 projection
- Have three columns: (unique) `id`, `asset_type` and `geometry`. `asset_type` column that matches naming for damage curves and rehab costs

Hazard rasters must have properly defined NoData values.

To do the damage estimations, the workflow uses damage curves and rehabilitation costs stored in `config/damage_curves` and `config/rehab_costs`. These should be organised as follows:

| Data type       | Format       | Location                                      |
|-----------------|--------------|-----------------------------------------------|
| Damage curves  | CSV          | `config/damage_curves/{hazard}/{asset_type}/{source}.csv` |
| Rehabilitation costs | CSV     | `config/damage_curves/{hazard}/{source}.csv`|

Rehabilitation costs are indexed `asset_type`.

Use '#' to mark comment lines in the CSV files.

## Notes on datasets

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

### STORM Cyclone data

Currently have historical and 2080 RCP 8.5 data from 2--3 different models. We need to decide how to combine these. Perhaps by min, max, and medians estimats?

### Asset datasets

Stored in geoparquet format. Some projections need to be aligned.

![](analysis/figures/inputs/tza_road_network.png)
![](analysis/figures/inputs/tza_railway_network.png)
![](analysis/figures/inputs/tza_maritime_ports_network.png)


## Rehabilitation costs

These are nuanced because they depend on the hazard type. Extreme heat buckles tracks, so rehabilitation costs only include the cost of replacing the buckled tracks. Flooding washes away the track bed, so rehabilitation costs include rebuilding the track bed as well as replacing the tracks.

#### References

[CCDR-Somalia repository](https://github.com/alisonpeard/oia-somalia-2025)
