import os
import json
from typing import Dict, Any, List, Optional, Union

def save_to_geojson(data: Dict[str, Any], file_path: str) -> str:
    """
    Save GeoJSON data to a file.
    
    Args:
        data: GeoJSON data to save
        file_path: Path to save the file
        
    Returns:
        Path to the saved file
    """
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    
    return file_path

def split_by_tiles(
    data: Dict[str, Any], 
    output_dir: str, 
    zoom_level: int = 14,
    prefix: str = "tile"
) -> List[str]:
    """
    Split GeoJSON data into tiles.
    
    This function requires geopandas to be installed.
    
    Args:
        data: GeoJSON data to split. Assumed to be in EPSG:4326.
        output_dir: Directory to save the tile files
        zoom_level: Zoom level to determine tile size
        prefix: Prefix for tile file names
        
    Returns:
        List of paths to the created tile files
        
    Raises:
        ImportError: If required dependencies are not installed
    """
    try:
        import geopandas as gpd
        from shapely.geometry import box
        import mercantile
    except ImportError:
        raise ImportError(
            "This function requires geopandas, shapely and mercantile"
            "Install with: pip install geopandas shapely mercantile"
        )
    
    os.makedirs(output_dir, exist_ok=True)
    
    gdf = gpd.GeoDataFrame.from_features(data["features"])
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    elif gdf.crs.to_epsg() != 4326:
        print(f"Warning: Input data CRS is {gdf.crs}. Converting to EPSG:4326.")
        gdf = gdf.to_crs(epsg=4326)

    if gdf.empty:
        print("Warning: Input GeoDataFrame is empty. No tiles will be generated.")
        return []

    geographic_bounds = gdf.total_bounds # [minx, miny, maxx, maxy] in EPSG:4326

    try:
        gdf_mercator = gdf.to_crs(epsg=3857)
    except Exception as e:
        print(f"Error reprojecting data to EPSG:3857: {e}")
        raise RuntimeError(f"Failed to reproject GeoDataFrame to EPSG:3857: {e}") from e

    tiles_data = []

    west, south, east, north = geographic_bounds
    # mercantile.tiles generates Tile(x, y, z) objects
    tile_indices = list(mercantile.tiles(west, south, east, north, zooms=zoom_level))
    for tile in tile_indices:
        # Get bounds in Web Mercator (EPSG:3857)
        mercator_bounds = mercantile.xy_bounds(tile)
        tiles_data.append({
            'x': tile.x, 'y': tile.y, 'z': tile.z,
            'bbox_mercator': [mercator_bounds.left, mercator_bounds.bottom, mercator_bounds.right, mercator_bounds.top]
        })

    output_files = []

    try:
        sindex = gdf_mercator.sindex
        use_sindex = True
    except Exception:
        # Older geopandas might not have sindex readily available or might fail
        sindex = None
        use_sindex = False
        print("Warning: Could not build spatial index. Falling back to slower intersection checks.")

    for tile_info in tiles_data:
        tile_box_mercator = box(*tile_info['bbox_mercator'])

        if use_sindex:
            possible_matches_idx = list(sindex.intersection(tile_box_mercator.bounds))
            subset_gdf = gdf_mercator.iloc[possible_matches_idx]
            intersecting_gdf = subset_gdf[subset_gdf.intersects(tile_box_mercator)]
        else:
            intersecting_gdf = gdf_mercator[gdf_mercator.intersects(tile_box_mercator)]

        if not intersecting_gdf.empty:
            try:
                intersecting_gdf_4326 = intersecting_gdf.to_crs(epsg=4326)
            except Exception as e:
                print(f"Error reprojecting tile {tile_info['z']}/{tile_info['x']}/{tile_info['y']} data back to EPSG:4326: {e}")
                continue # Skip this tile if reprojection fails

            file_path = os.path.join(output_dir, f"{prefix}_{tile_info['z']}_{tile_info['x']}_{tile_info['y']}.geojson")

            try:
                intersecting_gdf_4326.to_file(file_path, driver='GeoJSON')
                output_files.append(file_path)
            except Exception as e:
                 print(f"Error saving tile {file_path}: {e}")

    return output_files

