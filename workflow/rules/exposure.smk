"""Generic rules to perform vector-raster intersection."""
from pathlib import Path


def get_all_subregion_inputs_for_asset(wildcards):
    asset = wildcards.asset
    assets_dir = Path(f"../results/input/assets/{asset}")
    subregions = [f.stem for f in assets_dir.glob("*.geoparquet")]
    return expand(
        "../results/exposure/{asset}/{subregion}.geoparquet",
        asset=asset,
        subregion=subregions,
    )


rule intersect_all_subregions_for_asset:
    """
    snakemake --cores 4 ../results/exposure/tza_road/.all
    """
    input:
        get_all_subregion_inputs_for_asset
    output:
        touch("../results/exposure/{asset}/.all")


rule intersect_subregion:
    """
    snakemake --cores 4 ../results/exposure/tza_road/dar_es_salaam.geoparquet
    snakemake --cores 4 ../results/exposure/tza_road/kilimanjaro.geoparquet
    """
    input:
        vector="../results/input/assets/{asset}/{subregion}.geoparquet",
        rasters=expand(
            "../results/input/hazards/{source}/{hazard_type}_{epoch}_{scenario}_rp{rp}.tif",
            source=["fathom"],
            hazard_type=["fluvial"],
            epoch=["2050"],
            scenario=["SSP2-4p5"],
            rp=["00020"],
        )
    output:
        vector="../results/exposure/{asset}/{subregion}.geoparquet",
    params:
        copy_raster_values=True
    script:
        "../scripts/exposure/intersect.py"


ruleorder: intersect_subregion > intersect_all_subregions_for_asset