# %%
import os
import geopandas as gpd
import logging
from tqdm import tqdm


__all__ = ["format_subregion_name", "undo_subregion_formatting"]

def check_geoms(polys):
    geom_types = polys.geometry.geom_type.unique().tolist()
    assert all([geom_type in ["Polygon"] for geom_type in geom_types]), \
        f"Found unexpected geometry types in edges: {geom_types}."

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
    ).area


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


def intersect_by_overlap(polys, admin):
    check_for_duplicates(polys, column="id")
    check_for_duplicates(admin, column="subregion")

    polys_with_admin = gpd.sjoin(
        polys, admin, how="inner", predicate="intersects"
    )
    admin_dict = dict(zip(admin['subregion'], admin.geometry))
    tqdm.pandas(desc="Calculating overlaps")
    polys_with_admin["overlap"] = polys_with_admin.progress_apply(
        calculate_overlap, axis=1, admin=admin_dict
    )
    polys_with_subregion = polys_with_admin.sort_values("overlap", ascending=False)
    polys_with_subregion = polys_with_subregion.drop_duplicates(
        subset=[col for col in polys.columns if col != 'geometry'], keep="first"
    ).drop(columns=["overlap"])
    return polys_with_subregion


def main(input, output, params):
    polys = gpd.read_parquet(input.polys).to_crs(params.local_crs)
    admin = gpd.read_file(input.admin).to_crs(params.local_crs)
    logging.info(f"Using local projection EPSG:{params.local_crs}.")

    check_geoms(polys)

    admin = prepare_admin_data(admin)
    polys = intersect_by_overlap(polys, admin)

    subregions = admin["subregion"].unique().tolist()
    logging.info(f"Found {len(subregions)} subregions.")

    os.makedirs(output.polydir, exist_ok=True)
    logging.info(f"Saving subregions to: {output.polydir}.")

    skipped = []
    for subregion in (pbar := tqdm(subregions)):
        pbar.set_postfix({'subregion': subregion})

        polys_subregion = polys[polys["subregion"] == subregion].copy()
        polys_subregion = polys_subregion.drop(columns=["index_right", "subregion"])
        assert "asset_type" in polys_subregion.columns, \
            "All assets must have an asset_type column."

        if len(polys_subregion) == 0:
            skipped.append(subregion)
            continue

        polys_subregion = polys_subregion.to_crs("EPSG:4326")
        polys_subregion.to_parquet(
            os.path.join(output.polydir, f"{subregion}.geoparquet"),
            index=False
        )
    
    if len(skipped) > 0:
        logging.warning(f"No polygons found for subregions: {*skipped,}")
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
