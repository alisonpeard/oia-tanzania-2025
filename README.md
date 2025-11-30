## Quickstart

1. Clone the repository:
```bash
git clone git@github.com:alisonpeard/oia-tanzania-2025.git
```

2. Create and activate the conda environment:
```bash
cd oia-tanzania-2025
conda env create -f environment.yaml
conda activate oia-direct-damages
```

3. Download the input data from the shared drive and place it locally.

4. In `workflow/config.yaml`, set the `inputs` key to your input data location. The input data structure should be:

    - Vector asset files: `{inputs}/assets/{asset}_{geom}.parquet`
    - Admin boundary files: `{inputs}/admin/tza_admin_{level}.gpkg`
    - Hazard raster files: `{inputs}/hazards/{hazard}_{epoch}_{scenario}_rp{rp}.tif`

5. Copy `{inputs}/hazards/{hazard}_{epoch}_{scenario}_rp{rp}.tif` to `results/hazards/aligned/`. These are pre-processed.

6. Run all intersections and damage calculations for the pluvial flood hazard on the Tanzania road edges asset (add `-n` flag for dry run):
```bash
cd workflow
snakemake --cores 4 ../results/flags/tza_railway_edges/pluvial/.processed -n
```

---

## To do
- Separate hazard pre-processing into its own workflow
- Add scripts for figures

---

### Assets

Assets should be placed in `{input}/assets/` with format: `{asset}_{geom}.parquet` where:
- `asset`: asset type (e.g., `tza_airports`, `tza_railway`)
- `geom`: geometry type (e.g., `nodes`, `edges`, `polygon`)

Rules in `rules/assets.smk` pre-process these to:
- Split by subregion
- Have a single geometry type per asset (e.g., LineString, Polygon, Point—no MultiLineStrings)
- Have WGS84 projection
- Have five columns: (unique) `id`, `asset_type`, `unit`, `unit_type`, `geometry`. The `asset_type` column should match naming for damage curves and rehab costs

Pre-processed assets are placed in `results/assets/` with format: `{asset}_{geom}/{subregion}.geoparquet`.

### Hazards

The workflow to pre-process hazard rasters is in `rules/hazards.smk` but needs to be tidied a bit.

Pre-processed hazards should be placed in `results/hazards/aligned/` with format:
```
{hazard}_{epoch}_{scenario}_rp{rp}.tif
```

where:
- `hazard`: hazard name (e.g., `pluvial`, `cyclone`). Should match the hazard used in damage curves and rehabilitation costs
- `epoch`: time horizon (e.g., `2020`, `2050`, `2080`)
- `scenario`: climate scenario (e.g., `historical`, `ssp245`, `ssp585`)
- `rp`: return period (e.g., `00010`, `00050`, `00100`)

Hazard rasters should have WGS84 projection and proper `NoData` values defined. Rules to pre-process hazard rasters are in `rules/hazards` and the rule to align all pre-processed hazards to a common grid is in `rules/hazards.smk`.

---

The workflow uses damage curves, design standards, and rehabilitation costs stored in `config/damage_curves`, `config/design_standards`, and `config/rehab_costs`:

| Data type            | Format | Location                                           |
|----------------------|--------|----------------------------------------------------|
| Damage curves        | CSV    | `config/damage_curves/{hazard}/{asset_type}.csv`   |
| Design standards     | CSV    | `config/design_standards/{hazard}.csv`             |
| Rehabilitation costs | CSV    | `config/rehab_costs/{hazard}.csv`                  |

Rehabilitation costs and design standards are indexed by `asset_type`.

Damage curves have an `intensity` column and three columns for damage fractions: `damage_fraction_max`, `damage_fraction_min`, `damage_fraction_mean`. Use `#` to note the units of intensity. Costs are specified in `costs_per_unit` with a separate `unit_type` column indicating `m` (LineStrings), `sqm` (Polygons), or `unit` (Points). Example processing scripts to get input costs and curves into the right format are in `analysis/scripts/`.
