"""
Develop unsplitting code here. Groupby ID and take maximum exposure
"""
import logging
import geopandas as gpd


def main(input, output, params):
    gdf = gpd.read_parquet(input.vector)

    hazard_columns = [col for col in gdf.columns if col.startswith("hazard-")]
    damage_columns = [col for col in gdf.columns if col.startswith("damage-")]
    cost_columns = [col for col in gdf.columns if col.startswith("cost-")]
    risk_columns = hazard_columns + damage_columns + cost_columns

    agg_func = {col: "max" for col in risk_columns} | \
                {col: "mean" for col in damage_columns} | \
                    {col: "sum" for col in cost_columns}

    gdf = gdf[["id"] + risk_columns].copy()
    gdf_grouped = gdf.groupby("id").agg(agg_func).sort_index()

    # check input vector data for duplicates
    gdf_ref = gpd.read_parquet(input.reference)
    gdf_ref = gdf_ref.set_index("id").sort_index()

    assert gdf_ref.index.is_unique
    assert gdf_grouped.index.equals(gdf_ref.index), "Indices do not match after dissolving"

    gdf_grouped = gdf_grouped.join(gdf_ref[["geometry"]])
    gdf_grouped = gpd.GeoDataFrame(gdf_grouped, geometry="geometry", crs="EPSG:4326")

    gdf_grouped.to_parquet(output.vector)
    logging.info(f"Saved unsplit data to {output.vector}.")


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(process)d %(filename)s %(message)s",
        level=logging.INFO
    )
    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)