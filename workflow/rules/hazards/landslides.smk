""""
snakemake --cores 4 all_landslide_scenarios
"""

def get_reference_raster(wildcards, input_path=INPUTS):
    """Helper function to get the first raster file from a directory"""
    path = f"{input_path}/hazards/landslides/reference_raster"
    rasters = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".tif")]
    if len(rasters) == 0:
        raise ValueError(f"No raster files found in {path}")
    return rasters[0]


rule rasterise_landslide:
    """
    snakemake --cores 4 ../results/hazards/input/landslide_2030_ssp245_rp00005.tif
    """
    input:
        gpkg=lambda wildcards: expand("{path}/hazards/landslides/landslide_polygons_{rp}yr_{epoch}_{scenario}_BAU_runout.gpkg",
                    path=INPUTS,
                    rp=int(wildcards.rp),
                    epoch=wildcards.epoch,
                    scenario=wildcards.scenario
        )[0],
        reference=get_reference_raster
    params:
        crs=config["local_crs"]
    output:
        raster="../results/hazards/input/landslide_{epoch}_{scenario}_rp{rp}.tif"
    run:
        import rasterio
        import geopandas as gpd
        from rasterio.features import rasterize
        import numpy as np
        
        print(f"Reading reference: {input.reference}")
        print(f"Reading geopackage: {input.gpkg}")
        print(f"Output will be: {output.raster}")
        
        # read reference raster to get grid properties
        with rasterio.open(input.reference) as ref:
            meta = ref.meta.copy()
            transform = ref.transform
            shape = ref.shape
            print(f"Reference shape: {shape}")
            print(f"Reference transform: {transform}")
        
        # read geopackage
        gdf = gpd.read_file(input.gpkg, layer='runout_zones')
        print(f"Read {len(gdf)} features from runout_zones layer")
        print(f"Columns: {gdf.columns.tolist()}")

        gdf = gdf.to_crs(params.crs).buffer(500).to_crs(4326)
        
        if 'hazard_score' not in gdf.columns:
            raise ValueError(f"hazard_score column not found! Available columns: {gdf.columns.tolist()}")
        
        # rasterize to match reference grid
        print("Rasterizing...")
        rasterized = rasterize(
            [(geom, value) for geom, value in zip(gdf.geometry, gdf['hazard_score'])],
            out_shape=shape,
            transform=transform,
            fill=-32768,  # NoData value
            dtype='float32'
        )
        
        print(f"Rasterized shape: {rasterized.shape}")
        print(f"Value range: {rasterized.min()} to {rasterized.max()}")
        
        # Update metadata
        meta.update(dtype='float32', nodata=-32768, compress='lzw')
        
        # Write output
        print(f"Writing to {output.raster}")
        with rasterio.open(output.raster, 'w', **meta) as dst:
            dst.write(rasterized, 1)
        
        print("Done!")


rule all_landslide_scenarios:
    """
    snakemake --cores 4 all_landslide_scenarios
    """
    input:
        tiffs = expand(
            "../results/hazards/inputcl/{SUBCATEGORY}_{EPOCH}_{SCENARIO}_rp{RP}.tif",
            SUBCATEGORY=["landslide"],
            EPOCH=["2030"],
            SCENARIO=["ssp245"],
            RP = ["00005", "00010", "00025", "00050", "00100"]
        )