import asyncio
import json
import os
import pytest
from pathlib import Path

from osm_data_client import get_osm_data

TEST_DIR = Path("tests/test_data")
OUTPUT_DIR = TEST_DIR / "output"

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_API_TESTS") == "1",
    reason="Skipping tests that require API access"
)

class TestAPIIntegration:
    """Integration tests for the API client."""
    
    @pytest.mark.asyncio
    async def test_get_buildings(self):
        """Test fetching building data from a small area."""
        # Define a very small area to keep the test quick
        geometry = {
            "type": "Polygon",
            "coordinates": [[
                [-73.9851, 40.7572],
                [-73.9850, 40.7572],
                [-73.9850, 40.7573],
                [-73.9851, 40.7573],
                [-73.9851, 40.7572]
            ]]
        }
        
        params = {
            "fileName": "test_buildings",
            "outputType": "geojson",
            "filters": {
                "tags": {
                    "all_geometry": {
                        "building": []
                    }
                }
            }
        }
        
        try:
            result = await get_osm_data(geometry, **params)
            
            # Verify the structure of the result
            assert "type" in result
            assert result["type"] == "FeatureCollection"
            assert "features" in result
            
            # Save the result for inspection
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            with open(OUTPUT_DIR / "test_buildings.geojson", "w") as f:
                json.dump(result, f)
                
            print(f"Found {len(result['features'])} buildings")
            
        except Exception as e:
            pytest.fail(f"API call failed: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_get_amenities(self):
        """Test fetching amenity data from a small area."""
        # Define a slightly larger area for amenities
        geometry = {
            "type": "Polygon",
            "coordinates": [[
                [-73.990, 40.757],
                [-73.985, 40.757],
                [-73.985, 40.760],
                [-73.990, 40.760],
                [-73.990, 40.757]
            ]]
        }
        
        params = {
            "fileName": "test_amenities",
            "outputType": "geojson",
            "filters": {
                "tags": {
                    "all_geometry": {
                        "amenity": []
                    }
                }
            }
        }
        
        try:
            result = await get_osm_data(geometry, **params)
            
            # Verify the structure of the result
            assert "type" in result
            assert result["type"] == "FeatureCollection"
            assert "features" in result
            
            # Save the result for inspection
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            with open(OUTPUT_DIR / "test_amenities.geojson", "w") as f:
                json.dump(result, f)
                
            print(f"Found {len(result['features'])} amenities")
            
        except Exception as e:
            pytest.fail(f"API call failed: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_invalid_geometry(self):
        """Test with invalid geometry should raise an error."""
        # Invalid geometry (Point instead of Polygon)
        geometry = {
            "type": "Point",
            "coordinates": [-73.985, 40.757]
        }
        
        params = {
            "fileName": "test_invalid",
            "outputType": "geojson"
        }
        
        with pytest.raises(Exception):
            await get_osm_data(geometry, **params)
