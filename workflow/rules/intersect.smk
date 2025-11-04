"""Generic rules to perform vector-raster intersection."""

rule intersect:
    """
    snakemake --cores 4 ../results/intersected/tza_road/tza_roads_network_edges.geoparquet
    """
    input:
        vector="../results/input/assets/{source}/{asset_name}.parquet",
        rasters=expand(
            "../results/input/hazards/{source}/{hazard_type}/{epoch}/{scenario}/rp{rp}.tif",
            source=["fathom"],
            hazard_type=["fluvial_undefended"],
            epoch=["2050"],
            scenario=["SSP2-4p5"],
            rp=["00020"],
        )
    output:
        "../results/intersected/{source}/{asset_name}.geoparquet",
    params:
        copy_raster_values=True
    script:
        "../scripts/intersections/intersect.py"