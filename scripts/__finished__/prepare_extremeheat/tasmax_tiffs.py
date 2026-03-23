"""
Aggregate the hd35 return level maps and output in correct format for
snakemake workflow.
"""
# %%
import os
import xarray as xr
import rioxarray
import matplotlib.pyplot as plt
from pathlib import Path

from oi_risk import config


scenarios = ["historical", "rcp26", "rcp45", "rcp85"]
epochs = {
    "historical": [2010],
    "rcp26": [2030, 2050, 2080],
    "rcp45": [2030, 2050, 2080],
    "rcp85": [2030, 2050, 2080]
}
rps = [5, 10, 20, 50, 100, 200, 500, 1000]
MODELS = ['MOHC-HadGEM2-ES_KNMI-RACMO22T', 'MPI-M-MPI-ESM-LR_MPI-CSC-REMO2009']

if __name__ == "__main__":
    config = config.load_config()
    DATADIR = config['paths']['incoming_data']
    OUTDIR = config['paths']['processed_data']

    wd = Path(DATADIR) / "hazards" / "tasmax" / "ensemble" 
    outdir = Path(OUTDIR) / "hazards" / "tasmax" 

    os.makedirs(outdir, exist_ok=True)


    for scenario in scenarios:
        template_ds = None

        indir = wd / scenario
        models = MODELS

        hazard_maps = []
        for model in models:
            filepath = indir / model / "return_levels.nc"
            if not os.path.exists(filepath):
                print(f"Missing file: {filepath}")
                continue
            ds = xr.open_dataset(filepath, engine="netcdf4", decode_times=False)

            # align grids
            if template_ds is None:
                template_ds = ds.copy()
            else:
                ds = ds.interp(rlat=template_ds.rlat, rlon=template_ds.rlon, method='nearest')

            hazard_maps.append(ds["tasmax"])

        if hazard_maps:
            print(f"Combining {len(hazard_maps)} hazard maps for scenario {scenario}")
            combined = xr.concat(hazard_maps, dim="model")
            haz_mean = combined.mean(dim="model", skipna=True)
            haz_min = combined.min(dim="model", skipna=True)
            haz_max = combined.max(dim="model", skipna=True)

        for epoch in epochs[scenario]:
            for rp in rps:
                haz_mean = combined.sel(epoch=epoch, return_period=rp).mean(dim="model", skipna=True)
                haz_min = combined.sel(epoch=epoch, return_period=rp).min(dim="model", skipna=True)
                haz_max = combined.sel(epoch=epoch, return_period=rp).max(dim="model", skipna=True)

                haz_mean.rio.write_crs("EPSG:4326", inplace=True)
                haz_min.rio.write_crs("EPSG:4326", inplace=True)
                haz_max.rio.write_crs("EPSG:4326", inplace=True)

                outmean = f"tasmax_{epoch}_{scenario}_rp{str(rp).zfill(5)}.tif"
                outmin = f"tasmaxmin_{epoch}_{scenario}_rp{str(rp).zfill(5)}.tif"
                outmax = f"tasmaxmax_{epoch}_{scenario}_rp{str(rp).zfill(5)}.tif"

                outmeanpath = os.path.join(outdir, outmean)
                outminpath = os.path.join(outdir, outmin)
                outmaxpath = os.path.join(outdir, outmax)

                haz_mean.rio.to_raster(outmeanpath)
                # haz_min.rio.to_raster(outminpath)
                # haz_max.rio.to_raster(outmaxpath)

                print(f"Saved ensemble mean hazard map to {outmeanpath}")
                # print(f"Saved ensemble min hazard map to {outminpath}")
                # print(f"Saved ensemble max hazard map to {outmaxpath}")

    print("Finished exporting hazard maps to GeoTIFFs.")
# %%