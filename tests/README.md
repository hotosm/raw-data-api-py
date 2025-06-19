# Integration Tests for OSM Data Client

This directory contains integration tests for the OSM Data Client.
These tests verify that the client works correctly with the actual
API and file system.

## Running the Tests

### Basic Usage

Run all integration tests:

```bash
python tests/run_tests.py
```

### Skipping API Tests

If you want to skip tests that make actual API calls:

```bash
SKIP_API_TESTS=1 python tests/run_tests.py
```

### Running Specific Tests

To run specific tests, use the `TEST_PATTERN` environment variable:

```bash
# Run only CLI help test
TEST_PATTERN="test_cli.py::TestCliIntegration::test_cli_help" python tests/run_tests.py

# Run all CLI tests
TEST_PATTERN="test_cli.py" python tests/run_tests.py
```

## Test Data

The tests create a directory structure at `tests/test_data` with:

- `fixtures/`: Input files for tests
- `output/`: Output files generated during tests

The test fixtures include sample GeoJSON files for testing the
client with predefined geometries.

## Test Environment Cleanup

The tests clean up after themselves by removing the output
directory when they're done.
