"""
Prepare all the direct damage results for plotting.

This script includes hard-coded patches for missing hazard data.
"""
import os
import pandas as pd
import geopandas as gpd
from glob import glob

from . import paths


def extract_hazard_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract hazard, epoch, scenario, and return period from hazard column name."""
    if "-" in hazcol:
        prefix, parts = hazcol.split("-")
    else:
        prefix = ""
        parts = hazcol
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


def prepare_hazard_coastal(df) -> pd.DataFrame:
    # interpolate missing 50-year coastal hazard based on 10- and 100-year
    missing_stem = "-coastal_2050_ssp585_rp00050"
    lower_stem = "-coastal_2050_ssp585_rp00010"
    upper_stem = "-coastal_2050_ssp585_rp00100"

    def interp(xmin, ymin, xmax, ymax):
        """Linear interpolation"""
        return lambda x: ymin + (ymax - ymin) * (x - xmin) / (xmax - xmin)
    
    xmin, xmax = 10, 100
    for metric in ["damage", "cost"]: #TODO: check if hazard and defended
        stats = ["min", "mean", "max"]
        for stat in stats:
            lower_col = metric + lower_stem + "_" + stat
            upper_col = metric + upper_stem + "_" + stat
            missing_col = metric + missing_stem + "_" + stat
            df[missing_col] = df.apply(
                lambda row: interp(
                    xmin, row[lower_col],
                    xmax, row[upper_col]
                )(50),
                axis=1
            )
            print(f"WARNING: Replaced {missing_col} with interpolated values from {lower_col} and {upper_col}")
    return df.copy() # de-fragment

    
def prepare_hazard_pluvial(df) -> pd.DataFrame:
    # interpolate missing 200-year pluvial hazard based on 100- and 500-year
    missing_stem = "-pluvial_2080_ssp245_rp00200"
    lower_stem = "-pluvial_2080_ssp245_rp00100"
    upper_stem = "-pluvial_2080_ssp245_rp00500"

    def interp(xmin, ymin, xmax, ymax):
        """Linear interpolation"""
        return lambda x: ymin + (ymax - ymin) * (x - xmin) / (xmax - xmin)
    
    xmin, xmax = 100, 500
    for metric in ["damage", "cost"]: #TODO: check if hazard and defended
        stats = ["min", "mean", "max"]
        for stat in stats:
            lower_col = metric + lower_stem + "_" + stat
            upper_col = metric + upper_stem + "_" + stat
            missing_col = metric + missing_stem + "_" + stat
            df[missing_col] = df.apply(
                lambda row: interp(
                    xmin, row[lower_col],
                    xmax, row[upper_col]
                )(200),
                axis=1
            )
            print(f"WARNING: Replaced {missing_col} with interpolated values from {lower_col} and {upper_col}")
    return df.copy() # de-fragment


def prepare_hazard_cyclone(df) -> pd.DataFrame:
    """Let SSP126 be based on historical baseline for cyclone hazard"""
    i = 0
    # represent ssp126 using historical baseline
    newkeys = []
    newvals = []
    for metric in ["hazard", "defended"]:
        for rp in ['10', '25', '50', '250', '1000']:
            ref = metric + '-cyclone_2010_historical_rp' + rp.zfill(5)
            ssp126_2010 = metric + '-cyclone_2010_ssp126_rp' + rp.zfill(5)
            ssp126_2050 = metric + '-cyclone_2050_ssp126_rp' + rp.zfill(5)
            ssp126_2090 = metric + '-cyclone_2090_ssp126_rp' + rp.zfill(5)
            newkeys.append(ssp126_2010)
            newvals.append(df[ref].copy())
            newkeys.append(ssp126_2050)
            newvals.append(df[ref].copy())
            newkeys.append(ssp126_2090)
            newvals.append(df[ref].copy())
            i += 3
    
    for metric in ["damage", "cost"]:
        stats = ["min", "mean", "max"]
        for rp in ['10', '25', '50', '250', '1000']:
            for stat in stats:
                ref = metric + '-cyclone_2010_historical_rp' + rp.zfill(5) + "_" + stat
                ssp126_2010 = metric + '-cyclone_2010_ssp126_rp' + rp.zfill(5) + "_" + stat
                ssp126_2050 = metric + '-cyclone_2050_ssp126_rp' + rp.zfill(5) + "_" + stat
                ssp126_2090 = metric + '-cyclone_2090_ssp126_rp' + rp.zfill(5) + "_" + stat
                newkeys.append(ssp126_2010)
                newvals.append(df[ref].copy())
                newkeys.append(ssp126_2050)
                newvals.append(df[ref].copy())
                newkeys.append(ssp126_2090)
                newvals.append(df[ref].copy())
                i += 3
    
    newcols = pd.DataFrame(dict(zip(newkeys, newvals)))
    df = pd.concat([df, newcols], axis=1)
    print(f"WARNING: Prepared cyclone data using baseline with {i} new columns for 2050 and 2080 SSP1-2.6")
    return df


def prepare_hazard_data(df, hazard) -> pd.DataFrame:
    """Prepare direct damage results for a given hazard"""
    df = df.copy()
    costcols = [col for col in df.columns if col.startswith("cost")]
    costcols_clean = ["_".join(col.split("_")[:-1]) for col in costcols]

    renamed_costs = df[costcols].copy()
    renamed_costs.columns = costcols_clean
    df = pd.concat([df.drop(columns=costcols), renamed_costs], axis=1)

    df = df.copy()
    if hazard == "cyclone":
        df = prepare_hazard_cyclone(df)
    if hazard == "pluvial":
        df = prepare_hazard_pluvial(df)
    if hazard == "coastal":
        df = prepare_hazard_coastal(df)
    return df