rule process_roads:
    """
    snakemake --cores 4 ../results/assets/input/tza_road
    """
    input:
        edges=f"{INPUTS}/input/assets/geoparquets/tza_roads_edges.parquet",
        admin=f"{INPUTS}/input/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        edgedir=directory("../results/assets/tza_road"),
    params:
        local_crs=config["local_crs"]
    script:
        "../../scripts/assets/process_linestrings.py"


rule process_railways:
    """
    snakemake --cores 4 ../results/assets/tza_rail
    """
    input:
        edges=f"{INPUTS}/input/assets/geoparquets/tza_railway_edges.parquet",
        admin=f"{INPUTS}/input/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        edgedir=directory("../results/assets/tza_rail"),
    params:
        local_crs=config["local_crs"]
    script:
        "../../scripts/assets/process_linestrings.py"