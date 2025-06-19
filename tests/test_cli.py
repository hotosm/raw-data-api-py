import os
import json
import subprocess
import shutil
import sys
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).parent
TEST_DIR = BASE_DIR / "test_data"
OUTPUT_DIR = TEST_DIR / "output"
FIXTURE_DIR = TEST_DIR / "fixtures"
KEEP_TEST_OUTPUTS = os.environ.get("KEEP_TEST_OUTPUTS", "0") == "1"

TINY_BBOX = [-73.9851, 40.7572, -73.9850, 40.7573]  # Very small area in NYC


class TestCliIntegration:
    """Integration tests for the CLI interface."""

    @classmethod
    def setup_class(cls):
        """Set up test environment before all tests."""
        # Create test directories
        for directory in [TEST_DIR, OUTPUT_DIR, FIXTURE_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {directory}")

        # Create sample GeoJSON for tests
        sample_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-73.9851, 40.7572],  # Using the tiny area
                                [-73.9850, 40.7572],
                                [-73.9850, 40.7573],
                                [-73.9851, 40.7573],
                                [-73.9851, 40.7572],
                            ]
                        ],
                    },
                }
            ],
        }

        sample_geojson_path = FIXTURE_DIR / "sample_area.geojson"
        with open(sample_geojson_path, "w") as f:
            json.dump(sample_geojson, f)

        print(f"Created sample GeoJSON: {sample_geojson_path}")

    @classmethod
    def teardown_class(cls):
        """Clean up test environment after all tests."""
        if OUTPUT_DIR.exists() and not KEEP_TEST_OUTPUTS:
            print(f"Cleaning up test output directory: {OUTPUT_DIR}")
            shutil.rmtree(OUTPUT_DIR)

    def run_cli_command(self, args, check=True):
        """Helper method to run CLI commands with improved error handling."""
        python_exe = sys.executable

        # Create the full command
        cmd = [python_exe, "-m", "osm_data_client.cli"] + args
        print(f"Running command: {' '.join(cmd)}")

        # Run the command
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Log output for debugging
        print(f"STDOUT: {result.stdout}")
        if result.stderr:
            print(f"STDERR: {result.stderr}")

        # Check result if needed
        if check and result.returncode != 0:
            pytest.fail(
                f"Command failed with exit code {result.returncode}: {result.stderr}"
            )

        return result

    def test_cli_version(self):
        """Test the CLI version command."""
        result = self.run_cli_command(["--version"])

        # Verify version is displayed
        assert "OSM Data Client version" in result.stdout

    def test_missing_required_args(self):
        """Test CLI with missing required arguments."""
        # This command should fail, so don't check the result
        result = self.run_cli_command([], check=False)

        assert result.returncode != 0
        assert "--geojson" in result.stderr and "--bounds" in result.stderr

    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access",
    )
    def test_bounds_download(self):
        """Test downloading data for a bounding box."""
        output_file = OUTPUT_DIR / "bbox_test.geojson"

        # Remove output file if it already exists
        if output_file.exists():
            output_file.unlink()

        result = self.run_cli_command(
            [
                "--bounds",
                str(TINY_BBOX[0]),
                str(TINY_BBOX[1]),
                str(TINY_BBOX[2]),
                str(TINY_BBOX[3]),
                "--feature-type",
                "building",
                "--out",
                str(output_file),
            ]
        )

        # Check if command succeeded
        assert "Downloaded OSM data saved to" in result.stdout

        # Verify output file exists and has content
        assert output_file.exists(), f"Output file {output_file} does not exist"
        file_size = output_file.stat().st_size
        assert file_size > 0, f"Output file {output_file} is empty (0 bytes)"
        print(f"Downloaded file size: {file_size} bytes")

    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access",
    )
    def test_geojson_download(self):
        """Test downloading data using a GeoJSON input file."""
        input_file = FIXTURE_DIR / "sample_area.geojson"
        output_file = OUTPUT_DIR / "geojson_test.geojson"

        # Remove output file if it already exists
        if output_file.exists():
            output_file.unlink()

        result = self.run_cli_command(
            [
                "--geojson",
                str(input_file),
                "--feature-type",
                "building",  # Changed from "amenity" to "building" for consistency
                "--out",
                str(output_file),
            ]
        )

        # Check if command succeeded
        assert "Downloaded OSM data saved to" in result.stdout

        # Verify output file exists and has content
        assert output_file.exists(), f"Output file {output_file} does not exist"
        file_size = output_file.stat().st_size
        assert file_size > 0, f"Output file {output_file} is empty (0 bytes)"
        print(f"Downloaded file size: {file_size} bytes")

    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access",
    )
    def test_extract_option(self):
        """Test the --extract option."""
        output_file = OUTPUT_DIR / "extract_test.geojson"

        # Remove output file if it already exists
        if output_file.exists():
            output_file.unlink()

        result = self.run_cli_command(
            [
                "--bounds",
                str(TINY_BBOX[0]),
                str(TINY_BBOX[1]),
                str(TINY_BBOX[2]),
                str(TINY_BBOX[3]),
                "--feature-type",
                "building",
                "--out",
                str(output_file),
                "--extract",  # Force extraction
            ]
        )

        # Check if command succeeded
        assert "Downloaded OSM data saved to" in result.stdout

        # Check file existence and size
        output_path = None

        if output_file.exists():
            output_path = output_file
        elif output_file.with_suffix(".zip").exists():
            output_path = output_file.with_suffix(".zip")

        assert output_path is not None, (
            f"Neither {output_file} nor {output_file.with_suffix('.zip')} exist"
        )
        file_size = output_path.stat().st_size
        assert file_size > 0, f"Output file {output_path} is empty (0 bytes)"
        print(f"Downloaded file size: {file_size} bytes")

    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access",
    )
    def test_no_zip_option(self):
        """Test the --no-zip option."""
        output_file = OUTPUT_DIR / "no_zip_test.geojson"

        # Remove output file if it already exists
        if output_file.exists():
            output_file.unlink()

        result = self.run_cli_command(
            [
                "--bounds",
                str(TINY_BBOX[0]),
                str(TINY_BBOX[1]),
                str(TINY_BBOX[2]),
                str(TINY_BBOX[3]),
                "--feature-type",
                "building",
                "--out",
                str(output_file),
                "--no-zip",  # Request unzipped data
            ]
        )

        # Check if command succeeded
        assert "Downloaded OSM data saved to" in result.stdout

        # Verify output file exists and has content
        assert output_file.exists(), f"Output file {output_file} does not exist"
        file_size = output_file.stat().st_size
        assert file_size > 0, f"Output file {output_file} is empty (0 bytes)"
        print(f"Downloaded file size: {file_size} bytes")

    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access",
    )
    def test_different_formats_cli(self):
        """Test downloading data in different formats using the CLI."""
        output_file = OUTPUT_DIR / "format_test"

        # Remove output files if they already exist
        for ext in [".csv", ".zip"]:
            if output_file.with_suffix(ext).exists():
                output_file.with_suffix(ext).unlink()

        # Remove directory if it exists
        csv_dir = Path(f"{output_file}_csv")
        if csv_dir.exists() and csv_dir.is_dir():
            shutil.rmtree(csv_dir)

        result = self.run_cli_command(
            [
                "--bounds",
                str(TINY_BBOX[0]),
                str(TINY_BBOX[1]),
                str(TINY_BBOX[2]),
                str(TINY_BBOX[3]),
                "--feature-type",
                "building",
                "--out",
                str(output_file),
                "--format",
                "csv",  # Test CSV format
            ]
        )

        # Check if command succeeded
        assert "Downloaded OSM data saved to" in result.stdout

        # Check that some output exists (either as a file or directory)
        expected_file = output_file.with_suffix(".csv")
        expected_zip = output_file.with_suffix(".zip")
        expected_dir = Path(f"{output_file}_csv")

        outputs_exist = any(
            [expected_file.exists(), expected_zip.exists(), expected_dir.exists()]
        )

        assert outputs_exist, (
            f"No output found at {expected_file}, {expected_zip}, or {expected_dir}"
        )

        # Check file content if it exists
        for path in [expected_file, expected_zip]:
            if path.exists() and path.is_file():
                file_size = path.stat().st_size
                assert file_size > 0, f"Output file {path} is empty (0 bytes)"
                print(f"Downloaded file size: {file_size} bytes")

    @pytest.mark.skipif(
        os.environ.get("SKIP_API_TESTS") == "1",
        reason="Skipping tests that require API access",
    )
    def test_custom_api_url(self):
        """Test using a custom API URL."""
        output_file = OUTPUT_DIR / "custom_api_test.geojson"

        # Remove output file if it already exists
        if output_file.exists():
            output_file.unlink()

        result = self.run_cli_command(
            [
                "--bounds",
                str(TINY_BBOX[0]),
                str(TINY_BBOX[1]),
                str(TINY_BBOX[2]),
                str(TINY_BBOX[3]),
                "--feature-type",
                "building",
                "--out",
                str(output_file),
                "--api-url",
                "https://api-prod.raw-data.hotosm.org/v1",  # Explicit API URL
            ]
        )

        # Check if command succeeded
        assert "Downloaded OSM data saved to" in result.stdout

        # Verify output file exists and has content
        assert output_file.exists(), f"Output file {output_file} does not exist"
        file_size = output_file.stat().st_size
        assert file_size > 0, f"Output file {output_file} is empty (0 bytes)"
        print(f"Downloaded file size: {file_size} bytes")
