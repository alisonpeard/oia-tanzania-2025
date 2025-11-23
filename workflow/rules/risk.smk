from pathlib import Path
from warnings import warn

def get_subregions():
    subregions_file = Path("../results/assets/subregions.txt")
    if not subregions_file.exists():
        return []
    with open(subregions_file) as f:
        return [line.strip() for line in f if line.strip()]


rule intersect_subregion:
    """
    snakemake --cores 4 ../results/risk/edges/tza_railway/kilimanjaro.geoparquet
    snakemake --cores 4 ../results/risk/nodes/tza_roads_bridges_and_culverts/kilimanjaro.geoparquet
    snakemake --cores 4 ../results/risk/polygons/tza_airports/kilimanjaro.geoparquet
    """
    input:
        asset_dir="../results/assets/{geom}/{asset}",
        hazard_dir=rules.align_hazard_rasters.output.outdir
    output:
        vector="../results/risk/{geom}/{asset}/{subregion}.geoparquet"
    params:
        subregion="{subregion}",
        copy_raster_values=True,
        crs=config["local_crs"],
        damage_curve_dir="../config/damage_curves",
        rehab_cost_dir="../config/rehab_costs",
        protection_dir="../config/design_standards"
    script:
        "../scripts/risk/intersect.py"


rule verify_asset_exposure:
    """
    snakemake --cores 4 ../results/flags/edges/tza_railway/kilimanjaro/.verified
    snakemake --cores 4 ../results/flags/polygons/tza_airports/kilimanjaro/.verified
    snakemake --cores 4 ../results/flags/nodes/tza_roads_bridges_and_culverts/kilimanjaro/.verified
    """
    input:
        vector="../results/risk/{geom}/{asset}/{subregion}.geoparquet",
        ref_dir="../results/assets/{geom}/{asset}",
        hazdir="../results/hazards/aligned"
    params:
        subregion="{subregion}",
    output:
        touch("../results/flags/{geom}/{asset}/{subregion}/.verified")
    script:
        "../scripts/risk/verify.py"


rule all_results_for_subregion:
    """
    snakemake --cores 4 ../results/flags/edges/tza_railway/kilimanjaro/.done
    snakemake --cores 4 ../results/flags/polygons/tza_airports/kilimanjaro/.done
    snakemake --cores 4 ../results/flags/nodes/tza_roads_bridges_and_culverts/kilimanjaro/.done
    """
    input:
        verified="../results/flags/{geom}/{asset}/{subregion}/.verified",
        protected="../results/risk/{geom}/{asset}/{subregion}.geoparquet"
    output:
        touch("../results/flags/{geom}/{asset}/{subregion}.done")


def all_subregion_flags(wildcards):
    checkpoints.determine_subregions.get()
    subregions = get_subregions()
    return expand(
        "../results/flags/{geom}/{asset}/{subregion}.done",
        geom=wildcards.geom,
        asset=wildcards.asset,
        subregion=subregions
    )


rule all_results_for_asset:
    """
    snakemake --cores 4 ../results/flags/edges/tza_railway/.done
    snakemake --cores 4 ../results/flags/polygons/tza_airports/.done
    snakemake --cores 4 ../results/flags/nodes/tza_roads_bridges_and_culverts/.done
    """
    input:
        all_subregion_flags
    output:
        touch("../results/flags/{geom}/{asset}/.done")