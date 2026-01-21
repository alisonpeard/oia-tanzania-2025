"""
Copy the CHAZ files to the correct location and format.

Other pre-processing:
- use 2090 to represent 2080 epoch
- use 2010 simulations to represent 2030 epoch
- use historical 2010 data to represent ssp126 for all epochs
"""
# %%
import os
from itertools import product
from pathlib import Path
import shutil
from tqdm import tqdm

from oi_risk import config

REDO = False
SIMULATION_TYPE = ["historical", "future"][1]

scenarios = {
    "historical": {
        "subcategory": ["cyclone"],
        "rp": ["00010", "00025", "00050", "00250", "01000"],
        "epoch": ["2010"],
        "scenario": ["historical"]
    }, "future": {
        "subcategory": ["cyclone"],
        "rp": ["00010", "00025", "00050", "00250", "01000"],
        "epoch": ["2030", "2050", "2080"],
        "scenario": ["ssp126", "ssp245", "ssp585"]
    }
}

def format_input_file(indir, subcategory, rp, epoch, scenario):
    """Match files names and implement assumptions."""
    if scenario == "historical":
        scenario = "baseline"
    if epoch == "2080":
        epoch = "2090"
    if epoch == "2030":
        epoch = "2010"
    if scenario == "ssp126":
        epoch = "2010"
        scenario = "baseline"

    rp = int(rp)

    return indir / f"CHAZ_FIXED_RETURN_PERIODS_{epoch}_{scenario}_mean_{rp}_YR_RP__TZA.tif"


def main(config, simulation_type="historical", redo=False):
    indir = Path(config['paths']['incoming_data']) / "hazards" / "chaz"
    outdir = Path(config['paths']['snakemake_data']) / "hazards" / "raw"
    os.makedirs(outdir, exist_ok=True)

    scen_values = scenarios[simulation_type].values()
    for value in (pbar := tqdm(product(*scen_values))):
        subcategory, rp, epoch, scenario = value
        pbar.set_postfix(simulation_type=simulation_type, subcategory=subcategory, rp=rp, epoch=epoch, scenario=scenario)
        inpath = format_input_file(indir, subcategory, rp, epoch, scenario)
        outpath = outdir / f"{subcategory}_{epoch}_{scenario}_rp{rp}.tif"
        print(f"{inpath} -> {outpath}")

        if outpath.exists() and not redo:
            print(f"  Skipping existing: {outpath}")
            continue

        print(f"\ncopying:\n  {inpath}\n   ->\n    {outpath}")
        shutil.copy2(inpath, outpath)


if __name__ == '__main__':
    CONFIG = config.load_config()
    main(CONFIG, SIMULATION_TYPE, REDO)
# %%
