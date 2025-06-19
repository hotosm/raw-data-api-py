import pytest
import os
import shutil
from pathlib import Path

from osm_data_client import (
    get_osm_data,
    RawDataClient,
    RawDataOutputOptions,
    AutoExtractOption,
    RawDataClientConfig,
)
from osm_data_client.exceptions import ValidationError

BASE_DIR = Path(__file__).parent
TEST_DIR = BASE_DIR / "test_data"
OUTPUT_DIR = TEST_DIR / "output"
KEEP_TEST_OUTPUTS = os.environ.get("KEEP_TEST_OUTPUTS", "0") == "1"

# Add marker to skip API tests when SKIP_API_TESTS env var is set
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_API_TESTS") == "1",
    reason="Skipping tests that require API access",
)


class TestAPIIntegration:
    """Integration tests for the API client."""

    @classmethod
    def setup_class(cls):
        """Set up test environment before all tests."""
        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Test output directory: {OUTPUT_DIR}")

    @classmethod
    def teardown_class(cls):
        """Clean up test environment after all tests."""
        if OUTPUT_DIR.exists() and not KEEP_TEST_OUTPUTS:
            print(f"Cleaning up test output directory: {OUTPUT_DIR}")
            shutil.rmtree(OUTPUT_DIR)

    @pytest.fixture
    def small_geometry(self):
        """Return a very small test geometry to speed up tests."""
        # Use a tiny area to make tests run faster
        return {
            "type": "Polygon",
            "coordinates": [
                [
                    [-73.9851, 40.7572],  # NYC tiny area
                    [-73.9850, 40.7572],
                    [-73.9850, 40.7573],
                    [-73.9851, 40.7573],
                    [-73.9851, 40.7572],
                ]
            ],
        }

    @pytest.fixture
    def cleanup_files(self):
        """Fixture to clean up files after each test."""
        # Store files created during test
        created_files = []

        yield created_files

        # Clean up after test
        for file_path in created_files:
            if file_path.exists():
                if file_path.is_dir():
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()

    @pytest.mark.asyncio
    async def test_basic_building_download(self, small_geometry, cleanup_files):
        """Test fetching building data using the simplified API."""
        params = {
            "fileName": "test_buildings",
            "outputType": "geojson",
            "filters": {"tags": {"all_geometry": {"building": []}}},
        }

        config = RawDataClientConfig(output_directory=OUTPUT_DIR)
        client = RawDataClient(config)

        try:
            result = await client.get_osm_data(small_geometry, **params)
            cleanup_files.append(result.path)

            assert result.exists(), f"Result file {result.path} does not exist"

            # Check if we got an actual file with content
            if result.path.is_file():
                file_size = result.path.stat().st_size
                assert file_size > 0, f"Result file {result.path} is empty (0 bytes)"
                print(f"Downloaded file size: {file_size} bytes")

        except Exception as e:
            pytest.fail(f"API call failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_auto_extract_options(self, small_geometry, cleanup_files):
        """Test the different auto-extract options."""
        # Test keeping as zip (force_zip)
        output_options = RawDataOutputOptions(auto_extract=AutoExtractOption.force_zip)

        params = {
            "fileName": "test_zip_option",
            "outputType": "geojson",
            "bindZip": True,
            "filters": {"tags": {"all_geometry": {"building": []}}},
        }

        config = RawDataClientConfig(output_directory=OUTPUT_DIR)
        client = RawDataClient(config)

        # Force ZIP test
        first_result = await client.get_osm_data(
            small_geometry, output_options, **params
        )
        cleanup_files.append(first_result.path)

        assert first_result.path.exists(), (
            f"Result file {first_result.path} does not exist"
        )
        assert first_result.path.suffix == ".zip", (
            f"Expected ZIP file, got {first_result.path.suffix}"
        )

        # Test forcing extraction (force_extract)
        output_options = RawDataOutputOptions(
            auto_extract=AutoExtractOption.force_extract
        )

        # Create a new file name to avoid conflicts
        params["fileName"] = "test_extract_option"

        second_result = await client.get_osm_data(
            small_geometry, output_options, **params
        )
        cleanup_files.append(second_result.path)

        assert second_result.path.exists(), (
            f"Result file {second_result.path} does not exist"
        )

        # Check if we got the expected file type (not a zip)
        if second_result.extracted:
            assert second_result.path.suffix != ".zip", (
                "Expected extracted file, got ZIP file"
            )

    @pytest.mark.asyncio
    async def test_different_formats(self, small_geometry, cleanup_files):
        """Test fetching data in different output formats."""
        formats_to_test = ["geojson", "csv"]  # Limited subset for speed

        for format_type in formats_to_test:
            params = {
                "fileName": f"test_format_{format_type}",
                "outputType": format_type,
                "filters": {"tags": {"all_geometry": {"building": []}}},
            }

            config = RawDataClientConfig(output_directory=OUTPUT_DIR)
            client = RawDataClient(config)

            result = await client.get_osm_data(small_geometry, **params)
            cleanup_files.append(result.path)

            # Verify the result exists with helpful messages
            assert result.path.exists(), (
                f"Result file for {format_type} format does not exist"
            )

            # Check file size to ensure we got actual content
            if result.path.is_file():
                file_size = result.path.stat().st_size
                assert file_size > 0, (
                    f"Result file for {format_type} format is empty (0 bytes)"
                )
                print(f"Downloaded {format_type} file size: {file_size} bytes")

    @pytest.mark.asyncio
    async def test_with_api_config(self, small_geometry, cleanup_files):
        """Test using a custom API config."""
        params = {
            "fileName": "test_api_config",
            "outputType": "geojson",
            "filters": {"tags": {"all_geometry": {"building": []}}},
        }

        config = RawDataClientConfig(
            base_api_url="https://api-prod.raw-data.hotosm.org/v1",
            output_directory=OUTPUT_DIR,
        )

        client = RawDataClient(config)

        result = await client.get_osm_data(small_geometry, **params)
        cleanup_files.append(result.path)

        # Verify the result exists with helpful messages
        assert result.path.exists(), f"Result file {result.path} does not exist"

        # Check file size
        if result.path.is_file():
            file_size = result.path.stat().st_size
            assert file_size > 0, "Result file is empty (0 bytes)"
            print(f"Downloaded file size: {file_size} bytes")

    @pytest.mark.asyncio
    async def test_validation_errors(self):
        """Test various validation errors."""
        # Test invalid geometry type
        invalid_geometry = {
            "type": "Point",  # Point is invalid, should be Polygon or MultiPolygon
            "coordinates": [-73.985, 40.757],
        }

        with pytest.raises(ValidationError, match="Geometry type") as excinfo:
            await get_osm_data(invalid_geometry, fileName="test_invalid")
        print(f"Validation error for invalid geometry: {str(excinfo.value)}")

        # Test invalid format
        valid_geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-73.9851, 40.7572],
                    [-73.9850, 40.7572],
                    [-73.9850, 40.7573],
                    [-73.9851, 40.7573],
                    [-73.9851, 40.7572],
                ]
            ],
        }

        with pytest.raises(ValidationError, match="outputType") as excinfo:
            await get_osm_data(
                valid_geometry, fileName="test_invalid", outputType="invalid_format"
            )
        print(f"Validation error for invalid format: {str(excinfo.value)}")
