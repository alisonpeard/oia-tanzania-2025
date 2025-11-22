checkpoint determine_subregions:
    """
    snakemake --cores 1 ../results/assets/subregions.txt
    """
    input:
        subregions=f"{INPUTS}/admin/tza_admin_{ADMIN_LEVEL}.gpkg"
    output:
        subregions="../results/assets/subregions.txt",
    run:
        import geopandas as geopandas

        def format_subregion_name(subregion:str) -> str:
            subregion = subregion.lower()
            subregion = subregion.replace(" ", "_")
            subregion = subregion.replace("/", "-")
            return subregion

        subregions = geopandas.read_file(input.subregions)
        subregions = subregions["shapeName"].apply(format_subregion_name).unique().tolist()
        with open(output.subregions, "w") as f:
            f.write('\n'.join(subregions))


rule process_edges:
    """
    snakemake --cores 4 ../results/assets/edges/tza_roads
    snakemake --cores 4 ../results/assets/edges/tza_railway
    """
    input:
        edges=f"{INPUTS}/assets/{{asset}}_edges.parquet",
        admin=f"{INPUTS}/admin/tza_admin_{ADMIN_LEVEL}.gpkg",
        subregions="../results/assets/subregions.txt"
    output:
        edgedir=directory("../results/assets/edges/{asset}"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/assets/process_edges.py"


rule process_nodes:
    """
    snakemake --cores 4 ../results/assets/nodes/tza_roads_bridges_and_culverts
    """
    input:
        points=f"{INPUTS}/assets/{{asset}}_nodes.parquet",
        admin=f"{INPUTS}/admin/tza_admin_{ADMIN_LEVEL}.gpkg",
        subregions="../results/assets/subregions.txt"
    output:
        pointdir=directory("../results/assets/nodes/{asset}"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/assets/process_nodes.py"


rule process_polygons:
    """
    snakemake --cores 4 ../results/assets/polygons/tza_airports
    snakemake --cores 4 ../results/assets/polygons/tza_iww_ports
    snakemake --cores 4 ../results/assets/polygons/tza_maritime_ports
    """
    input:
        polys=f"{INPUTS}/assets/{{asset}}_polygons.parquet",
        admin=f"{INPUTS}/admin/tza_admin_{ADMIN_LEVEL}.gpkg",
        subregions="../results/assets/subregions.txt"
    output:
        polydir=directory("../results/assets/polygons/{asset}"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/assets/process_polygons.py"