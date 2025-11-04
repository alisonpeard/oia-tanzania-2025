# %% handling for unknown asset_types
import os
import pandas as pd
import geopandas as gpd
from scipy.interpolate import interp1d
from pathlib import Path
import logging


def dummy_rehab_cost(*args, **kwargs):
    return pd.NA


def get_hazard_from_colname(hazcol):
    return hazcol.split("_")[0].split('-')[1]


def main(input, output, params):
    damage_fractions = gpd.read_parquet(input.vector)

    asset_types = list(damage_fractions["asset_type"].unique())
    damage_cols = [col for col in damage_fractions.columns if col.startswith("damage-")]

    asset_rehab_costs = []
    for asset_type in asset_types:
        asset_rehab_cost = damage_fractions[damage_fractions["asset_type"] == asset_type].copy()
        for damage_col in damage_cols:
            hazard = get_hazard_from_colname(damage_col)


            rehab_cost_dir = os.path.join(params.rehab_cost_dir, hazard)
            rehab_costs = os.listdir(rehab_cost_dir)

            if rehab_costs:
                for rehab_cost in rehab_costs:
                    rehab_cost_df = pd.read_csv(os.path.join(rehab_cost_dir, rehab_cost), comment='#')
                    rehab_cost_df = rehab_cost_df.set_index("asset_type", drop=True)
                    rehab_cost_source= Path(rehab_cost).stem
                    
                    if asset_type in rehab_cost_df.index:
                        # TODO: Hanfle units properly
                        cost: float = rehab_cost_df.loc[asset_type, "cost"]
                        print(f"Rehabilitation cost for {asset_type} from {hazard} hazard: {cost}")
                        cost_col = '_'.join([damage_col, rehab_cost_source]).replace("damage-", "cost-")
                        asset_rehab_cost[cost_col] = cost * asset_rehab_cost[damage_col]
                    else:
                        logging.warning(f"No rehab cost found for asset type '{asset_type}' in hazard '{hazard}' cost file '{rehab_cost}'.")
            else:
                logging.warning(f"No cost curves found for hazard '{hazard}'.")

        asset_rehab_costs.append(asset_rehab_cost)
    
    rehab_costs = pd.concat(asset_rehab_costs)

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