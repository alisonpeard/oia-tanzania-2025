import os
from osgeo import gdal
import numpy as np
from pathlib import Path

def main(input, output, params):
    Path(output.outdir).mkdir(parents=True, exist_ok=True)
    
    min_pixel_size = float('inf')
    xmin, ymin = float('inf'), float('inf')
    xmax, ymax = float('-inf'), float('-inf')
    
    print("Analysing input rasters...")
    print(f"{input.rasters=}")
    # rasters = os.listdir(input.rasters)
    # rasters = [f for f in rasters if f.endswith('.tif')]
    for raster_path in input.rasters:
        ds = gdal.Open(raster_path)
        gt = ds.GetGeoTransform()
        
        # Get pixel size (take absolute value and minimum of x/y)
        pixel_x = abs(gt[1])
        pixel_y = abs(gt[5])
        pixel_size = min(pixel_x, pixel_y)
        
        if pixel_size < min_pixel_size:
            min_pixel_size = pixel_size
            reference_raster = raster_path
        
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
        
        ds = None
    
    print(f"Reference raster: {reference_raster}")
    print(f"Target resolution: {min_pixel_size} degrees")
    print(f"Target extent: {xmin}, {ymin}, {xmax}, {ymax}")
    
    # Align each raster
    for raster_path in input.rasters:
        basename = os.path.basename(raster_path)
        out_path = os.path.join(output.outdir, basename)
        
        print(f"Aligning: {basename}")
        
        # Use gdalwarp with specified parameters
        warp_options = gdal.WarpOptions(
            format='GTiff',
            dstSRS='EPSG:4326',
            xRes=min_pixel_size,
            yRes=min_pixel_size,
            outputBounds=(xmin, ymin, xmax, ymax),
            targetAlignedPixels=True,
            resampleAlg='bilinear',
            creationOptions=['COMPRESS=LZW', 'BIGTIFF=IF_SAFER', 'TILED=YES']
        )
        
        gdal.Warp(out_path, raster_path, options=warp_options)
    
    print("Alignment complete. All rasters now share the same grid in EPSG:4326.")

if __name__ == "__main__":
    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)