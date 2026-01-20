def format_input_scenario(scenario):
    if scenario == "historical":
        return "baseline"
    else:
        return scenario


rule copy_chaz_tiff:
    """
    snakemake --cores 4 ../results/hazards/input/cyclone_2050_ssp245_rp00025.tif
    """
    input:
        tiff=lambda wildcards: "{path}/hazards/chaz/CHAZ_FIXED_RETURN_PERIODS_{epoch}_{scenario}_mean_{rp}_YR_RP__TZA.tif".format(
            path=INPUTS,
            epoch=wildcards.EPOCH,
            scenario=format_input_scenario(wildcards.SCENARIO),
            rp=int(wildcards.RP)
        )
    output:
        tiff="../results/hazards/input/cyclone_{EPOCH}_{SCENARIO}_rp{RP}.tif"
    shell:
        """
        mkdir -p $(dirname {output.tiff})
        # copy input to output location
        cp {input.tiff} {output.tiff}
        """


rule all_chaz_scenarios:
    """
    snakemake --cores 4 all_chaz_scenarios
    """
    input:
        tiffs = expand(
            "../results/hazards/input/cyclone_{EPOCH}_{SCENARIO}_rp{RP}.tif",
            EPOCH=["2010", "2050", "2090"],
            SCENARIO=["ssp245", "ssp585"],
            RP = ["00010", "00025", "00050", "00250", "01000"]
        )


rule all_chaz_historical:
    """
    snakemake --cores 4 all_chaz_historical
    """
    input:
        tiffs = expand(
            "../results/hazards/input/cyclone_{EPOCH}_{SCENARIO}_rp{RP}.tif",
            SUBCATEGORY=["chaz"],
            EPOCH=["2010"],
            SCENARIO=["historical"],
            RP = ["00010", "00025", "00050", "00250", "01000"]
        )   