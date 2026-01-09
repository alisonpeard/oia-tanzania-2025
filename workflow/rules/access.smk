from pathlib import Path
from warnings import warn


def get_subregions():
    subregions_file = Path("../results/assets/subregions.txt")
    if not subregions_file.exists():
        return []
    with open(subregions_file) as f:
        return [line.strip() for line in f if line.strip()]



rule calculate_annual_service_access:
    """
    snakemake --cores 4 ../results/school_access/tza_roads_edges/pluvial/kilimanjaro/annual.parquet
    """
    input:
        vector="../results/{service}_access/{asset}_{geom}/{hazard}/{subregion}/profile.parquet"
    output:
        parquet="../results/{service}_access/{asset}_{geom}/{hazard}/{subregion}/annual.parquet"
    log:
        file="../logs/{service}_access/expectations_{geom}_{asset}_{subregion}_{hazard}.log"
    script:
        "../scripts/access_expectations.py"


rule calculate_all_annual_service_access:
    """
    snakemake --cores 1 calculate_all_annual_service_access -n
    """
    input:
        expand(
            "../results/{service}_access/tza_roads_edges/{hazard}/{subregion}/annual.parquet",
            service=["health"], # ["school", "heatlh"]
            hazard=[
                "pluvial",
                "fluvial",
                "coastal",
                "landslide"
                ],
            subregion=get_subregions()
        )