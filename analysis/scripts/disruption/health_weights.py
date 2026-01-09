"""
Set all health centres to have weight == 1.
"""

# %%
import os
import pandas as pd
import geopandas as gpd

roads_path = "/Users/alison/Downloads/flows/road_weights/tza_roads_weights.gpkg"
health_path = "/Users/alison/Downloads/flows/schools_hospitals/TZA_health.shp"
out_path = "/Users/alison/Downloads/flows/health_weights/tza_roads_weights.gpkg"
POPULATION = "pop_2030"


def format_health_id(id:str) -> str:
    """Format service id to match node ids."""
    id = int(id)
    return f"tza_health_{id}"


def get_nearest_values(x,input_gdf,column_name):
    polygon_index = input_gdf.distance(x.geometry).sort_values().index[0]
    return input_gdf.loc[polygon_index,column_name]


def assign_populations(row):
        """Remove effects of local populations.
        """
        if row["health"] == 0:
            row["population"] = row["population_demand"]
        elif row["health"] == 1:
            row["population"] = row["population_served"]
        return row

if __name__ == "__main__":

    # load roads weights
    roads = gpd.read_file(roads_path)
    roads["population"] =  roads[POPULATION]
    total_pop = roads["population"].sum()

    health = gpd.read_file(health_path)
    health = health.to_crs(roads.crs)
    health["id"] = range(1, len(health) + 1)
    health["id"] = health["id"].apply(format_health_id)
    health["population"] = 1
    health = health[["id", "geometry", "population"]]

    print("Finding nearest road nodes for healths")
    health = health.sjoin_nearest(
        roads[["id", "geometry"]], 
        how="left", 
        distance_col="dist"
    ).rename(columns={"id_right": "nearest_road"})

    nearest_roads = health[["id_left", "population", "nearest_road"]].groupby("nearest_road")
    nearest_roads = nearest_roads.agg({"population": sum, "id_left": list})
    nearest_roads = nearest_roads.rename(columns={"id_left": "health_ids"})
    nearest_roads = nearest_roads.reset_index().rename(columns={"nearest_road": "id"})
    nearest_roads["health"] = True

    roads_service = pd.merge(roads, nearest_roads, how="left", on="id", suffixes=("_demand", "_served"))
    roads_service[["health", "population_served"]] = roads_service[["health", "population_served"]].fillna(0)
    roads_service["health"] = roads_service["health"].astype(bool)

    roads_service["population"] = None
    roads_service = roads_service.apply(
        lambda row: assign_populations(row), axis=1
    )

    roads_service["health"] = roads_service["health"].astype(int)
    roads_service = roads_service[
         ["id", "health", "population_demand", "population_served", "population", "health_ids"]
    ]

    def format_list(input:list):
        if isinstance(input, list):
            return ','.join(input)
        else:
            return ''

    roads_service["health_ids"] = roads_service["health_ids"].apply(format_list)

    # add geometry back
    roads_service = roads_service.merge(
        roads[["id", "geometry"]],
        left_on=["id"],
        right_on=["id"],
        how="left"
    )
    roads_service = gpd.GeoDataFrame(roads_service, geometry="geometry", crs=roads.crs)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    roads_service.to_file(out_path, driver="GPKG")

    # %%