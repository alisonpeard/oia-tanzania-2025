rule process_roads:
    """
    snakemake --cores 4 ../results/input/assets/tza_road
    """
    input:
        edges=f"{INPUTS}/input/assets/geoparquets/tza_roads_edges.parquet",
        admin=f"{INPUTS}/input/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        edgedir=directory("../results/input/assets/tza_road"),
    params:
        local_crs=config["local_crs"],
        asset_type="road"
    script:
        "../../scripts/assets/process_linestrings.py"


rule process_railways:
    """
    snakemake --cores 4 ../results/input/assets/tza_rail
    """
    input:
        edges=f"{INPUTS}/input/dev/tza_railway_edges.parquet",
        admin=f"{INPUTS}/input/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        edgedir=directory("../results/input/assets/tza_rail"),
    params:
        local_crs=config["local_crs"],
        asset_type="rail"
    script:
        "../../scripts/assets/process_linestrings.py"