"""
inboxpilot/config_loader.py
Load and merge config from config.yaml + environment variables.
"""
from __future__ import annotations
import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

DEFAULT_CONFIG_PATH = "config.yaml"


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load config.yaml; return defaults if not found."""
    if os.path.exists(path):
        with open(path, "r") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    # Override with environment variables
    email_cfg = cfg.setdefault("email", {})
    if os.environ.get("INBOX_EMAIL"):
        email_cfg["username"] = os.environ["INBOX_EMAIL"]
    if os.environ.get("INBOX_PASSWORD"):
        email_cfg["password"] = os.environ["INBOX_PASSWORD"]

    return cfg


def save_config(cfg: Dict[str, Any], path: str = DEFAULT_CONFIG_PATH) -> None:
    with open(path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
