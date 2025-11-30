"""Utility functions for naming conventions."""
import pandas as pd
from pathlib import Path


def get_hazard_from_filename(raster_path):
    return Path(raster_path).stem.split('_')[0]


def get_hazard_from_colname(colname):
    return colname.split('_')[0].split('-')[-1]


def extract_hazard_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract hazard, epoch, scenario, and return period from hazard column name."""
    prefix, parts = hazcol.split("-")
    parts = parts.split("_")
    hazard = parts[0]
    epoch = parts[1]
    scenario = parts[2]
    rp = str(int(parts[3].replace("rp", "")))
    if len(parts) > 4:
        stat = "_".join(parts[4:])
    else:
        stat = pd.NA
    return prefix, hazard, epoch, scenario, rp, stat

