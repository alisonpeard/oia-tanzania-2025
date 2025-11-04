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


def main(input, output, params):

    edges = gpd.read_parquet(input.edges).to_crs(params.crs)
    admin = gpd.read_file(input.admin).to_crs(params.crs)
    logging.info(f"Working in {params.crs}.")

    subregions = admin["shapeName"].unique().tolist()
    logging.info(f"Available subregions: {len(subregions)}.")

    os.makedirs(output.edgedir, exist_ok=True)

    for subregion in subregions:
        admin_subregion = admin[admin["shapeName"] == subregion]
        subregion = format_subregion_name(subregion)
        print(f"Processing subregion {subregion}.")

        edges_subregion = gpd.overlay(
            edges,
            admin_subregion, how="intersection"
        )

        edges_exploded = edges_subregion.explode(index_parts=False).reset_index(drop=True)
        edges_exploded = edges_exploded.to_crs(params.crs)
        edges_exploded = edges_exploded[~edges_exploded.geometry.is_empty].reset_index(drop=True)

        if len(edges_exploded) == 0:
            logging.warning(f"No edges found in subregion {subregion}, skipping.")
            continue
            
        edges_exploded.to_parquet(
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