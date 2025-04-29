"""
Command-line interface for the OSM Data Client.

This module provides a command-line interface for downloading OSM data using
the Raw Data API.
"""
import argparse
import asyncio
import json
import sys
import logging
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError

from .client import RawDataClient
from .models import AutoExtractOption, RawDataClientConfig, RawDataOutputOptions
from .utils.geometry import bbox_to_polygon
from .exceptions import OSMClientError

log = logging.getLogger(__name__)

def setup_logging(verbose: bool) -> None:
    """
    Set up logging with appropriate verbosity.
    
    Args:
        verbose: Whether to enable verbose logging
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout
    )
    
    # Set specific loggers to WARNING to avoid noise
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    
    if verbose:
        log.debug("Verbose logging enabled")


async def run_cli(args: argparse.Namespace) -> int:
    """
    Execute the CLI command.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Prepare geometry
        if args.bbox:
            log.info("Using bounding box: %s", args.bbox)
            geometry = bbox_to_polygon(*args.bbox)
        else:
            geojson_path = Path(args.geojson)
            if geojson_path.exists():
                log.info("Loading GeoJSON from file: %s", geojson_path)
                with geojson_path.open('r') as f:
                    geometry = json.load(f)
            else:
                log.info("Using GeoJSON string from command line")
                geometry = args.geojson

        if args.no_zip and args.format.lower() not in ["geojson"]:
            log.warning(
                f"Format '{args.format}' requires ZIP packaging. "
                f"Ignoring --no-zip option"
            )
            no_zip = False
        else:
            no_zip = args.no_zip

        # Prepare parameters
        params = {
            "outputType": args.format,
            "fileName": Path(args.out).stem,
            "bindZip": not no_zip,
            "filters": {
                "tags": {
                    "all_geometry": {
                        args.feature_type: []
                    }
                }
            }
        }
        
        # Configure the client
        config = RawDataClientConfig(
            access_token=args.token,
            base_api_url=args.api_url,
            output_directory=Path(args.out).parent,# Set output directory from --out argument
            memory_threshold_mb=args.memory_threshold
        )
        
        if args.extract:
            extract_option = AutoExtractOption.force_extract
        else:
            extract_option = AutoExtractOption.automatic

        output_options = RawDataOutputOptions(auto_extract=extract_option)
        
        log.info("Downloading OSM data for %s...", args.feature_type)
        result = await RawDataClient(config).get_osm_data(geometry, output_options, **params)
        
        if not result.exists():
            log.error("Download failed - no output file was created")
            return 1
            
        log.info("Downloaded OSM data saved to: %s", result)
        
        return 0
        
    except OSMClientError as e:
        log.error("Error: %s", str(e))
        return 1
    except Exception as e:
        log.error("Unexpected error: %s", str(e))
        return 1

def main() -> int:
    """
    Main entry point for the CLI.
    
    Returns:
        Exit code
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Download OSM data from the Raw Data API."
    )
    
    # Add version argument
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the version and exit"
    )
    
    # Add geometry source arguments (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--geojson", type=str, help="Path to GeoJSON file or GeoJSON string."
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
        help="Base URL for the Raw Data API"
    )
    parser.add_argument(
        "--token",
        help="Access token for the Raw Data API (optional)"
    )
    
    parser.add_argument(
        "--feature-type", default="building", help="Type of feature to download"
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path.cwd() / "osm_data.geojson",
        help="Path to save the output file"
    )
    parser.add_argument(
        "--format",
        choices=["geojson", "shp", "kml", "mbtiles", "flatgeobuf", "csv", "geopackage", "pgdump"],
        default="geojson",
        help="Output format"
    )
    
    parser.add_argument(
        "--memory-threshold",
        type=int,
        default=50,
        help="Memory threshold in MB for extraction decisions (default: 50)"
    )

    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Do not request data as a zip file"
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract files from zip archive if possible"
    )
    
    # Add verbose logging flag
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    
    # Check for version flag first 
    if args.version:
        try:
            ver = version("osm_data_client")
        except PackageNotFoundError:
            ver = "development"
        print(f"OSM Data Client version {ver}")
        return 0

    if not args.geojson and not args.bbox:
        parser.error("one of the arguments --geojson --bbox is required")

    # Run the CLI asynchronously
    return asyncio.run(run_cli(args))

if __name__ == "__main__":
    sys.exit(main())
