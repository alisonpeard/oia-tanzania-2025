import os
import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
import rioxarray as rxr
from rasterio.features import shapes
import logging

__all__ = ["raster_to_geodataframe"]


def raster_to_geodataframe(raster:xr.DataArray) -> gpd.GeoDataFrame:
    data = raster[0].data
    transform = raster.rio.transform()
    mask = ~np.isnan(data)
    results = (
        {"properties": {"value": v}, "geometry": s}
        for i, (s, v) in enumerate(
            shapes(data, mask=mask, transform=transform)
        )
    )
    gdf = gpd.GeoDataFrame.from_features(results, crs="EPSG:4326")
    gdf = gdf.fillna(0.)
    # gdf = gdf[gdf["value"] > 0]
    return gdf


def verify_asset_geometries(idx, gdf, ref):
    assert gdf.crs.equals(ref.crs), "CRS do not match"
    segment = gdf.loc[idx]
    segment_ref = ref.loc[idx]
    assert segment.geometry.equals(segment_ref.geometry), "Geometries do not match"
    logging.info("Geometries match.")


def verify_asset_exposure(idx, gdf, hazard, hazcol):
    segment = gdf.loc[[idx]]
    x0, y0, x1, y1 = segment.total_bounds
    hazard = hazard.rio.clip_box(minx=x0, miny=y0, maxx=x1, maxy=y1, allow_one_dimensional_raster=True)
    hazard = raster_to_geodataframe(hazard)
    intersection = gpd.overlay(segment, hazard, how="intersection")
    max_result_value = gdf.loc[idx, hazcol]
    max_raster_value = intersection["value"].max()
    assert np.isclose(max_raster_value, max_result_value), \
      f"Max hazard values do not match: {max_raster_value} (raster) != {max_result_value} (result)"
    logging.info(f"Hazard values match. {max_raster_value} (raster) == {max_result_value} (result)")


def main(input):
  gdf = gpd.read_parquet(input.vector)

  hazcols = [col for col in gdf.columns if col.startswith("hazard-")]

  for hazcol in hazcols:
    logging.info(f"Verifying hazard column: {hazcol}")
    idx = gdf[hazcol].idxmax()
    if pd.isna(idx):
        logging.info("No exposure for this hazard scenario, skipping.")
        continue

    ref = gpd.read_parquet(input.reference).set_index("id")
    verify_asset_geometries(idx, gdf, ref)

    hazfile = hazcol.replace("hazard-", "") + ".tif"
    hazpath = os.path.join(input.hazdir, hazfile)
    hazard = rxr.open_rasterio(hazpath, masked=True)
    verify_asset_exposure(idx, gdf, hazard, hazcol)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(process)d %(filename)s %(message)s", level=logging.INFO
    )

    input = snakemake.input
    main(input)