import pytest
import os
import shutil
from pathlib import Path

from osm_data_client import (
    get_osm_data, RawDataClient, RawDataOutputOptions, 
    AutoExtractOption, RawDataClientConfig
)
from osm_data_client.exceptions import ValidationError

TEST_DIR = Path("tests/test_data")
OUTPUT_DIR = TEST_DIR / "output"
KEEP_TEST_OUTPUTS = os.environ.get("KEEP_TEST_OUTPUTS", "0") == "1"

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_API_TESTS") == "1",
    reason="Skipping tests that require API access"
)

class TestAPIIntegration:
    """Integration tests for the API client."""

    @classmethod
    def setup_class(cls):
        """Set up test environment before all tests."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def teardown_class(cls):
        """Clean up test environment after all tests."""
        if OUTPUT_DIR.exists() and not KEEP_TEST_OUTPUTS:
            shutil.rmtree(OUTPUT_DIR)

    @pytest.fixture
    def small_geometry(self):
        """Return a very small test geometry to speed up tests."""
        return {
            "type": "Polygon",
            "coordinates": [[
                [-73.9851, 40.7572],
                [-73.9850, 40.7572],
                [-73.9850, 40.7573],
                [-73.9851, 40.7573],
                [-73.9851, 40.7572]
            ]]
        }
    
    @pytest.mark.asyncio
    async def test_basic_building_download(self, small_geometry):
        """Test fetching building data using the simplified API."""
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
            config = RawDataClientConfig(
                output_directory=OUTPUT_DIR
            )

            client = RawDataClient(config)
            result = await client.get_osm_data(small_geometry, **params)
            
            assert result.exists()
            
            if result.exists():
                if result.is_dir():
                    import shutil
                    shutil.rmtree(result)
                else:
                    result.unlink()
                    
        except Exception as e:
            pytest.fail(f"API call failed: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_auto_extract_options(self, small_geometry):
        """Test the different auto-extract options."""
        # Test keeping as zip (force_zip)
        output_options = RawDataOutputOptions(auto_extract=AutoExtractOption.force_zip)
        
        params = {
            "fileName": "test_zip_option",
            "outputType": "geojson",
            "bindZip": True,
            "filters": {
                "tags": {
                    "all_geometry": {
                        "building": []
                    }
                }
            }
        }
        
        config = RawDataClientConfig(
            output_directory=OUTPUT_DIR
        )

        client = RawDataClient(config)
        first_result = await client.get_osm_data(small_geometry, output_options, **params)
        
        # Should be a zip file
        assert first_result.suffix == '.zip'
        assert first_result.exists()
        
        # Test forcing extraction (force_extract)
        output_options = RawDataOutputOptions(auto_extract=AutoExtractOption.force_extract)
        
        second_result = await client.get_osm_data(small_geometry, output_options, **params)
        
        # Should be extracted despite bindZip=True
        assert not second_result.suffix == '.zip'
        assert second_result.exists()
        
    @pytest.mark.asyncio
    async def test_different_formats(self, small_geometry):
        """Test fetching data in different output formats."""
        formats_to_test = ["geojson", "csv"]  # Limited subset 
        
        for format_type in formats_to_test:
            params = {
                "fileName": f"test_format_{format_type}",
                "outputType": format_type,
                "filters": {
                    "tags": {
                        "all_geometry": {
                            "building": []
                        }
                    }
                }
            }
            
            config = RawDataClientConfig(
                output_directory=OUTPUT_DIR
            )
            client = RawDataClient(config)
            
            result = await client.get_osm_data(small_geometry, **params)
            
            # Verify the result exists
            assert result.exists()

    @pytest.mark.asyncio
    async def test_with_api_config(self, small_geometry):
        """Test using a custom API config."""
        
        params = {
            "fileName": "test_api_config",
            "outputType": "geojson",
            "filters": {
                "tags": {
                    "all_geometry": {
                        "building": []
                    }
                }
            }
        }
        
        config = RawDataClientConfig(
            base_api_url="https://api-prod.raw-data.hotosm.org/v1",
            output_directory=OUTPUT_DIR
        )

        client = RawDataClient(config)
        
        result = await client.get_osm_data(small_geometry, **params)
        
        # Verify the result exists
        assert result.exists()
        
    @pytest.mark.asyncio
    async def test_validation_errors(self):
        """Test various validation errors."""
        # Test invalid geometry type
        invalid_geometry = {
            "type": "Point",
            "coordinates": [-73.985, 40.757]
        }
        
        with pytest.raises(ValidationError):
            await get_osm_data(invalid_geometry, fileName="test_invalid")
        
        # Test invalid format
        valid_geometry = {
            "type": "Polygon",
            "coordinates": [[
                [-73.9851, 40.7572],
                [-73.9850, 40.7572],
                [-73.9850, 40.7573],
                [-73.9851, 40.7573],
                [-73.9851, 40.7572]
            ]]
        }
        
        with pytest.raises(ValidationError):
            await get_osm_data(valid_geometry, fileName="test_invalid", outputType="invalid_format")
