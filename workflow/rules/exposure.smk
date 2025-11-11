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


def get_all_aligned_hazards():
    hazards_dir = Path("../results/aligned/hazards")
    hazards = []
    for root, dirs, files in os.walk(hazards_dir):
        for file in files:
            if file.endswith(".tif"):
                hazards.append(os.path.join(root,file))
    if len(hazards) == 0:
        raise ValueError("No input hazard rasters found in ../results/aligned/hazards")
    return hazards


rule intersect_all_subregions_for_asset:
    """
    snakemake --cores 4 ../results/exposure/tza_road/.all
    snakemake --cores 4 ../results/exposure/tza_road/kilimanjaro.geoparquet
    """
    input:
        get_all_subregion_inputs_for_asset
    output:
        touch("../results/exposure/{asset}/.all")


rule intersect_subregion:
    """
    snakemake --cores 4 ../results/exposure/tza_road/dar_es_salaam.geoparquet
    snakemake --cores 4 ../results/exposure/tza_road/kilimanjaro.geoparquet
    snakemake --cores 4 ../results/exposure/tza_airports/kigoma__urban.geoparquet
    """
    input:
        vector="../results/input/assets/{asset}/{subregion}.geoparquet",
        rasters=get_all_aligned_hazards(),
    output:
        vector=temp("../results/exposure/{asset}/{subregion}.geoparquet"),
    params:
        copy_raster_values=True,
        crs=config["local_crs"]
    script:
        "../scripts/exposure/intersect.py"


ruleorder: intersect_subregion > intersect_all_subregions_for_asset