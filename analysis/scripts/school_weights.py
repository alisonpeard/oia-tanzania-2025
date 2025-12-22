"""
32% of populated between 10--24 y/o.
3.2% population growth rate.

Todd, Gemma Joan Nifasha. The Trends in Adolescent and Youth Well-being in
the United Republic of Tanzania: Harnessing the Potential of Adolescents and
Youth in Tanzania (English). Washington, D.C.: World Bank Group.
http://documents.worldbank.org/curated/en/099092523030525310
"""

# %%
import os
import pandas as pd
import geopandas as gpd

roads_path = "/Users/alison/Downloads/flows/road_weights/tza_roads_weights.gpkg"
schools_path = "/Users/alison/Downloads/flows/schools_hospitals/schools_JRC_clean_duplicate_TZA.gpkg"
out_path = "/Users/alison/Downloads/flows/school_weights/tza_roads_weights.gpkg"
SCHOOL_GOING_FRACTION = 0.32
POPULATION = "pop_2030"


def format_school_id(id:str) -> str:
    """Format service id to match node ids."""
    id = int(id)
    return f"tza_school_{id}"


def get_nearest_values(x,input_gdf,column_name):
    polygon_index = input_gdf.distance(x.geometry).sort_values().index[0]
    return input_gdf.loc[polygon_index,column_name]


def net_population_served(row):
        """Remove effects of local populations.
        """
        if row["school"] == 0:
            row["population"] = row["population_demand"]
        elif row["school"] == 1:
            net_served = row["population_served"] - row["population_demand"]
            if net_served > 0:
                 row["population"] = net_served
            elif net_served <= 0:
                row["school"] = 0
                net_demand = row["population_demand"] - row["population_served"]
                row["population"] = net_demand
        return row
                 

if __name__ == "__main__":

    # load roads weights
    roads = gpd.read_file(roads_path)
    roads["population"] = SCHOOL_GOING_FRACTION * roads[POPULATION]
    total_pop = roads["population"].sum()


    schools = gpd.read_file(schools_path)
    schools = schools.to_crs(roads.crs)
    schools["id"] = schools["id"].apply(format_school_id)
    schools = schools.rename(columns={"student_per_school": "population"})
    schools = schools[schools["population"] > 0].copy()
    schools = schools[["id", "geometry", "population"]]

    total_school_pop = schools["population"].sum()
    zeta = total_school_pop / total_pop
    print(f"Total population in roads: {total_pop}")
    print(f"Total school-going population: {total_school_pop}")
    print(f"Fraction of school-going population: {zeta:.3f}")

    print("Finding nearest road nodes for schools")
    schools = schools.sjoin_nearest(
        roads[["id", "geometry"]], 
        how="left", 
        distance_col="dist"
    ).rename(columns={"id_right": "nearest_road"})

    nearest_roads = schools[["id_left", "population", "nearest_road"]].groupby("nearest_road")
    nearest_roads = nearest_roads.agg({"population": sum, "id_left": list})
    nearest_roads = nearest_roads.rename(columns={"id_left": "school_ids"})
    nearest_roads = nearest_roads.reset_index().rename(columns={"nearest_road": "id"})
    nearest_roads["school"] = True

    roads_service = pd.merge(roads, nearest_roads, how="left", on="id", suffixes=("_demand", "_served"))
    roads_service[["school", "population_served"]] = roads_service[["school", "population_served"]].fillna(0)
    roads_service["school"] = roads_service["school"].astype(bool)

    roads_service["population"] = None
    roads_service = roads_service.apply(
        lambda row: net_population_served(row), axis=1
    )

    roads_service["school"] = roads_service["school"].astype(int)
    roads_service = roads_service[
         ["id", "school", "population_demand", "population_served", "population", "school_ids"]
    ]
    roads_service[roads_service["school"] == 1]
    roads_service["zeta"] = zeta

    def format_list(input:list):
        if isinstance(input, list):
            return ','.join(input)
        else:
            return ''

    roads_service["school_ids"] = roads_service["school_ids"].apply(format_list)

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