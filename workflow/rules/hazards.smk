from pathlib import Path
import os


def get_all_input_hazards(wildcards):
    """Input function that runs at execution time"""
    hazards_dir = Path("../results/hazards/input")
    hazards = []
    for root, dirs, files in os.walk(hazards_dir):
        for file in files:
            if file.endswith(".tif"):
                hazards.append(os.path.join(root, file))
    if len(hazards) == 0:
        raise ValueError("No input hazard rasters found in ../results/hazards/input")
    return hazards

    
rule align_hazard_rasters:
    """
    Align all hazard rasters to a common grid, corresponding to the
    highest resolution hazard data.

    snakemake --cores 4 align_hazard_rasters
    """
    input:
        rasters=get_all_input_hazards,
    output:
        outdir=directory("../results/hazards/aligned")
    log:
        file="../logs/hazards/align_rasters.log"
    script:
        "../scripts/align_rasters.py"
