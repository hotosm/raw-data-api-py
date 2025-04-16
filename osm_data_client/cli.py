import argparse
import asyncio
import json
import os
import sys
from typing import Dict, Any, List
from importlib.metadata import version, PackageNotFoundError

from .api import get_osm_data
from .utils.geometry import bbox_to_polygon
from .utils.file import save_to_geojson, split_by_tiles
from .exceptions import OSMClientError

def main():
    """
    Command-line interface for OSM data download.
    """
    # Check for version flag first 
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        try:
            ver = version("osm_data_client")
        except PackageNotFoundError:
            ver = "development"
        print(f"OSM Data Client version {ver}")
        return 0

    parser = argparse.ArgumentParser(
        description="Download GeoJSON data from the Raw Data API."
    )
    
    # Add version argument
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the version and exit"
    )
    
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--geojson", type=str, help="Path to the GeoJSON file or GeoJSON string."
    )
    group.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("xmin", "ymin", "xmax", "ymax"),
        help="Bounding box coordinates (assumed to be in EPSG:4326).",
    )
    parser.add_argument(
        "--api-url",
        default="https://api-prod.raw-data.hotosm.org/v1",
        help="Base URL for the Raw Data API",
    )
    parser.add_argument(
        "--feature-type", default="building", help="Type of feature to download"
    )
    parser.add_argument(
        "--out",
        default=os.path.join(os.getcwd(), "osm_data.geojson"),
        help="Path to save the output file",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        help="Split the output GeoJSON data into individual tiles",
    )
    parser.add_argument(
        "--split-dir",
        default="tiles",
        help="Directory to save split tiles (if --split is used)",
    )
    parser.add_argument(
        "--zoom",
        type=int,
        default=14,
        help="Zoom level for tile splitting (if --split is used)",
    )
    parser.add_argument(
        "--format",
        choices=["geojson", "shp"],
        default="geojson",
        help="Output format",
    )
    
    # Parse arguments or exit with error
    args = parser.parse_args()

    async def run():
        try:
            if args.bbox:
                geometry = bbox_to_polygon(*args.bbox)
            else:
                if os.path.exists(args.geojson):
                    with open(args.geojson, 'r') as f:
                        geometry = json.load(f)
                else:
                    geometry = args.geojson
            
            params = {
                "outputType": args.format,
                "fileName": os.path.splitext(os.path.basename(args.out))[0],
                "filters": {
                    "tags": {
                        "all_geometry": {
                            args.feature_type: []
                        }
                    }
                }
            }
            
            print(f"Downloading OSM data for {args.feature_type}...")
            result = await get_osm_data(geometry, **params)
            
            save_to_geojson(result, args.out)
            print(f"Downloaded OSM data saved to: {args.out}")
            
            if args.split:
                try:
                    print(f"Splitting data into tiles at zoom level {args.zoom}...")
                    split_files = split_by_tiles(result, args.split_dir, args.zoom)
                    print(f"Split into {len(split_files)} tiles in: {args.split_dir}")
                except ImportError as e:
                    print(f"Warning: Could not split tiles - {str(e)}")
            
        except OSMClientError as e:
            print(f"Error: {e}")
            return 1
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return 1
        
        return 0

    return asyncio.run(run())

if __name__ == "__main__":
    exit(main())
