"""Rules to process TZA roads to standard vector format here."""

rule process_tza_roads:
    """
    snakemake --cores 4 ../results/input/assets/tza/roads/tza_roads_network_edges.geoparquet
    """
    input:
        edges=f"{INPUTS}/input/assets/tza_road/tza_roads_network_edges.parquet",
        admin=f"{INPUTS}/input/admin/geoboundaries/geoBoundaries-TZA-ADM1.gpkg"
    output:
        edgedir=directory("../results/input/assets/tza_road"),
    params:
        crs="EPSG:4326"
    script:
        "../../scripts/assets/process_tza_roads.py"