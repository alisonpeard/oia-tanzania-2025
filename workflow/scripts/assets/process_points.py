# %%
import os
import geopandas as gpd
import logging
from tqdm import tqdm


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


def prepare_admin_data(admin):
    admin = admin[["shapeName", "geometry"]].copy()
    admin.rename(columns={"shapeName": "subregion"}, inplace=True)
    admin["subregion"] = admin["subregion"].apply(format_subregion_name)
    admin = admin.dissolve(by="subregion", as_index=False)
    return admin


def check_for_duplicates(gdf, column="id"):
    n = len(gdf)
    n_unique = gdf[column].nunique()
    assert n == n_unique, f"Found {n - n_unique} duplicate indices in GeoDataFrame."


def main(input, output, params):
    points = gpd.read_parquet(input.points).to_crs(params.local_crs)
    admin = gpd.read_file(input.admin).to_crs(params.local_crs)
    logging.info(f"Using local projection EPSG:{params.local_crs}.")

    admin = prepare_admin_data(admin)

    points = gpd.sjoin(
        points, admin, how="inner", predicate="intersects"
    )

    subregions = admin["subregion"].unique().tolist()
    logging.info(f"Found {len(subregions)} subregions.")

    os.makedirs(output.pointdir, exist_ok=True)
    logging.info(f"Saving subregions to: {output.pointdir}.")

    skipped = []
    for subregion in (pbar := tqdm(subregions)):
        pbar.set_postfix({'subregion': subregion})

        points_subregion = points[points["subregion"] == subregion].copy()
        points_subregion = points_subregion.drop(columns=["index_right", "subregion"])
        assert "asset_type" in points_subregion.columns, \
            "All assets must have an asset_type column."

        if len(points_subregion) == 0:
            skipped.append(subregion)
            continue

        points_subregion = points_subregion.to_crs("EPSG:4326")
        points_subregion.to_parquet(
            os.path.join(output.pointdir, f"{subregion}.geoparquet"),
            index=False
        )
    
    if len(skipped) > 0:
        logging.warning(f"No points found for subregions: {*skipped,}")
    logging.info("Done. Saved output with EPSG:4326 projection.")


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(process)d %(filename)s %(message)s",
        level=logging.INFO
    )

    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)
# %%
