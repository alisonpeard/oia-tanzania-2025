from pathlib import Path


def get_all_subregion_damage_fractions_for_asset(wildcards):
    asset = wildcards.asset
    assets_dir = Path(f"../results/input/assets/{asset}")
    subregions = [f.stem for f in assets_dir.glob("*.geoparquet")]
    return expand(
        "../results/damage_fractions/{asset}/{subregion}.geoparquet",
        asset=asset,
        subregion=subregions,
    )


def get_all_subregion_damage_costs_for_asset(wildcards):
    asset = wildcards.asset
    assets_dir = Path(f"../results/input/assets/{asset}")
    subregions = [f.stem for f in assets_dir.glob("*.geoparquet")]
    return expand(
        "../results/damage_costs/{asset}/{subregion}.geoparquet",
        asset=asset,
        subregion=subregions,
    )


rule calculate_all_damage_fractions_for_asset:
    """
    snakemake --cores 4 ../results/damages/fractions/tza_road/.all
    """
    input:
        get_all_subregion_damage_fractions_for_asset
    output:
        touch("../results/damages/fractions/{asset}/.all")


rule calculate_all_damage_costs_for_asset:
    """
    snakemake --cores 4 ../results/exposure/tza_road/.all
    """
    input:
        get_all_subregion_damage_costs_for_asset
    output:
        touch("../results/damages/costs/{asset}/.all")


rule damage_fractions:
    """
    snakemake --cores 4 ../results/damages/fractions/tza_road/kilimanjaro.geoparquet
    snakemake --cores 4 ../results/damages/fractions/tza_road/dar_es_salaam.geoparquet
    """
    input:
        vector="../results/exposure/{asset}/{subregion}.geoparquet"
    output:
        vector=temp("../results/damages/fractions/{asset}/{subregion}.geoparquet")
    params:
        damage_curve_dir="../config/damage_curves"
    script:
        "../scripts/risk/damage_fractions.py"


rule damage_costs:
    """
    snakemake --cores 4 ../results/damages/costs/tza_road/dar_es_salaam.geoparquet
    snakemake --cores 4 ../results/damages/costs/tza_airports/dar_es_salaam.geoparquet
    """
    input:
        vector="../results/damages/fractions/{asset}/{subregion}.geoparquet"
    output:
        vector=temp("../results/damages/costs/{asset}/{subregion}.geoparquet")
    params:
        rehab_cost_dir="../config/rehab_costs"
    script:
        "../scripts/risk/damage_costs.py"


rule unsplit_costs:
    """
    snakemake --cores 4 ../results/damages/final/tza_road/kilimanjaro.geoparquet
    """
    input:
        vector="../results/damages/costs/{asset}/{subregion}.geoparquet",
        reference="../results/input/assets/{asset}/{subregion}.geoparquet"
    output:
        vector="../results/damages/final/{asset}/{subregion}.geoparquet"
    script:
        "../scripts/assets/unsplit.py"


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
        "../scripts/assets/verify_asset_exposure.py"