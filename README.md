### Pre-processing

#### Hazard data

All hazards processed to format

```
"{processed_data}/hazards/cleaned/{type}_{year}_{scenario}_rp{rp.zfill(5)}.tif
```

- Fathom floods: `fathom.py` to resample 30 m to 90 m and mosaic tiles.
- CHAZ tropical cyclones: `chaz.py` script to rename files and add assumptions (check docstring for details).
- Extreme heat: Created by Alison in correct format, copy manually.
- Landslides: Created by Pamela in correct format, copy manually.

### Post-processing

### Analysis and visualisations