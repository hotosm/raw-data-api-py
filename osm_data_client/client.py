import logging
import asyncio
import json
from typing import Dict, Any, Union, Optional
from aiohttp import ClientSession, ClientResponseError

from .models import (
    GeometryInput,
    RequestParams,
    RawDataApiMetadata,
    RawDataOutputOptions,
    RawDataClientConfig,
)
from .exceptions import APIRequestError, TaskPollingError, DownloadError
from .processing import OutputProcessor, RawDataResult


log = logging.getLogger(__name__)


class RawDataAPI:
    """Client for the HOTOSM Raw Data API."""

    def __init__(self, config: RawDataClientConfig = RawDataClientConfig.default()):
        """
        Initialize the API client.

        Args:
            config: Configuration for the client
        """
        self.config = config
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Referer": "raw-data-client-py",
        }

        if config.access_token:
            self.headers["Authorization"] = f"Bearer {config.access_token}"
            log.debug("Using access token for authentication")

    async def request_snapshot(
        self, geometry: GeometryInput, params: RequestParams
    ) -> Dict[str, Any]:
        """
        Request a snapshot of OSM data.

        Args:
            geometry: Validated GeoJSON geometry object
            params: Validated request parameters

        Returns:
            API response with task tracking information

        Raises:
            APIRequestError: If the API request fails
        """
        payload = {
            **params.to_api_params(),
            "geometry": geometry.to_dict(),
        }

        log.debug("Requesting snapshot with params: %s", json.dumps(payload))

        async with ClientSession() as session:
            try:
                async with session.post(
                    f"{self.config.base_api_url}/snapshot/",
                    data=json.dumps(payload),
                    headers=self.headers,
                ) as response:
                    response_data = await response.json()
                    if response.status >= 400:
                        log.error(
                            "API request failed with status %d: %s",
                            response.status,
                            response_data,
                        )
                        raise APIRequestError(response.status, response_data)

                    # Log queue information if available
                    if "queue" in response_data:
                        queue_position = response_data.get("queue", 0)
                        if queue_position > 0:
                            log.info("Request queued at position %d", queue_position)

                    log.debug("Snapshot request successful: %s", response_data)
                    return response_data
            except ClientResponseError as ex:
                log.error("API client error: %s", str(ex))
                raise APIRequestError(ex.status, {}, str(ex)) from ex
            except Exception as ex:
                log.error("Unexpected error in API request: %s", str(ex))
                raise APIRequestError(0, {}, str(ex)) from ex

    async def poll_task_status(
        self, task_link: str, polling_interval: int = 2
    ) -> Dict[str, Any]:
        """
        Poll the API to check task status until completion.

        Args:
            task_link: Task tracking URL
            polling_interval: Seconds between polling attempts

        Returns:
            Task status details

        Raises:
            TaskPollingError: If polling fails
        """
        log.info("Starting task polling: %s", task_link)

        # Track previous status to log changes
        previous_status = None

        async with ClientSession() as session:
            while True:
                try:
                    async with session.get(
                        url=f"{self.config.base_api_url}{task_link}",
                        headers=self.headers,
                    ) as response:
                        if response.status >= 400:
                            response_data = await response.json()
                            log.error(
                                "Polling failed with status %d: %s",
                                response.status,
                                response_data,
                            )
                            raise TaskPollingError(
                                f"Polling failed with status {response.status}: {response_data}"
                            )

                        result = await response.json()
                        current_status = result.get("status")

                        # Log status changes
                        if current_status != previous_status:
                            log.info("Task status: %s", current_status)
                            previous_status = current_status

                        if current_status in ["SUCCESS", "FAILED"]:
                            if current_status == "FAILED":
                                error_msg = result.get("result", {}).get(
                                    "error_msg", "Unknown error"
                                )
                                log.error("Task failed: %s", error_msg)
                            else:
                                log.info("Task completed successfully")
                            return result

                        log.debug(
                            "Task still processing, waiting %d seconds",
                            polling_interval,
                        )
                        await asyncio.sleep(polling_interval)
                except TaskPollingError:
                    raise
                except Exception as ex:
                    log.error("Error polling task status: %s", str(ex))
                    raise TaskPollingError(
                        f"Error polling task status: {str(ex)}"
                    ) from ex

    async def download_to_disk(
        self,
        data: RawDataApiMetadata,
        options: RawDataOutputOptions = RawDataOutputOptions.default(),
    ) -> RawDataResult:
        """
        Stream data from API to disk

        Args:
            data: Metadata containing download information
            options: Options for controlling extraction behavior

        Returns:
            RawDataResult with information about the downloaded file

        Raises:
            DownloadError: If downloading or processing fails
        """
        processor = OutputProcessor(self.config, options)
        file_path = processor.get_output_path(data)

        file_path.parent.mkdir(parents=True, exist_ok=True)
        log.info("Downloading data to %s (%s bytes)", file_path, data.size_bytes)

        try:
            async with ClientSession() as session:
                async with session.get(
                    data.download_url, headers=self.headers
                ) as response:
                    if response.status >= 400:
                        log.error("Download failed with status %d", response.status)
                        raise DownloadError(
                            f"Download failed with status {response.status}"
                        )

                    with open(file_path, "wb") as f:
                        log.debug("Streaming file contents using 1MB chunks")
                        downloaded_bytes = 0
                        async for chunk in response.content.iter_chunked(
                            1024 * 1024
                        ):  # 1MB chunks
                            f.write(chunk)
                            downloaded_bytes += len(chunk)
                            if (
                                data.size_bytes > 10 * 1024 * 1024
                                and downloaded_bytes % (10 * 1024 * 1024) == 0
                            ):
                                progress = (downloaded_bytes / data.size_bytes) * 100
                                log.info(
                                    "Download progress: %.1f%% (%d/%d bytes)",
                                    progress,
                                    downloaded_bytes,
                                    data.size_bytes,
                                )

                    log.info("Download complete: %s", file_path)

                    return await processor.process_download(file_path, data)

        except Exception as ex:
            log.error("Error downloading data: %s", str(ex))
            raise DownloadError(f"Error downloading data: {str(ex)}") from ex


