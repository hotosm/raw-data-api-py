from typing import Dict, Any, Tuple, Union, Optional

def bbox_to_polygon(min_x: float, min_y: float, max_x: float, max_y: float) -> Dict[str, Any]:
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
    return {
        "type": "Polygon",
        "coordinates": [[
            [min_x, min_y],
            [max_x, min_y],
            [max_x, max_y],
            [min_x, max_y],
            [min_x, min_y]
        ]]
    }

def convert_from_crs(geometry: Dict[str, Any], from_crs: str, to_crs: str = "4326") -> Dict[str, Any]:
    """
    Convert a geometry from one CRS to another.
    
    This function requires geopandas to be installed.
    
    Args:
        geometry: GeoJSON geometry to convert
        from_crs: Source CRS (e.g., "3857")
        to_crs: Target CRS (e.g., "4326")
        
    Returns:
        Converted GeoJSON geometry
        
    Raises:
        ImportError: If geopandas is not installed
    """
    try:
        import geopandas as gpd
        from shapely.geometry import shape
    except ImportError:
        raise ImportError(
            "This function requires geopandas and shapely. "
            "Install with: pip install geopandas shapely"
        )
    
    # Create a GeoDataFrame from the geometry
    gdf = gpd.GeoDataFrame(
        geometry=[shape(geometry)], 
        crs=f"EPSG:{from_crs}"
    )
    
    # Convert to target CRS
    gdf = gdf.to_crs(f"EPSG:{to_crs}")
    
    # Return the converted geometry
    return gdf.geometry.values[0].__geo_interface__
