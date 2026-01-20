"""
Zero all heat damage costs.
"""
import pandas as pd

heat_costs = pd.read_csv("config/rehab_costs/heat/heatonly.csv", comment="#")
heat_costs = heat_costs.set_index("asset_type")
heat_costs = 0 * heat_costs
heat_costs.head()
heat_costs.to_csv("config/rehab_costs/heat/heatonly.csv")