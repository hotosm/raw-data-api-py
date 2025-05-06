# OSM Data Client

A Python client for the Humanitarian OpenStreetMap Team (HOT) Raw Data API.

## Installation

```bash
pip install raw-data-api-py
```

## Conceptual Overview

The OSM Data Client allows you to extract OpenStreetMap data for specific geographic areas through the HOT Raw Data API. The workflow follows this pattern:

1. Define an area of interest (GeoJSON polygon)
2. Configure filters for specific OpenStreetMap features
3. Submit a request and wait for processing
4. Download and use the resulting data

## Quick Start

```python
import asyncio
from osm_data_client import get_osm_data

async def main():
    # Define area of interest
    geometry = {
        "type": "Polygon",
        "coordinates": [[
            [-73.98, 40.75],  # NYC area
            [-73.98, 40.76],
            [-73.97, 40.76],
            [-73.97, 40.75],
            [-73.98, 40.75]
        ]]
    }
    
    # Request building data
    result = await get_osm_data(
        geometry,
        fileName="nyc_buildings",
        outputType="geojson",
        filters={
            "tags": {
                "all_geometry": {
                    "building": []  # All buildings
                }
            }
        }
    )
    
    print(f"Data downloaded to: {result.path}")
    
if __name__ == "__main__":
    asyncio.run(main())
```

## Command-Line Interface

Extract data using the CLI:

```bash
python -m osm_data_client.cli --bounds -73.98 40.75 -73.97 40.76 --feature-type building --out buildings.geojson
```

## Key Components

- **get_osm_data**: Main function for simple requests
- **RawDataClient**: Configurable client for advanced usage
- **GeometryInput**: Handles polygon validation
- **RequestParams**: Handles request configuration
- **RawDataResult**: Contains the result file path and metadata

## Common Use Cases

### Configuring Output Directory

```python
from osm_data_client import RawDataClient, RawDataClientConfig

config = RawDataClientConfig(output_directory="/path/to/outputs")
client = RawDataClient(config)

result = await client.get_osm_data(geometry, **params)
```

### Controlling File Extraction

```python
from osm_data_client import RawDataOutputOptions, AutoExtractOption

# Always extract from zip archives
options = RawDataOutputOptions(auto_extract=AutoExtractOption.force_extract)

result = await client.get_osm_data(geometry, options, **params)
```

### Using Different Output Formats

```python
# GeoJSON example
result = await get_osm_data(
    geometry,
    outputType="geojson",
    filters={"tags": {"all_geometry": {"building": []}}}
)

# Shapefile example
result = await get_osm_data(
    geometry,
    outputType="shp",
    filters={"tags": {"all_geometry": {"highway": []}}}
)
```

## Error Handling

The client uses specific exception types for different errors:

```python
from osm_data_client.exceptions import ValidationError, APIRequestError

try:
    result = await get_osm_data(geometry, **params)
except ValidationError as e:
    print(f"Invalid input: {e}")
except APIRequestError as e:
    print(f"API error: {e}")
```

## API Reference

### Core Functions

```python
async def get_osm_data(
    geometry: Union[Dict[str, Any], str],
    **kwargs
) -> RawDataResult
```

### Client Classes

```python
class RawDataClient:
    async def get_osm_data(
        self,
        geometry: Union[Dict[str, Any], str], 
        output_options: RawDataOutputOptions = RawDataOutputOptions.default(),
        **kwargs
    ) -> RawDataResult
```

### Configuration Classes

```python
@dataclass
class RawDataClientConfig:
    access_token: Optional[str] = None
    memory_threshold_mb: int = 50
    base_api_url: str = "https://api-prod.raw-data.hotosm.org/v1"
    output_directory: Path = Path.cwd()
```

```python
class AutoExtractOption(Enum):
    automatic = auto()     # Decide based on format and size
    force_zip = auto()     # Always keep as zip
    force_extract = auto() # Always extract
```

## CLI Options

```
python -m osm_data_client.cli [options]

Options:
  --geojson PATH          Path to GeoJSON file or GeoJSON string
  --bounds XMIN YMIN XMAX YMAX  
                          Bounds coordinates in EPSG:4326
  --feature-type TYPE     Type of feature to download (default: "building")
  --out PATH              Output path (default: "./osm_data.geojson")
  --format FORMAT         Output format (geojson, shp, kml, etc.)
  --no-zip                Do not request data as a zip file
  --extract               Extract files from zip archive
  --verbose, -v           Enable verbose logging
```
