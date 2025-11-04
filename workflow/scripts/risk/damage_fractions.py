# %% handling for unknown asset_types
import os
import pandas as pd
import geopandas as gpd
from scipy.interpolate import interp1d
from pathlib import Path
import logging


def dummy_damage_curve(*args, **kwargs):
    return pd.NA


def get_hazard_from_colname(hazcol):
    return hazcol.split("_")[0].split('-')[1]


def make_damage_function(df:pd.DataFrame):
    hazard_intensity, damage_fraction = (
        df["intensity"],
        df["damage_fraction"],
    )
    bounds = tuple(f(damage_fraction) for f in (min, max))
    return interp1d(
        hazard_intensity,
        damage_fraction,
        kind="linear",
        fill_value=bounds,
        bounds_error=False,
    )


def main(input, output, params):
    exposure = gpd.read_parquet(input.vector)

    asset_types = list(exposure["asset_type"].unique())
    hazard_cols = [col for col in exposure.columns if col.startswith("hazard-")]

    asset_damages = []
    for asset_type in asset_types:
        asset_damage = exposure[exposure["asset_type"] == asset_type].copy()
        for hazard_col in hazard_cols:
            hazard = get_hazard_from_colname(hazard_col)
            damage_curve_dir = os.path.join(params.damage_curve_dir, hazard, asset_type)
            damage_curves = os.listdir(damage_curve_dir)

            if damage_curves:
                for damage_curve in damage_curves:
                    damage_df = pd.read_csv(os.path.join(damage_curve_dir, damage_curve), comment='#')
                    damage_curve_source = Path(damage_curve).stem
                    damage_function = make_damage_function(damage_df)
                    print(f"{asset_type} - {hazard}: {damage_curve_source}")
                    damage_col = hazard_col.replace("hazard-", "damage-") #TODO: handle multiple curves
                    asset_damage[damage_col] = asset_damage[hazard_col].apply(damage_function)
            else:
                logging.warning(f"No damage curves found for asset type '{asset_type}' and hazard '{hazard}'.")

        asset_damages.append(asset_damage)
    
    damage_fractions = pd.concat(asset_damages)
    assert len(damage_fractions) == len(exposure)

    damage_fractions.to_parquet(output.vector)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(process)d %(filename)s %(message)s", level=logging.INFO
    )

    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)