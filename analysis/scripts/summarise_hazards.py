# %%
import os
import pandas as pd
from pathlib import Path

import utils

pd.set_option('display.max_rows', None)

cfg = utils.load_config()
hazdir = os.path.join(cfg["outputs"], "hazards", "input")
outpath = os.path.join(cfg["outputs"], "hazards", "input-summary.xlsx")
hazfiles = os.listdir(hazdir)

# remove files starting with '._'
hazfiles = [f for f in hazfiles if not f.startswith('._')]

hazards = []
for hazfile in hazfiles:
    hazstem = Path(hazfile).stem
    print(f"Processing {hazstem}")
    info:tuple = utils.extract_hazard_info(hazstem)
    hazards.append(info)

hazdf = pd.DataFrame(hazards, columns=["hazard", "epoch", "scenario", "return_period"])
hazdf = hazdf.groupby(["hazard", "epoch", "scenario"]).agg({"return_period": list})
hazdf.to_excel(outpath, index=True)
print(f"Number of hazards: {len(hazfiles)}")
hazdf
# %%
