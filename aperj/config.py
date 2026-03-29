"""Configuration management - loading, creating, and validating config files."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "aperj"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yml"
COOKIES_DIR = DEFAULT_CONFIG_DIR / "cookies"

DEFAULT_CONFIG: dict[str, Any] = {
    "keywords": [],
    "region": "Rio de Janeiro, RJ",
    "max_results_per_source": 200,
    "flaresolverr_url": "",  # e.g. "http://localhost:8191/v1"
    "output": {
        "format": "rich",
        "csv_path": "apes.csv",
    },
    "sources": {
        "zapimoveis": {"enabled": True},
        "vivareal": {"enabled": True},
        "imovelweb": {"enabled": False},  # listing pages return HTTP 500
        "olx": {"enabled": True},
        "nuroa": {"enabled": True},
        "nestoria": {"enabled": True},
        "portalrjimoveis": {"enabled": True},
        "imoveisnet": {"enabled": True},
        "mercadolivre": {"enabled": True},
        "judicearaujo": {"enabled": True},
        "lopes": {"enabled": True},
        "patrimovel": {"enabled": True},
        "cyrela": {"enabled": True},
        "even": {"enabled": True},
        "mrv": {"enabled": False},  # fully client-rendered SPA, no server-side data
        "privilegioimoveis": {"enabled": True},
        "quintoandar": {"enabled": True},
    },
    "auth": {},
}


def init_config(path: Path | None = None) -> Path:
    """Create a default configuration file and the cookies directory."""
    path = path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)

    if path.exists():
        logger.warning("Config file already exists at %s - not overwriting.", path)
        return path

    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(DEFAULT_CONFIG, fh, default_flow_style=False, sort_keys=False)

    logger.info("Default config written to %s", path)
    logger.info("Cookies directory created at %s", COOKIES_DIR)
    return path


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load configuration from *path* (falling back to the default location)."""
    path = path or DEFAULT_CONFIG_PATH

    if not path.exists():
        logger.info("No config file found at %s - using built-in defaults.", path)
        return dict(DEFAULT_CONFIG)

    logger.info("Loading config from %s", path)
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def get_keywords(config: dict[str, Any], cli_keywords: list[str] | None = None) -> list[str]:
    """Merge keywords from config and CLI arguments (CLI takes precedence)."""
    kw: list[str] = list(config.get("keywords", []))
    if cli_keywords:
        kw.extend(cli_keywords)
    # deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for k in kw:
        low = k.strip().lower()
        if low and low not in seen:
            seen.add(low)
            deduped.append(k.strip())
    return deduped


def get_source_config(config: dict[str, Any], source_name: str) -> dict[str, Any]:
    """Return source-specific configuration section."""
    return config.get("sources", {}).get(source_name, {})


def get_auth(config: dict[str, Any], source_name: str) -> dict[str, str]:
    """Return auth credentials for a given source (empty dict if none)."""
    return config.get("auth", {}).get(source_name, {})


def get_cookie_path(source_name: str) -> Path | None:
    """Return the cookie file path for *source_name* if it exists."""
    cookie_file = COOKIES_DIR / source_name
    if cookie_file.exists():
        logger.debug("Found cookie file for %s at %s", source_name, cookie_file)
        return cookie_file
    return None


def load_cookies(source_name: str) -> dict[str, str]:
    """Load cookies from the source's cookie file (Netscape/curl format or key=value)."""
    cookie_path = get_cookie_path(source_name)
    if cookie_path is None:
        return {}

    cookies: dict[str, str] = {}
    with open(cookie_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Try key=value first
            if "=" in line and "\t" not in line:
                key, _, val = line.partition("=")
                cookies[key.strip()] = val.strip()
            else:
                # Netscape format: domain  flag  path  secure  expiry  name  value
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
    logger.debug("Loaded %d cookies for %s", len(cookies), source_name)
    return cookies
