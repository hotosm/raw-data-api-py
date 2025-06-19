"""
Geometry utility functions for the OSM Data Client.

This module provides utility functions for working with GeoJSON geometry objects.
"""

import logging
from typing import Dict, Any

log = logging.getLogger(__name__)


def bbox_to_polygon(
    min_x: float, min_y: float, max_x: float, max_y: float
) -> Dict[str, Any]:
    """
    Convert a bounding box to a GeoJSON polygon.

    Args:
        min_x: Minimum X coordinate (longitude)
        min_y: Minimum Y coordinate (latitude)
        max_x: Maximum X coordinate (longitude)
        max_y: Maximum Y coordinate (latitude)

    Returns:
        GeoJSON Polygon
    """
    log.debug("Converting bbox [%f, %f, %f, %f] to polygon", min_x, min_y, max_x, max_y)

    # Basic validation
    if min_x > max_x or min_y > max_y:
        log.warning("Invalid bbox: min values greater than max values")

    if not (
        -180 <= min_x <= 180
        and -180 <= max_x <= 180
        and -90 <= min_y <= 90
        and -90 <= max_y <= 90
    ):
        log.warning("Bbox coordinates outside normal lat/lon ranges")

    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_x, min_y],
                [max_x, min_y],
                [max_x, max_y],
                [min_x, max_y],
                [min_x, min_y],
            ]
        ],
    }
