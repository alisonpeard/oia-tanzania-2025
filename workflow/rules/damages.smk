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
    snakemake --cores 4 ../results/damage_fractions/tza_road/.all
    snakemake --cores 4 ../results/damage_fractions/tza_road/kilimanjaro.geoparquet
    """
    input:
        get_all_subregion_damage_fractions_for_asset
    output:
        touch("../results/damage_fractions/{asset}/.all")


rule calculate_all_damage_costs_for_asset:
    """
    snakemake --cores 4 ../results/exposure/tza_road/.all
    """
    input:
        get_all_subregion_damage_costs_for_asset
    output:
        touch("../results/damage_costs/{asset}/.all")


rule damage_fractions:
    """
    snakemake --cores 4 ../results/damage_fractions/tza_road/kilimanjaro.geoparquet
    """
    input:
        vector="../results/exposure/{asset}/{subregion}.geoparquet"
    output:
        vector="../results/damage_fractions/{asset}/{subregion}.geoparquet"
    params:
        damage_curve_dir="../config/damage_curves"
    script:
        "../scripts/risk/damage_fractions.py"


rule damage_costs:
    """
    snakemake --cores 4 ../results/damage_costs/tza_road/kilimanjaro.geoparquet
    """
    input:
        vector="../results/damage_fractions/{asset}/{subregion}.geoparquet"
    output:
        vector="../results/damage_costs/{asset}/{subregion}.geoparquet"
    params:
        rehab_cost_dir="../config/rehab_costs"
    script:
        "../scripts/risk/damage_costs.py"
