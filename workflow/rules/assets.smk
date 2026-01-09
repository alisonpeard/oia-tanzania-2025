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


rule process_input_edges:
    """
    snakemake --cores 4 ../results/assets/tza_roads_edges
    snakemake --cores 4 ../results/assets/tza_railway_edges
    """
    input:
        edges=f"{INPUTS}/assets/{{asset}}_edges.parquet",
        admin=f"{INPUTS}/admin/tza_admin_{ADMIN_LEVEL}.gpkg",
        subregions="../results/assets/subregions.txt"
    output:
        edgedir=directory("../results/assets/{asset}_edges"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/process_input_edges.py"


rule process_input_nodes:
    """
    snakemake --cores 4 ../results/assets/tza_roads_bridges_and_culverts_nodes
    """
    input:
        points=f"{INPUTS}/assets/{{asset}}_nodes.parquet",
        admin=f"{INPUTS}/admin/tza_admin_{ADMIN_LEVEL}.gpkg",
        subregions="../results/assets/subregions.txt"
    output:
        pointdir=directory("../results/assets/{asset}_nodes"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/process_input_nodes.py"


rule process_input_polygons:
    """
    snakemake --cores 4 ../results/assets/tza_airports_polygons
    snakemake --cores 4 ../results/assets/tza_iww_ports_polygons
    snakemake --cores 4 ../results/assets/tza_maritime_ports_polygons
    """
    input:
        polys=f"{INPUTS}/assets/{{asset}}_polygons.parquet",
        admin=f"{INPUTS}/admin/tza_admin_{ADMIN_LEVEL}.gpkg",
        subregions="../results/assets/subregions.txt"
    output:
        polydir=directory("../results/assets/{asset}_polygons"),
    params:
        local_crs=config["local_crs"]
    script:
        "../scripts/process_input_polygons.py"


rule process_all_assets:
    input:
        expand("../results/assets/{asset_geom}",
            asset_geom=[
                "tza_roads_edges",
                # "tza_railway_edges",
                # "tza_roads_bridges_and_culverts_nodes",
                # "tza_airports_polygons",
                # "tza_iww_ports_polygons",
                # "tza_maritime_ports_polygons"
            ]
        )
