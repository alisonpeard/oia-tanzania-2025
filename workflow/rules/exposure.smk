from pathlib import Path


rule intersect_subregion:
    """
    snakemake --cores 4 ../results/exposure/tza_road/dar_es_salaam.geoparquet
    snakemake --cores 4 ../results/exposure/tza_road/kilimanjaro.geoparquet
    snakemake --cores 4 ../results/exposure/tza_airports/dar_es_salaam.geoparquet
    """
    input:
        vector="../results/input/assets/{asset}/{subregion}.geoparquet",
        hazard_dir=rules.align_hazard_rasters.output.outdir
    output:
        vector="../results/exposure/{asset}/{subregion}.geoparquet",
    params:
        copy_raster_values=True,
        crs=config["local_crs"],
        damage_curve_dir="../config/damage_curves",
        rehab_cost_dir="../config/rehab_costs"
    script:
        "../scripts/exposure/intersect.py"


rule subtract_design_standards:
    """
    snakemake --cores 4 ../results/net_exposure/tza_road/kilimanjaro.geoparquet
    """
    input:
        vector="../results/exposure/{asset}/{subregion}.geoparquet"
    output:
        vector="../results/net_exposure/{asset}/{subregion}.geoparquet"
    params:
        protection_dir="../config/design_standards"
    script:
        "../scripts/exposure/subtract_protection.py"


def get_all_output_files_for_asset(wildcards):
    asset = wildcards.asset
    assets_dir = Path(f"../results/input/assets/{asset}")
    subregions = [f.stem for f in assets_dir.glob("*.geoparquet")]
    return expand(
        "../results/net_exposure/{asset}/{subregion}.geoparquet",
        asset=asset,
        subregion=subregions,
    )


rule intersect_all_subregions_for_asset:
    """
    snakemake --cores 4 ../results/exposure/tza_road/.all
    snakemake --cores 4 ../results/exposure/tza_airports/.all
    snakemake --cores 4 ../results/exposure/tza_road/kilimanjaro.geoparquet
    """
    input:
        get_all_output_files_for_asset
    output:
        touch("../results/exposure/{asset}/.all")


ruleorder: intersect_subregion > intersect_all_subregions_for_asset
