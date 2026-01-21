import pandas as pd

def extract_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract prefix, hazard, epoch, scenario, and return period from hazard column name."""
    if "-" in hazcol:
        prefix, parts = hazcol.split("-")
    else:
        prefix = ""
        parts = hazcol
    parts = parts.split("_")
    hazard = parts[0]
    epoch = parts[1]
    scenario = parts[2]
    rp = str(int(parts[3].replace("rp", "")))
    if len(parts) > 4:
        stat = "_".join(parts[4:])
    else:
        stat = pd.NA
    return prefix, hazard, epoch, scenario, rp, stat