import logging
import json
from typing import Dict, Any, Union, Optional, List, TypedDict, Tuple
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

log = logging.getLogger(__name__)


class FilterDict(TypedDict, total=False):
    """TypedDict for filter specifications."""

    tags: Dict[str, Any]
    attributes: Dict[str, List[str]]


@dataclass
class GeometryInput:
    """Validated geometry input for OSM API requests."""

    type: str
    coordinates: List[Any]

    @classmethod
    def from_input(cls, geometry: Union[Dict[str, Any], str]) -> "GeometryInput":
        """
        Create a GeometryInput from either a dictionary or a JSON string.

        Args:
            geometry: GeoJSON geometry object or string

        Returns:
            Validated GeometryInput object

        Raises:
            ValidationError: If geometry is invalid
        """
        from .exceptions import ValidationError

        if isinstance(geometry, str):
            try:
                geometry_dict = json.loads(geometry)
                log.debug("Parsed geometry from JSON string")
            except json.JSONDecodeError:
                log.error("Failed to parse geometry JSON string")
                raise ValidationError("Invalid GeoJSON string")
        else:
            geometry_dict = geometry

        if (
            geometry_dict.get("type") == "FeatureCollection"
            and "features" in geometry_dict
        ):
            log.debug("Converting FeatureCollection to Geometry")
            if geometry_dict["features"]:
                feature = geometry_dict["features"][0]
                if "geometry" in feature:
                    geometry_dict = feature["geometry"]

        if "type" not in geometry_dict:
            log.error("Geometry missing 'type' field")
            raise ValidationError("Geometry must have a 'type' field")

        if "coordinates" not in geometry_dict:
            log.error("Geometry missing 'coordinates' field")
            raise ValidationError("Geometry must have a 'coordinates' field")

        valid_types = ["Polygon", "MultiPolygon"]
        if geometry_dict["type"] not in valid_types:
            log.error("Invalid geometry type: %s", geometry_dict["type"])
            raise ValidationError(f"Geometry type must be one of {valid_types}")

        # Check CRS if present (basic validation)
        if "crs" in geometry_dict:
            crs = geometry_dict.get("crs", {}).get("properties", {}).get("name")
            valid_crs = [
                "urn:ogc:def:crs:OGC:1.3:CRS84",
                "urn:ogc:def:crs:EPSG::4326",
                "WGS 84",
            ]
            if crs and crs not in valid_crs:
                log.warning("Unsupported CRS: %s. Raw Data API requires EPSG:4326", crs)
                raise ValidationError(
                    "Unsupported coordinate system. Raw Data API requires "
                    "GeoJSON in WGS84 (EPSG:4326) standard."
                )

        # Basic coordinate validation for first coordinate
        try:
            first_coord = cls._get_first_coordinate(geometry_dict["coordinates"])
            if first_coord and not cls._is_valid_coordinate(first_coord):
                log.error("Invalid coordinates: %s", first_coord)
                raise ValidationError(
                    "Coordinates appear to be invalid. Should be longitude/latitude "
                    "in the range of -180 to 180 and -90 to 90 respectively."
                )
        except (IndexError, TypeError):
            log.warning("Could not validate coordinates format")

        log.debug("Validated geometry of type %s", geometry_dict["type"])
        return cls(type=geometry_dict["type"], coordinates=geometry_dict["coordinates"])

    @staticmethod
    def _get_first_coordinate(coordinates):
        """Extract the first coordinate from nested arrays."""
        # For Polygon or MultiPolygon in GeoJSON, we need to navigate the nested structure
        # A Polygon coordinate is [[[x1,y1], [x2,y2], ...]]
        # A MultiPolygon coordinate is [[[[x1,y1], [x2,y2], ...]], ...]

        result = coordinates
        while isinstance(result, list) and isinstance(result[0], list):
            result = result[0]

        return result

    @staticmethod
    def _is_valid_coordinate(coord):
        """Check if a coordinate is valid (within expected range)."""
        if not isinstance(coord, list) or len(coord) < 2:
            return False
        return -180 <= coord[0] <= 180 and -90 <= coord[1] <= 90

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {"type": self.type, "coordinates": self.coordinates}