class RawDataClient:
    """
    Client for fetching OSM data via the HOTOSM Raw Data API.

    This client provides a high-level interface for requesting and downloading
    OpenStreetMap data for a specified area with customizable filters.
    """

    def __init__(self, config: RawDataClientConfig = RawDataClientConfig.default()):
        """
        Initialize the client.

        Args:
            config: Configuration for the client
        """
        self.config = config
        self.api = RawDataAPI(config)

    async def get_osm_data(
        self,
        geometry: Union[Dict[str, Any], str],
        output_options: RawDataOutputOptions = RawDataOutputOptions.default(),
        **kwargs,
    ) -> RawDataResult:
        """
        Get OSM data for a specified area.

        Args:
            geometry: GeoJSON geometry object or string
            output_options: Options for controlling output behavior
            **kwargs: Additional parameters for customizing the request
                - fileName: Name for the export file (default: "osm_export")
                - outputType: Format of the output (default: "geojson")
                - bindZip: Whether to retrieve results as a zip file (default: False)
                - filters: Dictionary of filters to apply
                - geometryType: List of geometry types to include

        Returns:
            Path to the downloaded data file or directory

        Raises:
            ValidationError: If inputs are invalid
            APIRequestError: If the API request fails
            TaskPollingError: If polling the task status fails
            DownloadError: If downloading data fails

        Examples:
            >>> data_path = await get_osm_data(
            ...     {"type": "Polygon", "coordinates": [...]},
            ...     fileName="my_buildings",
            ...     outputType="geojson",
            ...     filters={"tags": {"all_geometry": {"building": []}}}
            ... )
        """
        # Validate inputs
        geometry_input = GeometryInput.from_input(geometry)
        params = RequestParams.from_kwargs(**kwargs)

        # Request snapshot
        log.info("Requesting OSM data snapshot for %s", params.file_name)
        task_response = await self.api.request_snapshot(geometry_input, params)

        # Get task link for polling
        task_link = task_response.get("track_link")
        if not task_link:
            raise TaskPollingError("No task link found in API response")

        # Poll for task completion
        result = await self.api.poll_task_status(task_link)

        if result["status"] != "SUCCESS":
            # Handle failure
            error_msg = f"Task failed with status: {result['status']}"
            if result.get("result", {}).get("error_msg"):
                error_msg += f" - {result['result']['error_msg']}"
            raise DownloadError(error_msg)

        # Create metadata from the result
        metadata = RawDataApiMetadata.from_api_result(result, params)
        log.debug("Data metadata: %s", metadata)

        # Avoid downloading
        if self.config.stream:
            return result.get("result")

        # Download the data
        return await self.api.download_to_disk(metadata, output_options)


async def get_osm_data(geometry: dict[str, Any] | str, **kwargs) -> RawDataResult:
    """
    Get OSM data for a specified area.

    This is a convenience wrapper around RawDataClient.get_osm_data.

    Args:
        geometry: GeoJSON geometry object or string
        **kwargs: Additional parameters for customizing the request
            - fileName: Name for the export file (default: "osm_export")
            - outputType: Format of the output (default: "geojson")
            - bindZip: Whether to retrieve results as a zip file (default: False)
            - filters: Dictionary of filters to apply
            - geometryType: List of geometry types to include
            - stream: Boolean whether to stream data url or not (default: False)

    Returns:
        Path to the downloaded data file or directory

    Raises:
        ValidationError: If inputs are invalid
        APIRequestError: If the API request fails
        TaskPollingError: If polling the task status fails
        DownloadError: If downloading data fails
    """
    config = RawDataClientConfig.default()

    if (stream := kwargs.pop("stream", False)):
        config.stream = stream

    client = RawDataClient(config=config)
    return await client.get_osm_data(geometry, **kwargs)
