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


def calculate_overlap(row, admin:dict):
    return row.geometry.intersection(
        admin[row["subregion"]]
    ).length


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


def intersect_by_overlap(edges, admin):
    check_for_duplicates(edges, column="id")
    check_for_duplicates(admin, column="subregion")

    edges_with_admin = gpd.sjoin(
        edges, admin, how="inner", predicate="intersects"
    )
    admin_dict = dict(zip(admin['subregion'], admin.geometry))
    tqdm.pandas(desc="Calculating overlaps")
    edges_with_admin["overlap"] = edges_with_admin.progress_apply(
        calculate_overlap, axis=1, admin=admin_dict
    )
    edges_with_subregion = edges_with_admin.sort_values("overlap", ascending=False)
    edges_with_subregion = edges_with_subregion.drop_duplicates(
        subset=[col for col in edges.columns if col != 'geometry'], keep="first"
    ).drop(columns=["overlap"])
    return edges_with_subregion


def main(input, output, params):
    edges = gpd.read_parquet(input.edges).to_crs(params.local_crs)
    admin = gpd.read_file(input.admin).to_crs(params.local_crs)
    logging.info(f"Using local projection EPSG:{params.local_crs}.")

    admin = prepare_admin_data(admin)
    edges = intersect_by_overlap(edges, admin)

    subregions = admin["subregion"].unique().tolist()
    logging.info(f"Found {len(subregions)} subregions.")

    os.makedirs(output.edgedir, exist_ok=True)
    logging.info(f"Saving subregions to: {output.edgedir}.")

    skipped = []
    for subregion in (pbar := tqdm(subregions)):
        pbar.set_postfix({'subregion': subregion})

        edges_subregion = edges[edges["subregion"] == subregion].copy()
        edges_subregion = edges_subregion.drop(columns=["index_right", "subregion"])
        assert "asset_type" in edges_subregion.columns, \
            "All assets must have an asset_type column."

        if len(edges_subregion) == 0:
            skipped.append(subregion)
            continue

        edges_subregion = edges_subregion.to_crs("EPSG:4326")
        edges_subregion.to_parquet(
            os.path.join(output.edgedir, f"{subregion}.geoparquet"),
            index=False
        )
    
    if len(skipped) > 0:
        logging.warning(f"No edges found for subregions: {*skipped,}")
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
