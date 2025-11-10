rule process_airports:
    """
    snakemake --cores 4 ../results/input/assets/tza_airports
    """
    input:
        polys=f"{INPUTS}/input/assets/geoparquets/tza_airports_polygons.parquet",
        admin=f"{INPUTS}/input/admin/geoboundaries/geoBoundaries-TZA-ADM1.gpkg"
    output:
        polydir=directory("../results/input/assets/tza_airports"),
    params:
        local_crs=config["local_crs"],
        asset_type="airport"
    script:
        "../../scripts/assets/process_polygons.py"