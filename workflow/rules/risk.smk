from pathlib import Path
from warnings import warn


def get_subregions():
    subregions_file = Path("../results/assets/subregions.txt")
    exclude = ["zanzibar", "pemba"]
    if not subregions_file.exists():
        return []
    with open(subregions_file) as f:
        subregions = [line.strip() for line in f if line.strip()]
        for exl in exclude:
            subregions = [sr for sr in subregions if exl not in sr.lower()]
    return subregions


rule intersect_subregion_hazard:
    """
    snakemake --cores 4 ../results/risk/tza_railway_edges/cyclone/kilimanjaro/profile.geoparquet
    snakemake --cores 4 ../results/risk/tza_airports_polygons/pluvial/kilimanjaro/profile.geoparquet
    snakemake --cores 4 ../results/risk/tza_roads_bridges_and_culverts_nodes/pluvial/kilimanjaro/profile.geoparquet
    """
    input:
        asset_dir="../results/assets/{asset}_{geom}",
        hazard_dir="../results/hazards/aligned"
    output:
        vector="../results/risk/{asset}_{geom}/{hazard}/{subregion}/profile.geoparquet"
    params:
        hazard="{hazard}",
        subregion="{subregion}",
        copy_raster_values=True,
        crs=config["local_crs"],
        damage_curve_dir="../config/damage_curves",
        rehab_cost_dir="../config/rehab_costs",
        protection_dir="../config/design_standards",
        splits_path=[None, "../results/risk/{asset}_{geom}/{hazard}/{subregion}/splits.geoparquet"][1]
    log:
        file="../logs/risk/intersect_{geom}_{asset}_{subregion}_{hazard}.log"
    script:
        "../scripts/intersections.py"


rule check_asset_hazard_exposure:
    """
    Double-check intersection results against input raster.

    snakemake --cores 4 ../results/flags/tza_railway_edges/pluvial/kilimanjaro.checked
    snakemake --cores 4 ../results/flags/tza_roads_bridges_and_culverts_nodes/pluvial/kilimanjaro.checked
    snakemake --cores 4 ../results/flags/tza_airports_polygons/pluvial/kilimanjaro.checked
    snakemake --cores 4 ../results/flags/tza_railway_edges/pluvial/shinyanga.checked
    """
    input:
        vector="../results/risk/{asset}_{geom}/{hazard}/{subregion}/profile.geoparquet",
        ref_dir="../results/assets/{asset}_{geom}",
        hazdir="../results/hazards/aligned"
    params:
        subregion="{subregion}",
        hazard="{hazard}"
    output:
        touch("../results/flags/{asset}_{geom}/{hazard}/{subregion}.checked")
    script:
        "../scripts/intersections_check.py"


def all_subregion_flags(wildcards):
    checkpoints.determine_subregions.get()
    subregions = get_subregions()
    return expand(
        "../results/flags/{asset}_{geom}/{hazard}/{subregion}.checked",
        geom=wildcards.geom,
        asset=wildcards.asset,
        hazard=wildcards.hazard,
        subregion=subregions
    )

rule calculate_annual_metrics:
    """
    snakemake --cores 4 ../results/risk/tza_railway_edges/pluvial/kilimanjaro/annual.parquet
    snakemake --cores 4 ../results/risk/tza_roads_bridges_and_culverts_nodes/pluvial/kilimanjaro/annual.parquet
    snakemake --cores 4 ../results/risk/tza_airports_polygons/pluvial/kilimanjaro/annual.parquet
    """
    input:
        vector="../results/risk/{asset}_{geom}/{hazard}/{subregion}/profile.geoparquet"
    output:
        parquet="../results/risk/{asset}_{geom}/{hazard}/{subregion}/annual.parquet"
    log:
        file="../logs/risk/expectations_{geom}_{asset}_{subregion}_{hazard}.log"
    script:
        "../scripts/expectations.py"


def all_subregions(wildcards):
    checkpoints.determine_subregions.get()
    subregions = get_subregions()
    return expand(
        "../results/risk/{asset}_{geom}/{hazard}/{subregion}/annual.parquet",
        geom=wildcards.geom,
        asset=wildcards.asset,
        hazard=wildcards.hazard,
        subregion=subregions
    )

rule all_results_for_asset_and_hazard:
    """
    snakemake --cores 4 ../results/flags/tza_railway_edges/pluvial/.processed -n
    snakemake --cores 4 ../results/flags/tza_roads_bridges_and_culverts_nodes/pluvial/.processed -n
    snakemake --cores 4 ../results/flags/tza_airports_polygons/pluvial/.processed -n
    """
    input:
        all_subregions
    output:
        touch("../results/flags/{asset}_{geom}/{hazard}/.processed")


rule all_intersections:
    """
    snakemake --cores 1 all_intersections -n
    """
    input:
        expand(
            # "../results/flags/{asset_geom}/{hazard}/.processed",
            "../results/risk/{asset_geom}/{hazard}/{subregion}/profile.geoparquet",
            asset_geom=[
                # "tza_railway_edges",
                # "tza_airports_polygons",
                # "tza_roads_bridges_and_culverts_nodes",
                "tza_roads_edges",
                # "tza_iww_ports_polygons", "tza_maritime_ports_polygons"
            ],
            hazard=[
                # "pluvial",
                # "fluvial",
                # "coastal",
                # "landslide",
                # "cyclone",
                "hd35",
                # "tasmax",
                ],
            subregion=get_subregions()
        )

# these are temporary workarounds for the Tanzania 2025 project
rule calculate_annual_metrics_cleaned:
    """
    snakemake --cores 4 ../results/risk_final/tza_railway_edges/pluvial/kilimanjaro/annual.parquet
    snakemake --cores 4 ../results/risk_final/tza_roads_bridges_and_culverts_nodes/pluvial/kilimanjaro/annual.parquet
    snakemake --cores 4 ../results/risk_final/tza_airports_polygons/pluvial/kilimanjaro/annual.parquet
    """
    input:
        vector="../results/risk_final/{asset}_{geom}/{hazard}/{subregion}/profile.geoparquet"
    output:
        parquet="../results/risk_final/{asset}_{geom}/{hazard}/{subregion}/annual.parquet"
    log:
        file="../logs/risk_final/expectations_{geom}_{asset}_{hazard}_{subregion}.log"
    script:
        "../scripts/expectations.py"


rule calculate_all_cleaned_metrics:
    """
    snakemake --cores 1 calculate_all_cleaned_metrics -n
    """
    input:
        expand(
            "../results/risk_final/{asset_geom}/{hazard}/{subregion}/annual.parquet",
            asset_geom=[
                "tza_railway_edges",
                # "tza_roads_bridges_and_culverts_nodes",
                # "tza_roads_edges",
                # "tza_hubs_polygons"
            ],
            hazard=[
                # "pluvial",
                # "fluvial",
                # "coastal",
                # "landslide",
                # "cyclone",
                # "hd35",
                "tasmax"
                ],
            subregion=get_subregions()
        )