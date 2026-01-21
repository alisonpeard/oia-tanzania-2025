"""Check damage_curves formatting.

We want everything standardised to 'intensity' and 'damage_fraction_mean' columns.

No need to make fake ones; snakemake can handle it. But for clarity will make.
"""
# %%
import os
import pandas as pd
from pathlib import Path
from oi_risk import config


REMAKE = False
AUTOFIX = True
DAMAGE_SYNONYMS = ["damage_frac"]
INTENSITY_SYNONYMS = ["flood_depth_m", "hazard_score", "wind_speed_m_per_s"]


def check_for_synonyms(df, string, synonyms):
    if string in df.columns:
        print(f"  ✅ '{string}' found in: {df.columns.tolist()}")
        return df
    else:
        for synonym in synonyms:
            if synonym in df.columns:
                print(f"  ⚠️  Found synonym for '{string}': {synonym}, renaming.")
                if AUTOFIX:
                    df = df.rename(columns={synonym: string})
                    return df
                else:
                    print("    (autofix disabled, not renaming)")
                    return df
        print(f"  ❌ Found no synonyms for unknown field '{string}'.")
    return df


if __name__ == "__main__":
    config = config.load_config()
    indir = Path(config['paths']['processed_data']) / "damage_curves"
    outdir = Path(config["paths"]["snakemake_data"]) / "config" / "damage_curves"

    for path in Path(indir).rglob("*.csv"):
        outpath = Path(str(path).replace(str(indir), str(outdir)))
        outpath.parent.mkdir(parents=True, exist_ok=True)

        if os.path.exists(outpath) and not REMAKE:
            print(f"Skipping existing file {outpath}")
            continue

        df = pd.read_csv(path, comment='#')
        df = check_for_synonyms(df, "intensity", INTENSITY_SYNONYMS)
        df = check_for_synonyms(df, "damage_fraction_mean", DAMAGE_SYNONYMS)
        df.to_csv(outpath, index=False)
        print(f"  Wrote to {outpath}\n")


    asset_types = [p.stem for p in outdir.glob("**/*.csv")]
    
    dummy_df = pd.DataFrame({
        "intensity": [0.0, 1.0],
        "damage_fraction_min": [0.0, float("nan")],
        "damage_fraction_mean": [0.0, float("nan")],
        "damage_fraction_max": [0.0, float("nan")],
    }, dtype=float)

    for heat_hazard in ["tasmax", "hd35"]:
        for asset_type in asset_types:
            outpath = outdir / heat_hazard / (asset_type + ".csv")
            if outpath.exists():
                print(f"  Skipping existing heat damage curve: {outpath}")
                continue
            outpath.parent.mkdir(parents=True, exist_ok=True)
            dummy_df.to_csv(outpath, index=False)
            print(f"  Wrote dummy heat damage curve to {outpath}\n")

# %%
