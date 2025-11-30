import os
import yaml


def load_config(path=None):
    path = path or os.path.join("..", "..", "workflow", "config.yaml")
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg