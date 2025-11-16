rule process_airports:
    """
    snakemake --cores 4 ../results/assets/tza_airports
    """
    input:
        polys=f"{INPUTS}/input/assets/geoparquets/tza_airports_polygons.parquet",
        admin=f"{INPUTS}/input/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        polydir=directory("../results/assets/tza_airports"),
    params:
        local_crs=config["local_crs"]
    script:
        "../../scripts/assets/process_polygons.py"