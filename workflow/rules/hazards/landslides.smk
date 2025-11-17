def format_scenario(scenario):
    if scenario.startswith("SSP"):
        parts = scenario.replace("SSP", "").split("_")
        ssp = parts[0]
        rcp = parts[1].replace("p", "")
        return f"ssp{ssp}{rcp}"
    else:
        raise ValueError(f"Unrecognized scenario format: {scenario}")


rule rasterise_landslide:
    """
    snakemake --cores 4 ../results/hazards/aligned/landslide_2050_SSP2-4p5_rp00005.tif
    """
    input:
        gpkg=lambda wildcards: expand("{path}/input/hazards/landslides/landslide_polygons_{rp}yr_{epoch}_{scenario}_BAU_runout.gpkg",
                    path=INPUTS,
                    rp=int(wildcards.rp),
                    epoch=wildcards.epoch,
                    scenario=format_scenario(wildcards.scenario)
        ),
        raster_dir=dir("../results/hazards/aligned")
    output:
        raster="../results/hazards_aligned/landslide_{epoch}_{scenario}_rp{rp}.tif"
    shell:
        """
        REF=$(ls . | head -n 1)
        REF=$(ls {input.rasters} | head -n 1)
        
        EXTENT=$(gdalinfo $REF | grep "Upper Left\|Lower Right" | awk '{{print $3, $4}}' | tr -d '(),' | xargs)
        RESOLUTION=$(gdalinfo $REF | grep "Pixel Size" | awk '{{print $4, $5}}' | tr -d '(),')

        gdal_rasterize -a hazard_score -l runout_zones \
            -te $EXTENT -tr $RESOLUTION \
            -a_srs EPSG:4326 \
            {input.gpkg} {output.raster}
        """
