from typing import Dict, Any, List, Optional, Union, Callable
import json

def reproject_geojson(geojson_data: Dict[str, Any], target_crs: str) -> Dict[str, Any]:
    """
    Reproject GeoJSON data to the specified CRS.
    
    This function requires geopandas to be installed.

    Args:
        geojson_data: GeoJSON data to reproject
        target_crs: Target CRS (e.g., "4326" or "3857")

    Returns:
        Reprojected GeoJSON data
        
    Raises:
        ImportError: If geopandas is not installed
    """
    # Skip reprojection if target is already 4326 (which is what the API returns)
    if target_crs == "4326":
        return geojson_data

    try:
        import geopandas as gpd
    except ImportError:
        raise ImportError(
            "This function requires geopandas. "
            "Install with: pip install geopandas"
        )
    
    # Create a GeoDataFrame from the GeoJSON
    gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
    
    # Set the CRS to 4326 (the CRS of the data from the API)
    gdf.set_crs(epsg=4326, inplace=True)
    
    # Reproject to the target CRS
    gdf = gdf.to_crs(epsg=int(target_crs))
    
    # Convert back to GeoJSON
    reprojected_geojson = json.loads(gdf.to_json())
    
    # Add CRS information to the GeoJSON
    reprojected_geojson["crs"] = {
        "type": "name",
        "properties": {"name": f"urn:ogc:def:crs:EPSG::{target_crs}"}
    }
    
    return reprojected_geojson

def filter_features(data: Dict[str, Any], filter_func: Callable[[Dict[str, Any]], bool]) -> Dict[str, Any]:
    """
    Filter GeoJSON features using a custom function.
    
    Args:
        data: GeoJSON data to filter
        filter_func: Function that takes a feature and returns True to keep it
        
    Returns:
        Filtered GeoJSON data
    """
    result = data.copy()
    result["features"] = [f for f in data["features"] if filter_func(f)]
    return result
