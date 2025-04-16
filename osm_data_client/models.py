from typing import Dict, Any, Union, Optional, List, TypedDict
from dataclasses import dataclass, field
import json

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
    def from_input(cls, geometry: Union[Dict[str, Any], str]) -> 'GeometryInput':
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
            except json.JSONDecodeError:
                raise ValidationError("Invalid GeoJSON string")
        else:
            geometry_dict = geometry
        
        if geometry_dict.get("type") == "FeatureCollection" and "features" in geometry_dict:
            if geometry_dict["features"]: 
                feature = geometry_dict["features"][0]
                if "geometry" in feature:
                    geometry_dict = feature["geometry"]
        
        if "type" not in geometry_dict:
            raise ValidationError("Geometry must have a 'type' field")
        
        if "coordinates" not in geometry_dict:
            raise ValidationError("Geometry must have a 'coordinates' field")
        
        valid_types = ["Polygon", "MultiPolygon"]
        if geometry_dict["type"] not in valid_types:
            raise ValidationError(f"Geometry type must be one of {valid_types}")
        
        return cls(
            type=geometry_dict["type"],
            coordinates=geometry_dict["coordinates"]
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": self.type,
            "coordinates": self.coordinates
        }

@dataclass
class RequestParams:
    """Validated parameters for OSM API requests."""
    file_name: str = "osm_export"
    output_type: str = "geojson"
    filters: Optional[FilterDict] = None
    geometry_type: Optional[List[str]] = None
    
    VALID_OUTPUT_TYPES = [
        "geojson", "shp", "kml", "mbtiles", 
        "flatgeobuf", "csv", "geopackage", "pgdump"
    ]
    
    @classmethod
    def from_kwargs(cls, **kwargs) -> 'RequestParams':
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
        if "filters" in kwargs:
            params["filters"] = kwargs.pop("filters")
        
        # Add any remaining kwargs
        params.update(kwargs)
        
        # Create instance
        instance = cls(**params)
        
        # Validate
        if instance.output_type not in cls.VALID_OUTPUT_TYPES:
            raise ValidationError(f"outputType must be one of {cls.VALID_OUTPUT_TYPES}")
            
        return instance
    
    def to_api_params(self) -> Dict[str, Any]:
        """Convert to API parameter dictionary."""
        # Convert to camelCase for API
        params = {
            "fileName": self.file_name,
            "outputType": self.output_type
        }
        
        if self.filters:
            params["filters"] = self.filters
            
        if self.geometry_type:
            params["geometryType"] = self.geometry_type
            
        return params

