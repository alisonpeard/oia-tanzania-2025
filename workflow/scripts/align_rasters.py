import os
import tqdm
import logging
from osgeo import gdal
from pathlib import Path


def rasters_are_aligned(raster_path, target_extent, target_res, tolerance=1e-6) -> bool:
    """Check if raster already matches target grid."""
    ds = gdal.Open(raster_path)
    gt = ds.GetGeoTransform()
    
    xmin_target, ymin_target, xmax_target, ymax_target = target_extent
    
    # Check resolution
    pixel_x = abs(gt[1])
    pixel_y = abs(gt[5])
    res_match = (abs(pixel_x - target_res) < tolerance and 
                 abs(pixel_y - target_res) < tolerance)
    
    # Check extent
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    ulx, uly = gt[0], gt[3]
    lrx = ulx + cols * gt[1]
    lry = uly + rows * gt[5]
    
    extent_match = (abs(ulx - xmin_target) < tolerance and
                   abs(lrx - xmax_target) < tolerance and
                   abs(uly - ymax_target) < tolerance and
                   abs(lry - ymin_target) < tolerance)
    
    # Check projection
    proj_match = 'EPSG:4326' in ds.GetProjection() or '+proj=longlat' in ds.GetProjection()
    
    ds = None
    
    return res_match and extent_match and proj_match


def main(input, output, params):
    print(f"Making output directory: {output.outdir}")
    Path(output.outdir).mkdir(parents=True, exist_ok=True)
    
    min_pixel_size = float('inf')
    xmin, ymin = float('inf'), float('inf')
    xmax, ymax = float('-inf'), float('-inf')

    reference_raster = input.reference_raster
    ds = gdal.Open(reference_raster)
    gt = ds.GetGeoTransform()
    
    # Get pixel size (take absolute value and minimum of x/y)
    pixel_x = abs(gt[1])
    pixel_y = abs(gt[5])
    pixel_size = min(pixel_x, pixel_y)
    
    min_pixel_size = pixel_size
    
    # Get extent
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    
    ulx, uly = gt[0], gt[3]
    lrx = ulx + cols * gt[1]
    lry = uly + rows * gt[5]
    
    xmin = min(xmin, ulx, lrx)
    xmax = max(xmax, ulx, lrx)
    ymin = min(ymin, uly, lry)
    ymax = max(ymax, uly, lry)
    
    logging.info(f"Reference raster: {reference_raster}")
    logging.info(f"Target resolution: {min_pixel_size} degrees")
    logging.info(f"Target extent: {xmin}, {ymin}, {xmax}, {ymax}")
    
    # Align each raster
    for raster_path in (pbar := tqdm.tqdm(input.rasters)):
        pbar.set_postfix({'Aligning raster': os.path.basename(raster_path)})
        basename = os.path.basename(raster_path)
        out_path = os.path.join(output.outdir, basename)
        if rasters_are_aligned(raster_path, (xmin, ymin, xmax, ymax), min_pixel_size):
            logging.info(f"Already aligned, recompressing: {basename}")
            translate_options = gdal.TranslateOptions(
                format='GTiff',
                creationOptions=[
                    'COMPRESS=ZSTD',
                    'ZSTD_LEVEL=9',
                    'PREDICTOR=3',
                    'TILED=YES',
                    'BLOCKXSIZE=512',
                    'BLOCKYSIZE=512',
                    'BIGTIFF=IF_SAFER',
                    'NUM_THREADS=ALL_CPUS'
                ]
            )
            gdal.Translate(out_path, raster_path, options=translate_options)
        else:
            logging.info(f"Aligning: {basename}")
            warp_options = gdal.WarpOptions(
                format='GTiff',
                dstSRS='EPSG:4326',
                xRes=min_pixel_size,
                yRes=min_pixel_size,
                outputBounds=(xmin, ymin, xmax, ymax),
                targetAlignedPixels=True,
                resampleAlg='bilinear',
                outputType=gdal.GDT_Float32,
                creationOptions=[
                    'COMPRESS=ZSTD',
                    'ZSTD_LEVEL=9',
                    'PREDICTOR=3',
                    'TILED=YES',
                    'BLOCKXSIZE=512',
                    'BLOCKYSIZE=512',
                    'BIGTIFF=IF_SAFER',
                    'NUM_THREADS=ALL_CPUS'
                ]
            )
            
            gdal.Warp(out_path, raster_path, options=warp_options)
    
    logging.info("Alignment complete. All rasters now share the same grid in EPSG:4326.")


if __name__ == "__main__":
    logging.basicConfig(
        filename=snakemake.log.file,
        format="%(asctime)s %(process)d %(filename)s %(message)s",
        level=logging.INFO
    )
    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)