## Quickstart

Clone the repository:

```bash
git clone git@github.com:alisonpeard/oia-tanzania-2025.git
```

Make a conda environment from the provided `environment.yaml` file:

```bash
conda env create -f environment.yaml
conda activate oia-direct-damages
```

Download the input data from the shared drive and place it somewhere local.

Change `workflow/config.yaml` and set the `inputs` key to point to your local folder for input data. In that folder place:

- Vector asset files
    - `{inputs}/assets/{asset}_{geom}.parquet`
- Admin boundary files
    - `{inputs}/admin/tza_admin_{level}.gpkg`
- Hazard raster files
    - `{inputs}/hazards/{hazard}_{epoch}_{scenario}_rp{rp}.tif`
    - Copy-paste these to `results/hazards/aligned/`

Run all intersections and damage calculations for the pluvial flood hazard on the Tanzania road edges asset (with `-n` flag for a dry run):

```bash
snakemake --cores 4 ../results/flags/tza_railway_edges/pluvial/.processed -n
```

---

### Assets

Assets should be placed in `{input}/assets/` with name format: `{asset}_{geom}.parquet` where:
- `geom`: geometry type, e.g., `nodes`, `edges`, `polygon`
- `asset`: asset type, e.g., `tza_airports`, `tza_railway`
- `subregion`: subregion name from admin file, e.g., `dar_es_salaam`

These are pre-processed by the rules in `rules/assets.smk` to have the following requirements:
- Have a single geometry type per asset, e.g., LineString, Polygon, Point (no MultiLineStrings)
- Have WGS84 projection
- Have three columns: (unique) `id`, `asset_type`, `unit`, `unit_type`, `geometry`. The `asset_type` column should matches naming for damage curves and rehab costs

### Hazards

Hazards are pre-processed because it took ages. Pre-processed hazards should be placed in `results/hazards/aligned/` with name format:

```
{hazard}_{epoch}_{scenario}_rp{rp}.tif
```

where:

- `hazard`: hazard name (e.g., `pluvial`, `cyclone`). Should match the hazard used in damage curves and rehabilitation costs.
- `epoch`: time horizon (e.g., `2020`, `2050`, `2080`)
- `scenario`: climate scenario (e.g., `historical`, `ssp245`, `ssp585`)
- `rp`: return period (e.g., `00010`, `00050`, `00100`).

Hazard rasters should have WGS84 projection and have proper `NoData` values defined. Rules to pre-process hazard rasters are in `rules/hazards` and the rule to align all the pre-processed hazards to a common grid is in `rules/hazards.smk`.

---


The workflow uses damage curves, design standards, and rehabilitation costs stored in `config/damage_curves`, `config/design_standards` and `config/rehab_costs`. These should be organised as follows:

| Data type       | Format       | Location                                      |
|-----------------|--------------|-----------------------------------------------|
| Damage curves  | CSV          | `config/damage_curves/{hazard}/{asset_type}.csv` |
| Design standards  | CSV          | `config/design_standards/{hazard}.csv` |
| Rehabilitation costs | CSV     | `config/damage_curves/{hazard}.csv`|

Rehabilitation costs and design standards are indexed by `asset_type`.

Damage curves, have an `intensity` column, then three columns for damage fractions: `damage_fraction_max`, `damage_fraction_min`, `damage_fraction_mean`. Use commenting `#` to note the units of intensity. Costs are specified in `costs_per_unit` with a separate `unit_type` column indicating `m` (LineStrings) or `sqm` (Polygons) or `unit` (Points). Example processing scripts to get input costs and curves into the right format are in `analysis/scripts/`.
