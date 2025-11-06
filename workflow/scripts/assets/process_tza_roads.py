import os
import pandas as pd
import geopandas as gpd
import logging


__all__ = ["format_subregion_name", "undo_subregion_formatting"]


def format_subregion_name(subregion:str) -> str:
    subregion = subregion.lower()
    subregion = subregion.replace(" ", "_")
    subregion = subregion.replace("/", "-")
    return subregion


def undo_subregion_formatting(subregion_formatted:str) -> str:
    subregion = subregion_formatted.replace("_", " ")
    subregion = subregion.replace("-", "/")
    subregion = subregion.title()
    return subregion


def format_asset_type(asset_type:str) -> str:
    asset_type = "road_" + asset_type
    return asset_type


def main(input, output, params):

    edges = gpd.read_parquet(input.edges).to_crs(params.crs)
    admin = gpd.read_file(input.admin).to_crs(params.crs)
    logging.info(f"Working in {params.crs}.")

    subregions = admin["shapeName"].unique().tolist()
    logging.info(f"Available subregions: {len(subregions)}.")

    os.makedirs(output.edgedir, exist_ok=True)

    edges_with_subregion = gpd.sjoin(
        edges, admin[["shapeName", "geometry"]],
        how="inner", predicate="intersects"
    )

    edges_with_subregion["overlap"] = edges_with_subregion.apply(
    lambda row: row.geometry.intersection(admin[admin["shapeName"] == row["shapeName"]].geometry.iloc[0]).length, 
    axis=1
    )
    
    edges_with_subregion = edges_with_subregion.sort_values("overlap", ascending=False).drop_duplicates(
        subset=[col for col in edges.columns if col != 'geometry'], keep="first"
    ).drop(columns=["overlap"])

    for subregion in subregions:
        subregion = format_subregion_name(subregion)
        print(f"Processing subregion {subregion}.")

        edges_subregion = edges_with_subregion[edges_with_subregion["shapeName"] == subregion].copy()
        edges_subregion = edges_subregion.drop(columns=["index_right", "shapeName"])
        edges_subregion["asset_type"] = edges_subregion["asset_type"].apply(format_asset_type)

        if len(edges_subregion) == 0:
            logging.warning(f"No edges found in subregion {subregion}, skipping.")
            continue
            
        edges_subregion.to_parquet(
            os.path.join(output.edgedir, f"{subregion}.geoparquet"),
            index=False
        )
        logging.info(f"Wrote edges subregion to {output.edgedir}/{subregion}.geoparquet")
    
    logging.info("Done.")

if __name__ == "__main__":
    
    logging.basicConfig(
        format="%(asctime)s %(process)d %(filename)s %(message)s", level=logging.INFO
    )

    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)