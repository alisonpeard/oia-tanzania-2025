from pathlib import Path


rule intersect_subregion:
    """
    snakemake --cores 4 ../results/risk/unprotected/tza_roads/dar_es_salaam.geoparquet
    snakemake --cores 4 ../results/risk/unprotected/tza_roads_bridges_and_culverts/dar_es_salaam.geoparquet
    snakemake --cores 4 ../results/risk/unprotected/tza_roads/kilimanjaro.geoparquet
    snakemake --cores 4 ../results/risk/unprotected/tza_airports/dar_es_salaam.geoparquet
    """
    input:
        asset_dir="../results/assets/{asset}",
        hazard_dir=rules.align_hazard_rasters.output.outdir
    output:
        vector="../results/risk/unprotected/{asset}/{subregion}.geoparquet",
    params:
        subregion="{subregion}",
        copy_raster_values=True,
        crs=config["local_crs"],
        damage_curve_dir="../config/damage_curves",
        rehab_cost_dir="../config/rehab_costs"
    script:
        "../scripts/risk/intersect.py"


def get_all_output_files_for_asset(wildcards):
    geom = wildcards.geom
    asset = wildcards.asset
    assets_dir = Path(f"../results/assets/{asset}")
    subregions = [f.stem for f in assets_dir.glob("*.geoparquet")]
    return expand(
        "../results/risk/protected/{asset}/{subregion}.geoparquet",
        geom=geom,
        asset=asset,
        subregion=subregions,
    )


rule intersect_all_subregions_for_asset:
    """
    snakemake --cores 4 ../results/risk/unprotected/tza_roads/.all
    snakemake --cores 4 ../results/risk/unprotected/tza_airports/.all
    snakemake --cores 4 ../results/risk/unprotected/tza_roads/kilimanjaro.geoparquet
    """
    input:
        get_all_output_files_for_asset
    output:
        touch("../results/risk/unprotected/{asset}/.all")


ruleorder: intersect_subregion > intersect_all_subregions_for_asset


rule validate_asset_exposure:
    """
    snakemake --cores 4 ../results/risk/verified/tza_roads/kilimanjaro.done
    snakemake --cores 4 ../results/risk/verified/tza_airports/dar_es_salaam.done
    snakemake --cores 4 ../results/risk/verified/tza_rail/dar_es_salaam.done
    snakemake --cores 4 ../results/risk/verified/tza_roads_bridges_and_culverts/dar_es_salaam.done
    """
    input:
        vector="../results/risk/unprotected/{asset}/{subregion}.geoparquet",
        reference="../results/assets/{asset}/{subregion}.geoparquet",
        hazdir="../results/hazards/aligned"
    output:
        touch("../results/risk/verified/{asset}/{subregion}.done")
    script:
        "../scripts/risk/verify.py"


def check_all_assets_validated(wildcards):
    asset = wildcards.asset
    assets_dir = Path(f"../results/assets/{asset}")
    subregions = [f.stem for f in assets_dir.glob("*.geoparquet")]
    return expand(
        "../results/risk/verified/{asset}/{subregion}.done",
        asset=asset,
        subregion=subregions,
    )


rule validate_all_asset_exposure:
    """
    snakemake --cores 4 ../results/risk/verified//tza_airports/.all
    snakemake --cores 4 ../results/risk/verified/tza_rail/.all
    """
    input:
        check_all_assets_validated
    output:
        touch("../results/risk/verified/{asset}/.all")


rule add_protection_standards:
    """
    snakemake --cores 4 ../results/risk/protected/tza_roads/kilimanjaro.geoparquet
    snakemake --cores 4 ../results/risk/protected/tza_rail/kilimanjaro.geoparquet
    snakemake --cores 4 ../results/risk/protected/tza_airports/kilimanjaro.geoparquet
    """
    input:
        vector="../results/risk/unprotected/{asset}/{subregion}.geoparquet"
    output:
        vector="../results/risk/protected/{asset}/{subregion}.geoparquet"
    params:
        protection_dir="../config/design_standards"
    script:
        "../scripts/risk/protect.py"