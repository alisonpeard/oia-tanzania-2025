rule process_tza_roads:
    """
    snakemake --cores 4 ../results/assets/tza_roads
    """
    input:
        edges=f"{INPUTS}/assets/geoparquets/tza_roads_edges.parquet",
        admin=f"{INPUTS}/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        edgedir=directory("../results/assets/tza_roads"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/assets/process_edges.py"


rule process_tza_railway:
    """
    snakemake --cores 4 ../results/assets/input/tza_railway
    """
    input:
        edges=f"{INPUTS}/assets/geoparquets/tza_railway_edges.parquet",
        admin=f"{INPUTS}/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        edgedir=directory("../results/assets/tza_railway"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/assets/process_edges.py"


rule process_tza_airports:
    """
    snakemake --cores 4 ../results/assets/tza_airports
    """
    input:
        polys=f"{INPUTS}/assets/geoparquets/tza_airports_polygons.parquet",
        admin=f"{INPUTS}/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        polydir=directory("../results/assets/tza_airports"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/assets/process_polygons.py"


rule process_tza_iww_ports:
    """
    snakemake --cores 4 ../results/assets/tza_iww_ports
    """
    input:
        points=f"{INPUTS}/assets/geoparquets/tza_iww_ports_polygons.parquet",
        admin=f"{INPUTS}/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        pointdir=directory("../results/assets/tza_iww_ports"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/assets/process_polygons.py"


rule process_tza_maritime_ports:
    """
    snakemake --cores 4 ../results/assets/tza_maritime_ports
    """
    input:
        polys=f"{INPUTS}/assets/geoparquets/tza_maritime_ports_polygons.parquet",
        admin=f"{INPUTS}/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        polydir=directory("../results/assets/tza_maritime_ports"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/assets/process_polygons.py"


rule process_roads_bridges_and_culverts:
    """
    snakemake --cores 4 ../results/assets/tza_roads_bridges_and_culverts
    """
    input:
        points=f"{INPUTS}/assets/geoparquets/tza_roads_bridges_and_culverts_nodes.parquet",
        admin=f"{INPUTS}/admin/geoboundaries/geoBoundaries-TZA-ADM{ADMIN_LEVEL}.gpkg"
    output:
        pointdir=directory("../results/assets/tza_roads_bridges_and_culverts"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/assets/process_nodes.py"