@dataclass
class RequestParams:
    """Validated parameters for OSM API requests."""

    file_name: str = "osm_export"
    output_type: str = "geojson"
    bind_zip: bool = True
    filters: Optional[FilterDict] = None
    geometry_type: Optional[List[str]] = None

    VALID_OUTPUT_TYPES = [
        "geojson",
        "shp",
        "kml",
        "mbtiles",
        "flatgeobuf",
        "csv",
        "geopackage",
        "pgdump",
    ]

    @classmethod
    def from_kwargs(cls, **kwargs) -> "RequestParams":
        """
        Create a RequestParams from keyword arguments.

        Args:
            **kwargs: Keyword arguments for request parameters

        Returns:
            Validated RequestParams object

        Raises:
            ValidationError: If parameters are invalid
        """
        from .exceptions import ValidationError

        # Convert to snake_case internally
        params = {}
        if "fileName" in kwargs:
            params["file_name"] = kwargs.pop("fileName")
        if "outputType" in kwargs:
            params["output_type"] = kwargs.pop("outputType")
        if "geometryType" in kwargs:
            params["geometry_type"] = kwargs.pop("geometryType")
        if "bindZip" in kwargs:
            params["bind_zip"] = kwargs.pop("bindZip")

        params.update(kwargs)

        if "output_type" in params and "bind_zip" in params:
            params["bind_zip"] = RequestParams.validate_bind_zip_compatibility(
                params["output_type"], params["bind_zip"]
            )

        instance = cls(**params)

        if instance.output_type not in cls.VALID_OUTPUT_TYPES:
            log.error("Invalid output type: %s", instance.output_type)
            raise ValidationError(f"outputType must be one of {cls.VALID_OUTPUT_TYPES}")

        return instance

    def to_api_params(self) -> Dict[str, Any]:
        """Convert to API parameter dictionary."""
        # Convert to camelCase for API
        params = {
            "fileName": self.file_name,
            "outputType": self.output_type,
            "bindZip": self.bind_zip,
        }

        if self.filters:
            params["filters"] = self.filters

        if self.geometry_type:
            params["geometryType"] = self.geometry_type

        return params

    @staticmethod
    def validate_bind_zip_compatibility(output_type, bind_zip):
        """Validate if the output format is compatible with bindZip=False"""
        streaming_compatible_formats = [
            "geojson",
            "cog",
            "fgb",
        ]  # Cloud Optimized GeoTIFF, FlatGeoBuf

        if not bind_zip and output_type.lower() not in streaming_compatible_formats:
            log.warning(
                f"Format '{output_type}' requires ZIP packaging. "
                f"Automatically setting bindZip=True"
            )
            return True
        return bind_zip


@dataclass(frozen=True)
class RawDataApiMetadata:
    """Immutable metadata about a dataset"""

    task_id: str
    format_ext: str
    timestamp: str
    size_bytes: int
    file_name: str
    download_url: str
    is_zipped: bool
    bbox: Optional[Tuple[float, float, float, float]] = None

    @classmethod
    def from_api_result(
        cls, result: Dict[str, Any], params: RequestParams
    ) -> "RawDataApiMetadata":
        """
        Create a RawDataApiMetadata from API result and request parameters.

        Args:
            result: API result dictionary from task status
            params: Request parameters used for the API request

        Returns:
            RawDataApiMetadata instance
        """
        task_result = result.get("result", {})
        task_id = result.get("id", "")
        timestamp = task_result.get("response_time", "")
        size_bytes = task_result.get("zip_file_size_bytes", 0)
        download_url = task_result.get("download_url", "")

        bbox = None
        query_area = task_result.get("queryArea", "")
        if query_area and query_area.startswith("bbox[") and query_area.endswith("]"):
            try:
                coords_str = query_area[5:-1]  # Remove "bbox[" and "]"
                coords = [float(x) for x in coords_str.split(",")]
                if len(coords) == 4:
                    bbox = tuple(coords)
                    log.debug("Extracted bbox: %s", bbox)
            except (ValueError, IndexError):
                log.warning("Could not parse bbox from queryArea: %s", query_area)

        return cls(
            is_zipped=params.bind_zip,
            file_name=params.file_name,
            task_id=task_id,
            format_ext=params.output_type,
            timestamp=timestamp,
            size_bytes=size_bytes,
            download_url=download_url,
            bbox=bbox,
        )

    def __str__(self) -> str:
        """Returns a string representation of RawDataApiMetadata for debugging purposes."""
        bbox_str = f"{self.bbox}" if self.bbox else "None"

        return (
            f"RawDataApiMetadata(\n"
            f"  task_id: {self.task_id}\n"
            f"  format_ext: {self.format_ext}\n"
            f"  timestamp: {self.timestamp}\n"
            f"  size_bytes: {self.size_bytes:,} bytes ({self._format_size()})\n"
            f"  file_name: {self.file_name}\n"
            f"  is_zipped: {self.is_zipped}\n"
            f"  bbox: {bbox_str}\n"
            f")"
        )

    def _format_size(self) -> str:
        """Helper method to format size in human-readable form."""
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024 or unit == "TB":
                return f"{size:.2f} {unit}"
            size /= 1024


class AutoExtractOption(Enum):
    """Options for controlling extraction behavior of ZIP archives."""

    automatic = auto()  # Decide based on format and size
    force_zip = auto()  # Always keep as zip
    force_extract = auto()  # Always extract regardless of size/format


@dataclass
class RawDataClientConfig:
    """Configuration for Raw Data API client."""

    access_token: Optional[str] = None
    memory_threshold_mb: int = 50
    base_api_url: str = "https://api-prod.raw-data.hotosm.org/v1"
    output_directory: Path = Path.cwd()
    stream: bool = False

    @property
    def memory_threshold_bytes(self) -> int:
        """Convert memory threshold to bytes."""
        return self.memory_threshold_mb * 1024 * 1024

    @classmethod
    def default(cls) -> "RawDataClientConfig":
        """Create a default configuration."""
        return cls()


@dataclass
class RawDataOutputOptions:
    """Options for controlling how output data is handled."""

    auto_extract: AutoExtractOption = AutoExtractOption.automatic

    @classmethod
    def default(cls) -> "RawDataOutputOptions":
        """Create default output options."""
        return cls()
