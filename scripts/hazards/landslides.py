"""
Copy the landslide files to the correct location and format.
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
        "subcategory": ["landslide"],
        "rp": ["00005", "00010", "00025", "00050", "00100"],
        "epoch": ["2015"],
        "scenario": ["historical"]
    }, "future": {
        "subcategory": ["landslide"],
        "rp": ["00005", "00010", "00025", "00050", "00100"],
        "epoch": ["2030", "2050", "2080"],
        "scenario": ["ssp126", "ssp245", "ssp585"]
    }
}

def format_input_file(indir, subcategory, rp, epoch, scenario):
    """Match files names and implement assumptions."""
    if scenario == "historical":
        scenario = "baseline"

    rp = int(rp)
    
    filename = f"hazard_polygons_{rp}yr_{epoch}_{scenario}_BAU_runout.tif"

    return indir / filename


def main(config, simulation_type="historical", redo=False):
    indir = Path(config['paths']['incoming_data']) / "hazards" / "landslides" / "maps"
    outdir = Path(config['paths']['snakemake_data']) / "hazards" / "raw"
    os.makedirs(outdir, exist_ok=True)

    scen_values = scenarios[simulation_type].values()
    for value in (pbar := tqdm(product(*scen_values))):
        subcategory, rp, epoch, scenario = value
        pbar.set_postfix(simulation_type=simulation_type, subcategory=subcategory, rp=rp, epoch=epoch, scenario=scenario)
        inpath = format_input_file(indir, subcategory, rp, epoch, scenario)
        outpath = outdir / f"{subcategory}_{epoch}_{scenario}_rp{rp}.tif"

        if not inpath.exists():
            print(f"  Warning: Source file not found: {inpath}")
            continue

        if outpath.exists() and not redo:
            print(f"  Skipping existing: {outpath}")
            continue

        print(f"\ncopying:\n  {inpath}\n   ->\n    {outpath}")
        shutil.copy2(inpath, outpath)


if __name__ == '__main__':
    CONFIG = config.load_config()
    main(CONFIG, SIMULATION_TYPE, REDO)
# %%
