class OSMClientError(Exception):
    """Base exception class for all OSM client errors."""
    pass

class ValidationError(OSMClientError):
    """Raised when input validation fails."""
    pass

class APIRequestError(OSMClientError):
    """Raised when an API request fails."""
    def __init__(self, status_code, response_data, message=None):
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(message or f"API request failed with status {status_code}: {response_data}")

class TaskPollingError(OSMClientError):
    """Raised when polling a task status fails."""
    pass

class DownloadError(OSMClientError):
    """Raised when downloading data fails."""
    pass
