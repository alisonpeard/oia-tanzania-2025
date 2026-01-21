"""
Mosaic the 1° Fathom hazard tiles and resample from 30 m to 90 m.

NOTE: Also converts cm to m for flood depth.
"""
# %%
import os
from itertools import product
from pathlib import Path
import subprocess
from tqdm import tqdm

from oi_risk import config

REDO = False
SIMULATION_TYPE = ["historical", "future"][0]

scenarios = {
    "historical": {
        "subcategory": ["pluvial", "fluvial", "coastal"],
        "rp": ["00005", "00010", "00020", "00050", "00100", "00200", "00500", "01000"],
        "epoch": ["2020"],
        "scenario": ["historical"]
    }, "future": {
        "subcategory": ["pluvial", "fluvial", "coastal"],
        "rp": ["00005", "00010", "00020", "00050", "00100", "00200", "00500", "01000"],
        "epoch": ["2030", "2050", "2080"],
        "scenario": ["ssp126", "ssp245", "ssp585"]
    }
}

def main(config, simulation_type="historical", redo=False):
    indir = Path(config['paths']['incoming_data']) / "hazards" / "fathom"
    outdir = Path(config['paths']['snakemake_data']) / "hazards" / "raw"
    os.makedirs(outdir, exist_ok=True)

    scen_values = scenarios[simulation_type].values()
    for value in (pbar := tqdm(product(*scen_values))):
        subcategory, rp, epoch, scenario = value
        pbar.set_postfix(simulation_type=simulation_type, subcategory=subcategory, rp=rp, epoch=epoch, scenario=scenario)
        inpath = indir / subcategory / epoch / scenario / f"1in{int(rp)}.zip"
        outpath = outdir / f"{subcategory}_{epoch}_{scenario}_rp{rp}.tif"

        if outpath.exists() and not redo:
            print(f"  Skipping existing: {outpath}")
            continue

        subprocess.run(["./fathom.sh", str(inpath), str(outpath)], check=True)


if __name__ == '__main__':
    CONFIG = config.load_config()
    main(CONFIG, SIMULATION_TYPE, REDO)
# %%
