import os
import json
import subprocess
import shutil
import pytest
from pathlib import Path

TEST_DIR = Path("tests/test_data")
OUTPUT_DIR = TEST_DIR / "output"
FIXTURE_DIR = TEST_DIR / "fixtures"
KEEP_TEST_OUTPUTS = os.environ.get("KEEP_TEST_OUTPUTS", "0") == "1"

class TestCliIntegration:
    """Integration tests for the CLI interface."""

    @classmethod
    def setup_class(cls):
        """Set up test environment before all tests."""
        for directory in [TEST_DIR, OUTPUT_DIR, FIXTURE_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
        
        sample_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [-73.989, 40.754],
                            [-73.981, 40.754],
                            [-73.981, 40.759],
                            [-73.989, 40.759],
                            [-73.989, 40.754]
                        ]]
                    }
                }
            ]
        }
        
        with open(FIXTURE_DIR / "sample_area.geojson", "w") as f:
            json.dump(sample_geojson, f)

    @classmethod
    def teardown_class(cls):
        """Clean up test environment after all tests."""
        if OUTPUT_DIR.exists() and not KEEP_TEST_OUTPUTS:
            shutil.rmtree(OUTPUT_DIR)

    def test_cli_help(self):
            """Test the CLI help command."""
            result = subprocess.run(
                ["python", "-m", "osm_data_client.cli", "--help"],
                capture_output=True,
                text=True
            )
            
            # Verify help text contains expected options
            assert result.returncode == 0
            assert "--geojson" in result.stdout
            assert "--bbox" in result.stdout
            assert "--feature-type" in result.stdout
            
            assert "--no-zip" in result.stdout
            assert "--extract" in result.stdout
            assert "--token" in result.stdout
            assert "--api-url" in result.stdout
    
    def test_cli_version(self):
        """Test the CLI version command."""
        result = subprocess.run(
            ["python", "-m", "osm_data_client.cli", "--version"],
            capture_output=True,
            text=True
        )
        
        # Verify version is displayed
        assert result.returncode == 0
        assert "OSM Data Client version" in result.stdout
    
    def test_missing_required_args(self):
        """Test CLI with missing required arguments."""
        result = subprocess.run(
            ["python", "-m", "osm_data_client.cli"],
            capture_output=True,
            text=True
        )

        assert result.returncode != 0
        assert "--geojson" in result.stderr and "--bbox" in result.stderr

    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access"
    )
    def test_bbox_download(self):
        """Test downloading data for a bounding box."""
        output_file = OUTPUT_DIR / "bbox_test.geojson"

        # Use a very small bounding box to keep the test quick
        bbox = [-73.9851, 40.7572, -73.9850, 40.7573]  # Tiny area in NYC

        result = subprocess.run([
            "python", "-m", "osm_data_client.cli",
            "--bbox", str(bbox[0]), str(bbox[1]), str(bbox[2]), str(bbox[3]),
            "--feature-type", "building",
            "--out", str(output_file)
        ], capture_output=True, text=True)

        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")

        # Check if command succeeded
        assert result.returncode == 0
        assert "Downloaded OSM data saved to" in result.stdout

        # Verify output file exists
        assert output_file.exists()

    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access"
    )
    def test_geojson_download(self):
        """Test downloading data using a GeoJSON input file."""
        input_file = FIXTURE_DIR / "sample_area.geojson"
        output_file = OUTPUT_DIR / "geojson_test.geojson"

        result = subprocess.run([
            "python", "-m", "osm_data_client.cli",
            "--geojson", str(input_file),
            "--feature-type", "amenity",
            "--out", str(output_file)
        ], capture_output=True, text=True)

        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")

        assert result.returncode == 0
        assert "Downloaded OSM data saved to" in result.stdout
        assert output_file.exists()

    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access"
    )
    def test_extract_option(self):
        """Test the new --extract option."""
        output_file = OUTPUT_DIR / "extract_test.geojson"

        # Use a very small bounding box to keep the test quick
        bbox = [-73.9851, 40.7572, -73.9850, 40.7573]

        result = subprocess.run([
            "python", "-m", "osm_data_client.cli",
            "--bbox", str(bbox[0]), str(bbox[1]), str(bbox[2]), str(bbox[3]),
            "--feature-type", "building",
            "--out", str(output_file),
            "--extract"  # New option to test
        ], capture_output=True, text=True)

        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")

        assert result.returncode == 0
        assert "Downloaded OSM data saved to" in result.stdout
        assert output_file.exists()


    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access"
    )
    def test_no_zip_option(self):
        """Test the new --no-zip option."""
        output_file = OUTPUT_DIR / "no_zip_test.geojson"

        # Use a very small bounding box to keep the test quick
        bbox = [-73.9851, 40.7572, -73.9850, 40.7573]

        result = subprocess.run([
            "python", "-m", "osm_data_client.cli",
            "--bbox", str(bbox[0]), str(bbox[1]), str(bbox[2]), str(bbox[3]),
            "--feature-type", "building",
            "--out", str(output_file),
            "--no-zip"  # New option to test
        ], capture_output=True, text=True)

        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")

        assert result.returncode == 0
        assert "Downloaded OSM data saved to" in result.stdout
        assert output_file.exists()

    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access"
    )
    def test_different_formats_cli(self):
        """Test downloading data in different formats using the CLI."""
        output_file = OUTPUT_DIR / "format_test"
        
        # Use a very small bounding box to keep the test quick
        bbox = [-73.9851, 40.7572, -73.9850, 40.7573]

        result = subprocess.run([
            "python", "-m", "osm_data_client.cli",
            "--bbox", str(bbox[0]), str(bbox[1]), str(bbox[2]), str(bbox[3]),
            "--feature-type", "building",
            "--out", str(output_file),
            "--format", "csv"  # Test different format
        ], capture_output=True, text=True)

        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")

        assert result.returncode == 0
        assert "Downloaded OSM data saved to" in result.stdout
        
        # Check that the output exists (either as a file or directory)
        expected_file = Path(f"{output_file}.csv")
        expected_dir = Path(f"{output_file}_csv")
        assert expected_file.exists() or expected_dir.exists()


    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access"
    )
    def test_custom_api_url(self):
        """Test using a custom API URL."""
        output_file = OUTPUT_DIR / "custom_api_test.geojson"

        # Use a very small bounding box to keep the test quick
        bbox = [-73.9851, 40.7572, -73.9850, 40.7573]

        result = subprocess.run([
            "python", "-m", "osm_data_client.cli",
            "--bbox", str(bbox[0]), str(bbox[1]), str(bbox[2]), str(bbox[3]),
            "--feature-type", "building",
            "--out", str(output_file),
            "--api-url", "https://api-prod.raw-data.hotosm.org/v1"  # Use default URL explicitly
        ], capture_output=True, text=True)

        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")

        assert result.returncode == 0
        assert "Downloaded OSM data saved to" in result.stdout
        assert output_file.exists()
