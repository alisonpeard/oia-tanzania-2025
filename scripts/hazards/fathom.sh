#!/bin/bash
set -e

ZIPFILE=$1
OUTPUT_TIFF=$2
TEMP_DIR=$(mktemp -d)

mkdir -p $(dirname $OUTPUT_TIFF)
trap "rm -rf $TEMP_DIR" EXIT
echo "Working in temporary directory: $TEMP_DIR"

echo "Listing files in zip archive..."
unzip -l $ZIPFILE | grep '\.tif$' | awk '{print $NF}' | while read file; do
    echo "/vsizip/$ZIPFILE/$file"
done > $TEMP_DIR/tiles.txt

echo "Creating VRT from tiles..."
gdalbuildvrt $TEMP_DIR/temp_mosaic.vrt -input_file_list $TEMP_DIR/tiles.txt

echo "Normalizing NoData values..."
gdal_calc.py --calc="(A==-32767)*(-32768) + (A!=-32767)*(A)" \
    --format=GTiff \
    -A $TEMP_DIR/temp_mosaic.vrt \
    --outfile=$TEMP_DIR/normalized_mosaic.tif \
    --NoDataValue=-32768 \
    --co BLOCKXSIZE=2048 \
    --co BLOCKYSIZE=2048 \
    --co SPARSE_OK=YES \
    --config GDAL_CACHEMAX 50%

echo "Resampling to 90 m resolution..."
gdalwarp -tr 0.000833 0.000833 \
    -r bilinear \
    -srcnodata -32768 \
    -dstnodata -32768 \
    -wo INIT_DEST=NO_DATA \
    $TEMP_DIR/normalized_mosaic.tif $TEMP_DIR/resampled_mosaic.tif

echo "Calculating final output..."
gdal_calc.py --calc="(A==-32768)*(-32768) + (A>-32767)*(A/100)" \
    --format=GTiff \
    --type=Float32 \
    -A $TEMP_DIR/resampled_mosaic.tif \
    --outfile=$OUTPUT_TIFF \
    --NoDataValue=-32768 \
    --co COMPRESS=LZW \
    --co BIGTIFF=IF_SAFER \
    --config GDAL_CACHEMAX 50%