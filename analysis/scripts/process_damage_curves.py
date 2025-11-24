"""Check damage_curves formatting.

We want everything standardised to 'intensity' and 'damage_fraction_mean' columns."""
# %%
import pandas as pd
from pathlib import Path

indir = "/Users/alison/Local/data/oia-tanzania-2025/input/curves"
outdir = "../../config/damage_curves"

attempt_autofix = True

intensity_synonyms = ["flood_depth_m", "hazard_score", "wind_speed_m_per_s"]
damage_synonyms = ["damage_frac"]


def check_for_synonyms(df, string, synonyms):
    if string in df.columns:
        print(f"  ✅ '{string}' found in: {df.columns.tolist()}")
        return df
    else:
        for synonym in synonyms:
            if synonym in df.columns:
                print(f"  ⚠️  Found synonym for '{string}': {synonym}, renaming.")
                if attempt_autofix:
                    df = df.rename(columns={synonym: string})
                    return df
                else:
                    print("    (autofix disabled, not renaming)")
                    return df
        print(f"  ❌ Did not find synonym for '{string}'.")
    return df


for path in Path(indir).rglob("*.csv"):
    print(f"Checking {path}")
    df = pd.read_csv(path, comment='#')

    df = check_for_synonyms(df, "intensity", intensity_synonyms)
    df = check_for_synonyms(df, "damage_fraction_mean", damage_synonyms)

    outpath = str(path).replace(indir, outdir)
    df.to_csv(outpath, index=False)
    print(f"  Wrote to {outpath}\n")

# %%
