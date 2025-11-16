rule process_roads_bridges_and_culvertsr:
    """
    snakemake --cores 4 ../results/assets/tza_roads_bridges_and_culverts
    """
    input:
        points=f"{INPUTS}/input/assets/geoparquets/tza_roads_bridges_and_culverts.parquet",
        admin=f"{INPUTS}/input/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        pointdir=directory("../results/assets/tza_roads_bridges_and_culverts"),
    params:
        local_crs=config["local_crs"]
    script:
        "../../scripts/assets/process_points.py"