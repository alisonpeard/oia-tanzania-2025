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
        gpkg=expand("{path}/input/hazards/landslides/landslide_polygons_{rp}yr_{epoch}_{scenario}_BAU_runout.gpkg",
                    path=INPUTS,
                    rp=int(wildcards.rp),
                    epoch=wildcards.epoch,
                    scenario=format_scenario(wildcards.scenario)
        )
        raster_dir=dir("../results/hazards/aligned")
    output:
        raster="../results/hazards_aligned/landslide_{epoch}_{scenario}_rp{rp}.tif"
