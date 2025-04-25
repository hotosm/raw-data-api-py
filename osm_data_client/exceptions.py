"""
Exception classes for the OSM Data Client.

This module defines the exception hierarchy for error conditions that may occur
when interacting with the Raw Data API.
"""

class OSMClientError(Exception):
    """Base exception class for all OSM client errors."""
    pass

class ValidationError(OSMClientError):
    """
    Raised when input validation fails.
    
    This can occur when invalid geometry or request parameters are provided.
    """
    pass

class APIRequestError(OSMClientError):
    """
    Raised when an API request fails.
    
    This can occur due to network issues, invalid requests, or server errors.
    """
    def __init__(self, status_code, response_data, message=None):
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(message or f"API request failed with status {status_code}: {response_data}")

class TaskPollingError(OSMClientError):
    """
    Raised when polling a task status fails.
    
    This can occur if the task tracking endpoint returns an error or becomes unavailable during polling.
    """
    pass

class DownloadError(OSMClientError):
    """
    Raised when downloading data fails.
    
    This can occur due to network issues, insufficient disk space, or when the
    downloaded file is corrupted or in an unexpected format.
    """
    pass
