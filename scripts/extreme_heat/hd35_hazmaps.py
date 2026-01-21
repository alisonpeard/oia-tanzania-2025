"""
Make nonstationary hd35 return level maps for each model and scenario.

Detrending: binomial GLM
GEV fitting: discrete GPD (https://arxiv.org/abs/1707.05033)
"""
# %%
import os
import logging
from glob import glob
from tqdm import tqdm
from pathlib import Path

import numpy as np
import xarray as xr
from scipy.optimize import minimize

from ttra.statistics import binom, dgpd
from oi_risk import config


dry_run = False
ignore = [".DS_Store"]

q_threshold = 80
rps = [5, 10, 20, 50, 100, 200, 500, 1000]

i = 1
epochs = [[2000, 2005, 2010], [2080, 2050, 2030]][i]
scenarios = [["historical"], ["rcp85", "rcp45", "rcp26"]][i]
MODELS = ['MOHC-HadGEM2-ES_KNMI-RACMO22T', 'MPI-M-MPI-ESM-LR_MPI-CSC-REMO2009']

logfile = "../logs/hazard_hd35.log"


i = 1
if __name__ == "__main__":
    config = config.load_config()
    DATADIR = config['paths']['incoming_data']

    input_dir = Path(DATADIR) / "hazards" / "hd35" / "yearly"
    output_dir = Path(DATADIR) / "hazards" / "hd35" / "ensemble" / "q" + str(q_threshold)

    print("Making hazard maps for epochs:", epochs, "scenarios:", scenarios)
    logging.basicConfig(filename=logfile, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    
    os.makedirs(output_dir, exist_ok=True)
    
    for scenario in scenarios:
        scenario_dir = os.path.join(input_dir, scenario)
        models = [d for d in os.listdir(scenario_dir) if d not in ignore]
        models = [m for m in models if m in MODELS]

        if len(models) == 0:
            logging.warning(f"No models found for scenario {scenario}")
            continue

        for model in models:
            model_dir = os.path.join(scenario_dir, model)
            files = glob(f"{model_dir}/*.nc")

            if len(files) == 0:
                logging.warning(f"No files found for model {model}, scenario {scenario}")
                continue

            ds = xr.open_mfdataset(files, engine="netcdf4")
            ds = ds.load()

            logging.info(f"Processing model: {model}, scenario: {scenario}")

            ds_epoch = ds.copy()
            x = ds_epoch[f"hd35"].values
            n, h, w = x.shape

            years = ds_epoch["year"].values
            years_centered = years - years.mean()

            # initialize arrays with NaNs
            tail_indices = np.full((h, w), np.nan)
            locs = np.full((h, w), np.nan)
            scales = np.full((h, w), np.nan)
            beta0_trends = np.full((h, w), np.nan)
            beta1_trends = np.full((h, w), np.nan)
            return_levels = np.full((len(rps), len(epochs), h, w), np.nan)

            # Define outfile HERE, outside the loops
            outfile = os.path.join(output_dir, scenario, model, "return_levels.nc")
            os.makedirs(os.path.dirname(outfile), exist_ok=True)

            for lat in tqdm(range(h)):
                for lon in range(w):

                    data = x[:, lat, lon]
                    if (data == -9999).all() or np.isnan(data).all():
                        continue

                    if data.max() == 0:
                        logging.debug(f"All data zero at lat {lat}, lon {lon}, skipping.")
                        continue

                    # Create mask before filtering data
                    valid_mask = (data != -9999) & ~np.isnan(data)
                    years_valid = years_centered[valid_mask]
                    data_valid = data[valid_mask]

                    # estimate initial parameters for trend model
                    p_init = np.clip(data_valid.mean() / 365, 0.01, 0.99)  # avoid extremes
                    beta0_init = np.log(p_init / (1 - p_init))  # logit of mean probability

                    # fit the trend model
                    fit_trend = minimize(
                        binom.nll,
                        [beta0_init, 0],
                        args=(data_valid, years_valid),
                        method='L-BFGS-B',
                        bounds=[(-10, 10), (-0.1, 0.1)]
                    )

                    if not fit_trend.success:
                        logging.warning(f"Trend fitting failed at lat {lat}, lon {lon}: {fit_trend.message}")
                        continue

                    beta0_trend, beta1_trend = fit_trend.x
                    logging.debug(f"Intercept: {beta0_trend:.4f}, Slope: {beta1_trend:.4f}")
                    
                    mean_rates = binom.expected_value(years_valid, (beta0_trend, beta1_trend))
                    residuals = data_valid - mean_rates
                    
                    threshold = np.percentile(residuals, q_threshold)
                    logging.debug(f"\nChosen threshold at lat {lat}, lon {lon}: {threshold}")

                    exceedances = residuals[residuals > threshold] - threshold
                    exceed_years = years_valid[residuals > threshold]

                    if len(exceedances) < 10:
                        logging.warning(f"Not enough exceedances at lat {lat}, lon {lon}")
                        continue
                    logging.debug(f"Number of exceedances at lat {lat}, lon {lon}: {len(exceedances)}\n")
                    
     
                    scale_init, shape_init = dgpd.guess_params(exceedances)
                    init_params = [scale_init, shape_init]
                    
                    if scale_init <= 0:
                        logging.warning(f"Initial guess for scale is non-positive at lat {lat}, lon {lon}")
                        continue

                    result = minimize(
                        dgpd.nll,
                        init_params,
                        args=(exceedances,),
                        method='L-BFGS-B',
                        bounds=[(2e-5, None), (-0.5, 0.5)]
                    )
                    
                    if not result.success:
                        logging.warning(f"Optimization failed at lat {lat}, lon {lon}: {result.message}")
                        continue
                    
                    scale, shape = result.x                        
                    tail_indices[lat, lon] = shape
                    scales[lat, lon] = scale
                    locs[lat, lon] = threshold
                
                    # get return levels 
                    for i_epoch, epoch in enumerate(epochs):
                        epoch_centered = epoch - years.mean()
                        for rp_idx, T in enumerate(rps):
                            base_rate = binom.expected_value(epoch_centered, (beta0_trend, beta1_trend))
                            return_level = base_rate + threshold + dgpd.quantile(1/T, scale, shape)
                            return_levels[rp_idx, i_epoch, lat, lon] = min(return_level, 365)
                    
        
            # make xarray DataArray
            return_levels_da = xr.DataArray(
                return_levels,
                dims=["return_period", "epoch", "rlat", "rlon"],
                coords={
                    "return_period": rps,
                    "epoch": epochs,
                    "rlat": ds_epoch["rlat"],
                    "rlon": ds_epoch["rlon"],
                },
                name=f"hd35",
                attrs={
                    "units": "days",
                    "long_name": f"Return levels for annual number of days exceeding 35°C",
                    "distribution": "Discrete Generalized Pareto Distribution (D-GPD)",
                },
            )

            # save results
            return_levels_ds = return_levels_da.to_dataset(name=f"hd35")
            return_levels_ds["tail_index"] = (("rlat", "rlon"), tail_indices)
            return_levels_ds["scale"] = (("rlat", "rlon"), scales)
            return_levels_ds["threshold"] = (("rlat", "rlon"), locs)
            return_levels_ds.to_netcdf(outfile)
            print(f"\n{return_levels_ds=}\n")
            print(f"Saved d-GPD return levels to {outfile}\n")

    print(f"Finished processing d-GPD hazard maps for hd35 and threshold q{q_threshold}.")
# %%
