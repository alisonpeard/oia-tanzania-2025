import os
import yaml

def load_config(path=None):
    path = path or os.path.join("..", "..", "workflow", "config.yaml")
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg


def extract_hazard_info(hazcol:str) -> tuple[str, str, str, int]:
    """Extract hazard, epoch, scenario, and return period from hazard column name."""
    parts = hazcol.replace("hazard-", "").split("_")
    hazard = parts[0]
    epoch = parts[1]
    scenario = parts[2]
    rp = str(int(parts[3].replace("rp", "")))
    return hazard, epoch, scenario, rp