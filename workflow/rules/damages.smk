from pathlib import Path


def get_all_subregion_damage_fractions_for_asset(wildcards):
    asset = wildcards.asset
    assets_dir = Path(f"../results/input/assets/{asset}")
    subregions = [f.stem for f in assets_dir.glob("*.geoparquet")]
    return expand(
        "../results/damages/fractions/{asset}/{subregion}.geoparquet",
        asset=asset,
        subregion=subregions,
    )


def get_all_subregion_damage_costs_for_asset(wildcards):
    asset = wildcards.asset
    assets_dir = Path(f"../results/input/assets/{asset}")
    subregions = [f.stem for f in assets_dir.glob("*.geoparquet")]
    return expand(
        "../results/damages/costs/{asset}/{subregion}.geoparquet",
        asset=asset,
        subregion=subregions,
    )


def get_all_subregion_results_for_asset(wildcards):
    asset = wildcards.asset
    assets_dir = Path(f"../results/input/assets/{asset}")
    subregions = [f.stem for f in assets_dir.glob("*.geoparquet")]
    return expand(
        "../results/damages/final/{asset}/{subregion}.geoparquet",
        asset=asset,
        subregion=subregions,
    )


rule calculate_all_damage_fractions_for_asset:
    """
    snakemake --notemp --cores 4 ../results/damages/fractions/tza_road/.all
    snakemake --notemp --cores 4 ../results/damages/fractions/tza_airports/.all
    """
    input:
        get_all_subregion_damage_fractions_for_asset
    output:
        touch("../results/damages/fractions/{asset}/.all")


rule calculate_all_damage_costs_for_asset:
    """
    snakemake --notemp --cores 4 ../results/damages/costs/tza_road/.all
    snakemake --notemp --cores 4 ../results/damages/costs/tza_airports/.all
    """
    input:
        get_all_subregion_damage_costs_for_asset
    output:
        touch("../results/damages/costs/{asset}/.all")


rule calculate_final_results_for_asset:
    """
    snakemake --cores 4 ../results/damages/final/tza_airports/.all
    """
    input:
        get_all_subregion_results_for_asset
    output:
        touch("../results/damages/final/{asset}/.all")


rule damage_fractions:
    """
    snakemake --cores 4 ../results/damages/fractions/tza_road/kilimanjaro.geoparquet
    snakemake --cores 4 ../results/damages/fractions/tza_road/dar_es_salaam.geoparquet
    snakemake --cores 4 ../results/damages/fractions/tza_airports/dar_es_salaam.geoparquet
    """
    input:
        vector="../results/exposure/{asset}/{subregion}.geoparquet"
    output:
        vector=temp("../results/damages/fractions/{asset}/{subregion}.geoparquet")
    params:
        damage_curve_dir="../config/damage_curves"
    script:
        "../scripts/risk/damage_fractions.py"


# rule damage_costs:
#     """
#     snakemake --cores 4 ../results/damages/costs/tza_road/dar_es_salaam.geoparquet
#     snakemake --cores 4 ../results/damages/costs/tza_airports/dar_es_salaam.geoparquet
#     """
#     input:
#         vector="../results/damages/fractions/{asset}/{subregion}.geoparquet"
#     output:
#         vector=temp("../results/damages/costs/{asset}/{subregion}.geoparquet")
#     params:
#         rehab_cost_dir="../config/rehab_costs"
#     script:
#         "../scripts/risk/damage_costs.py"


rule unsplit_costs:
    """
    snakemake --cores 4 ../results/damages/final/tza_road/kilimanjaro.geoparquet
    """
    input:
        vector="../results/damages/fractions/{asset}/{subregion}.geoparquet",
        reference="../results/input/assets/{asset}/{subregion}.geoparquet"
    output:
        vector="../results/damages/final/{asset}/{subregion}.geoparquet"
    script:
        "../scripts/assets/unsplit.py"



def get_all_asset_verifications(wildcards):
    asset = wildcards.asset
    assets_dir = Path(f"../results/input/assets/{asset}")
    subregions = [f.stem for f in assets_dir.glob("*.geoparquet")]
    return expand(
        "../results/damages/verified/{asset}/{subregion}.done",
        asset=asset,
        subregion=subregions,
    )


rule verify_all_asset_exposure:
    """
    snakemake --cores 4 ../results/damages/verified/tza_airports/.all
    """
    input:
        get_all_asset_verifications
    output:
        touch("../results/damages/verified/{asset}/.all")


rule verify_asset_exposure:
    """
    snakemake --cores 4 ../results/damages/verified/tza_road/kilimanjaro.done
    snakemake --cores 4 ../results/damages/verified/tza_airports/dar_es_salaam.done
    """
    input:
        vector="../results/damages/final/{asset}/{subregion}.geoparquet",
        reference="../results/input/assets/{asset}/{subregion}.geoparquet",
        hazdir="../results/aligned/hazards"
    output:
        touch("../results/damages/verified/{asset}/{subregion}.done")
    script:
        "../scripts/exposure/verify_asset_exposure.py"