"""
Load the CORDEX data, clip to bbox, compute yearly statistics (hd35 or tasmax),
and save to new netCDF files.
"""
# %%
import os
import numpy as np
import pandas as pd 
import xarray as xr
from pathlib import Path
from typing import Dict, Optional
from tqdm import tqdm

from oi_risk import config
# from config import CORDEXDIR, DATADIR


LAT = "rlat"
LON = "rlon"
TIME = "time"
BBOX = [29, 41, -12, -1]
VARIABLE = ["hd35", "tasmax"][1]


def kelvin2celcius(da):
    return da - 273.15


def parse_cordex_filename(filename: str) -> Dict[str, Optional[str]]:
    parts = filename.split('_')
    if len(parts) != 9:
        print(f"Error: Expected 9 parts, found {len(parts)} in '{filename}'.")
        return {}
    metadata = dict(zip([
        'variable', 'spatial_domain', 'gcm_model', 
        'climate_scenario', 'ensemble', 'rcm_model', 
        'version', 'temporal_frequency', 'timerange'
    ], parts))
    timerange = metadata.pop('timerange')
    if '-' in timerange and len(timerange) == 17:
        start_date_str, end_date_str = timerange.split('-')
        start_year = int(start_date_str[:4])
        end_year = int(end_date_str[:4])

        metadata['start_year'] = start_year
        metadata['end_year'] = end_year
    return metadata


def clip_cordex_to_bbox(ds, bbox):
    lon_min, lon_max, lat_min, lat_max = bbox
    mask = np.logical_and.reduce([
        ds['lon'] >= lon_min,
        ds['lon'] <= lon_max,
        ds['lat'] >= lat_min,
        ds['lat'] <= lat_max
    ])
    rlat_indices, rlon_indices = np.where(mask)
    rlat_start = rlat_indices.min() 
    rlat_end = rlat_indices.max() + 1
    rlon_start = rlon_indices.min()
    rlon_end = rlon_indices.max() + 1

    ds_subset = ds.isel(
        rlat=slice(rlat_start, rlat_end),
        rlon=slice(rlon_start, rlon_end)
    )
    return ds_subset


if __name__ == "__main__":

    config = config.load_config()

    CORDEXDIR = config['paths']['cordex_data']
    DATADIR = config['paths']['incoming_data']

    files = os.path.join(CORDEXDIR)
    files = [f for f in os.listdir(files) if f.endswith(".nc")]
    files = [os.path.join(CORDEXDIR, f) for f in files]
    file = files[0]

    wd = Path(DATADIR) / "hazards" / VARIABLE / "yearly"
    os.makedirs(wd, exist_ok=True)

    problem_files = {}
    for file in tqdm(files):
        metadata = parse_cordex_filename(Path(file).stem)
        climate_scenario = metadata['climate_scenario']
        start_year = metadata['start_year']
        end_year = metadata['end_year']
        gcm_model = metadata['gcm_model']
        rcm_model = metadata['rcm_model']

        outdir = os.path.join(wd, climate_scenario, f"{gcm_model}_{rcm_model}")
        os.makedirs(outdir, exist_ok=True)

        filename = f"{start_year}_{end_year}.nc"
        outpath = os.path.join(outdir, filename)

        if os.path.exists(outpath):
            print(f"File already exists: {outpath}. Skipping...")
            continue

        try:
            ds = xr.open_dataset(file, engine="netcdf4")
            ds_subset = clip_cordex_to_bbox(ds, BBOX)
            tasmax_c = kelvin2celcius(ds_subset['tasmax'])
            tasmax_c = tasmax_c.resample(time='1D').max()

            data_vars = {}

            if VARIABLE == "hd35":
                exceedance = tasmax_c > 35.0
                data_vars[VARIABLE] = exceedance.groupby('time.year').sum('time')
            elif VARIABLE == "tasmax":
                data_vars[VARIABLE] = tasmax_c.groupby('time.year').max('time')
            else:
                raise ValueError(f"Unknown output variable: {VARIABLE}")

            annual_statistic = xr.Dataset(data_vars)
            annual_statistic.attrs = metadata
            ds.close()
            annual_statistic.to_netcdf(outpath)
            annual_statistic.close()
            print(f"Processed {file} -> {outpath}")

        except Exception as e:
            problem_files[file] = str(e)
            print(f"Error processing {file}: {e}")

    problem_df = pd.DataFrame.from_dict(problem_files, orient='index', columns=['error'])
    problem_df.to_csv(os.path.join("../logs", f"problem_files_{VARIABLE}.csv"))

print("Processing complete.")
# %%
