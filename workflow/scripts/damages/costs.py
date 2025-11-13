"""
NOTE: refactor this so not repeatedly doing IO with the same csvs.
"""
import os
import pandas as pd
import geopandas as gpd
from scipy.interpolate import interp1d
from pathlib import Path
import logging


def dummy_rehab_cost(*args, **kwargs):
    return pd.NA


def get_hazard_from_colname(hazcol):
    return hazcol.split("_")[0].split("-")[1]


def main(input, output, params):
    damage_fractions = gpd.read_parquet(input.vector)

    asset_types = list(damage_fractions["asset_type"].unique())
    damage_cols = [col for col in damage_fractions.columns if col.startswith("damage-")]

    asset_damagess = []
    for asset_type in asset_types:
        asset_damages = damage_fractions[damage_fractions["asset_type"] == asset_type].copy()
        
        for damage_col in damage_cols:
            hazard = get_hazard_from_colname(damage_col)

            rehab_cost_file = os.path.join(params.rehab_cost_dir, f"{hazard}.csv")
            rehab_cost_df = pd.read_csv(rehab_cost_file, comment='#')
            rehab_cost_df = rehab_cost_df.set_index("asset_type", drop=True)
                    
            if asset_type in rehab_cost_df.index:
                for prefix in ["min", "mean", "max"]:
                    cost: float = rehab_cost_df.loc[asset_type, f"{prefix}_cost_usd"]
                    unit_type: str = rehab_cost_df.loc[asset_type, "unit_type"]
                    logging.info(f"Using {prefix} rehabilitation cost per {unit_type} for {asset_type} from {hazard} hazard: {cost}")

                    damage_fraction = asset_damages[damage_col]
                    units = asset_damages["unit"]

                    assert asset_damages["unit_type"].iloc[0] == unit_type, \
                        f"Unit type mismatch for asset type '{asset_type}' in hazard '{hazard}': " \
                        f"{asset_damages['unit_type'].unique()} != {unit_type}"

                    cost_col = damage_col.replace("damage-", "cost-") + "_" + prefix
                    asset_damages[cost_col] = cost * damage_fraction * units
            else:
                raise ValueError(
                    f"No rehab cost found for asset type '{asset_type}' in hazard '{hazard}' cost file '{rehab_cost_file}'."
                )

        asset_damagess.append(asset_damages)
    
    rehab_costs = pd.concat(asset_damagess)

    assert len(rehab_costs) == len(damage_fractions), \
        "Length mismatch in rehab costs calculation: " \
        f"{len(rehab_costs)} != {len(damage_fractions)}"

    rehab_costs.to_parquet(output.vector)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(process)d %(filename)s %(message)s", level=logging.INFO
    )

    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)