from typing import Dict, Any, Union, Optional, List, Tuple
import asyncio
import json
import io
import zipfile
from aiohttp import ClientSession, ClientResponseError

from .exceptions import APIRequestError, TaskPollingError, DownloadError
from .models import GeometryInput, RequestParams

class RawDataAPI:
    """Client for the HOTOSM Raw Data API."""

    def __init__(self, base_api_url: str = "https://api-prod.raw-data.hotosm.org/v1"):
        """
        Initialize the API client.
        
        Args:
            base_api_url: Base URL for the Raw Data API
        """
        self.base_api_url = base_api_url
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Referer": "osm-data-client-python",
        }

    async def request_snapshot(self, geometry: GeometryInput, params: RequestParams) -> Dict[str, Any]:
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

        async with ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_api_url}/snapshot/",
                    data=json.dumps(payload),
                    headers=self.headers,
                ) as response:
                    response_data = await response.json()
                    if response.status >= 400:
                        raise APIRequestError(response.status, response_data)
                    return response_data
            except ClientResponseError as ex:
                raise APIRequestError(ex.status, {}, str(ex)) from ex
            except Exception as ex:
                raise APIRequestError(0, {}, str(ex)) from ex

    async def poll_task_status(self, task_link: str, polling_interval: int = 2) -> Dict[str, Any]:
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
        async with ClientSession() as session:
            while True:
                try:
                    async with session.get(
                        url=f"{self.base_api_url}{task_link}", headers=self.headers
                    ) as response:
                        if response.status >= 400:
                            response_data = await response.json()
                            raise TaskPollingError(f"Polling failed with status {response.status}: {response_data}")
                        
                        result = await response.json()
                        if result["status"] in ["SUCCESS", "FAILED"]:
                            return result
                        await asyncio.sleep(polling_interval)
                except TaskPollingError:
                    raise
                except Exception as ex:
                    raise TaskPollingError(f"Error polling task status: {str(ex)}") from ex

    async def download_snapshot(self, download_url: str, file_name: str) -> Union[Dict[str, Any], List[Dict[str, Any]], Dict[str, Union[str, bytes]]]:
        """
        Download and extract the snapshot data.
        
        Args:
            download_url: URL to download the data
            file_name: Name for the downloaded file
            
        Returns:
            Parsed data (GeoJSON, CSV, or binary)
            
        Raises:
            DownloadError: If downloading or extracting fails
        """
        async with ClientSession() as session:
            try:
                async with session.get(url=download_url, headers=self.headers) as response:
                    if response.status >= 400:
                        response_text = await response.text()
                        raise DownloadError(f"Download failed with status {response.status}: {response_text}")
                    
                    data = await response.read()
                    return self._extract_zip_data(data, file_name)
            except DownloadError:
                raise
            except Exception as ex:
                raise DownloadError(f"Error downloading snapshot: {str(ex)}") from ex
    
    def _extract_zip_data(self, zip_data: bytes, file_name: str) -> Union[Dict[str, Any], List[Dict[str, Any]], Dict[str, Union[str, bytes]]]:
        """
        Extract and parse data from a zip archive.
        
        Args:
            zip_data: Binary zip data
            
        Returns:
            Parsed data from the archive
            
        Raises:
            DownloadError: If extraction fails
        """
        try:
            with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zip_ref:
                all_files = zip_ref.namelist()
                
                if len(all_files) < 2:
                    raise DownloadError(f"Expected at least 2 files in the archive, found {len(all_files)}")
                
                data_file = all_files[1]
                for f in all_files:
                    if file_name in f:
                        data_file = f
                        break

                with zip_ref.open(data_file) as file:
                    # Determine format based on file extension
                    if data_file.endswith('.geojson'):
                        return json.load(file)
                    elif data_file.endswith('.csv'):
                        import csv
                        from io import TextIOWrapper
                        csv_reader = csv.DictReader(TextIOWrapper(file, 'utf-8'))
                        return list(csv_reader)
                    else:
                        # For binary formats, return the binary data
                        return {
                            "format": data_file.split('.')[-1],
                            "data": file.read(),
                            "file_name": data_file
                        }
        except zipfile.BadZipFile as ex:
            raise DownloadError(f"Invalid zip file: {str(ex)}") from ex
        except Exception as ex:
            raise DownloadError(f"Error extracting data: {str(ex)}") from ex

async def get_osm_data(
    geometry: Union[Dict[str, Any], str], 
    **kwargs
) -> Dict[str, Any]:
    """
    Get OSM data for a specified area.
    
    Args:
        geometry: GeoJSON geometry object or string
        **kwargs: Additional parameters for customizing the request
            - fileName: Name for the export file (default: "osm_export")
            - outputType: Format of the output (default: "geojson")
            - filters: Dictionary of filters to apply
            - geometryType: List of geometry types to include
    
    Returns:
        GeoJSON data for the requested area
    
    Raises:
        ValidationError: If inputs are invalid
        APIRequestError: If the API request fails
        TaskPollingError: If polling the task status fails
        DownloadError: If downloading data fails
    
    Examples:
        >>> data = await get_osm_data(
        ...     {"type": "Polygon", "coordinates": [...]},
        ...     fileName="my_buildings",
        ...     outputType="geojson",
        ...     filters={"tags": {"all_geometry": {"building": []}}}
        ... )
    """
    # Validate inputs
    geometry_input = GeometryInput.from_input(geometry)
    params = RequestParams.from_kwargs(**kwargs)
    
    # Initialize API client
    api = RawDataAPI()
    
    # Request snapshot
    task_response = await api.request_snapshot(geometry_input, params)
    
    # Get task link for polling
    task_link = task_response.get("track_link")
    if not task_link:
        raise TaskPollingError("No task link found in API response")
    
    # Poll for task completion
    result = await api.poll_task_status(task_link)
    
    # Check for success and download
    if result["status"] == "SUCCESS" and result["result"].get("download_url"):
        download_url = result["result"]["download_url"]
        return await api.download_snapshot(download_url, params.file_name)
    
    # Handle failure
    error_msg = f"Task failed with status: {result['status']}"
    if result.get("result", {}).get("error_msg"):
        error_msg += f" - {result['result']['error_msg']}"
    raise DownloadError(error_msg)
