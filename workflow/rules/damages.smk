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
