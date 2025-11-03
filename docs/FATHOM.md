## Fathom flood hazard data

Note the tiny grid (1 arcsec) size of the Fathom data makes this very slow so we resample to 3 arcsec for processing efficiency.

To process Fathom input data, place input files in the following structure:

```bash
snakemake --cores 4 -- "../results/input/hazards/fathom/fluvial_undefended/2050/SSP2-4p5/rp00020.tif"
```