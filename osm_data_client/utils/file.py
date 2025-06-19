"""
File utility functions for the OSM Data Client.

This module provides utility functions for working with files
"""

import json
import logging
from typing import Dict, Any
from pathlib import Path

log = logging.getLogger(__name__)


def save_to_geojson(data: Dict[str, Any], file_path: str) -> Path:
    """
    Save GeoJSON data to a file.

    Args:
        data: GeoJSON data to save
        file_path: Path to save the file

    Returns:
        Path to the saved file
    """
    path = Path(file_path)
    log.info("Saving GeoJSON data to %s", path)

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    log.debug("GeoJSON data saved successfully")
    return path
