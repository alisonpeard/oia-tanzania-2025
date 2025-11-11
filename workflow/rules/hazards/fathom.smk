def format_scenario(scenario):
    if scenario.startswith("SSP"):
        return scenario.replace("p", ".").replace("-", "_")
    elif scenario == "hist":
        return "historical"


rule mosaic_fathom:
    """
    snakemake --cores 4 ../results/input/hazards/fluvial_2050_SSP2-4p5_rp00020.tif
    snakemake --cores 4 ../results/input/hazards/pluvial_2050_SSP5-8p5_rp00500.tif
    """
    input:
        zipfile=lambda wildcards: "{path}/input/hazards/flood/fathom/{subcategory}/{epoch}/{scenario}/1in{rp}.zip".format(
            path=INPUTS,
            subcategory=wildcards.SUBCATEGORY,
            epoch=wildcards.EPOCH,
            scenario=format_scenario(wildcards.SCENARIO),
            rp=int(wildcards.RP)
        )
    output:
        tiff="../results/input/hazards/{SUBCATEGORY}_{EPOCH}_{SCENARIO}_rp{RP}.tif"
    shell:
        """
        TEMP_DIR=$(mktemp -d)

        mkdir -p $(dirname {output.tiff})
        trap "rm -rf $TEMP_DIR" EXIT
        echo "Working in temporary directory: $TEMP_DIR"

        echo "Listing files in zip archive..."
        unzip -l {input.zipfile} | grep '\.tif$' | awk '{{print $NF}}' | while read file; do
            echo "/vsizip/{input.zipfile}/$file"
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
            --outfile={output.tiff} \
            --NoDataValue=-32768 \
            --co COMPRESS=LZW \
            --co BIGTIFF=IF_SAFER \
            --config GDAL_CACHEMAX 50%

        rm -rf $TEMP_DIR
        """


rule all_fathom_scenarios:
    input:
        tiffs = expand(
            "../results/input/hazards/flood-{SUBCATEGORY}_{EPOCH}_{SCENARIO}_rp{RP}.tif",
            SUBCATEGORY=["pluvial", "fluvial", "coastal"],
            EPOCH=["2050", "2080"],
            SCENARIO=["SSP2-4p5", "SSP5-8p5"],
            RP=["00005", "00010", "00100", "00200", "00500", "01000"],
        )


rule all_fathom_historical:
    input:
        tiffs = expand(
            "../results/input/hazards/flood-{SUBCATEGORY}_{EPOCH}_{SCENARIO}_rp{RP}.tif",
            SUBCATEGORY=["pluvial", "fluvial", "coastal"],
            EPOCH=["2020"],
            SCENARIO=["historical"],
            RP=["00005", "00010", "00100", "00200", "00500", "01000"],
        )   