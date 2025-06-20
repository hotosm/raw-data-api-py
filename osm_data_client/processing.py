from dataclasses import dataclass
from pathlib import Path
import logging
import zipfile
import json
from typing import Optional

from .models import RawDataApiMetadata, AutoExtractOption, RawDataOutputOptions
from .exceptions import DownloadError

log = logging.getLogger(__name__)


@dataclass
class RawDataResult:
    """
    Result object containing processed file path and associated metadata.

    Attributes:
        path: Path to the final processed file or directory
        metadata: Original metadata from the API response
        extracted: Whether the file was extracted from an archive
        original_path: Path to the original downloaded file (if different from path)
        extracted_files: List of files that were extracted (if applicable)
    """

    path: Path
    metadata: RawDataApiMetadata
    extracted: bool = False
    original_path: Optional[Path] = None
    extracted_files: Optional[list[Path]] = None

    def exists(self) -> bool:
        """Check if the result file or directory exists."""
        return self.path.exists()

    def __str__(self) -> str:
        """Return string representation of the result."""
        return str(self.path)


class OutputProcessor:
    """
    Handles all output file processing including extraction decisions.

    This class encapsulates the logic for determining how to process downloaded
    files, whether to extract them from archives, and how to organize the
    extracted contents based on file size and format.
    """

    def __init__(self, config, options=None):
        """
        Initialize the OutputProcessor.

        Args:
            config: Configuration containing output directory and memory threshold
            options: Options for controlling extraction behavior
        """
        self.config = config
        self.options = options or RawDataOutputOptions.default()

    def get_output_path(self, metadata: RawDataApiMetadata) -> Path:
        """
        Determine the appropriate output path based on metadata.

        Args:
            metadata: Data metadata from API response

        Returns:
            Path where the file should be saved
        """
        if metadata.is_zipped:
            return self.config.output_directory / f"{metadata.file_name}.zip"
        else:
            return (
                self.config.output_directory
                / f"{metadata.file_name}.{metadata.format_ext}"
            )

    def should_extract(self, metadata: RawDataApiMetadata) -> bool:
        """
        Determine if extraction should occur based on format and options.

        Args:
            metadata: Data metadata from API response

        Returns:
            Boolean indicating if extraction should be performed
        """
        if not metadata.is_zipped:
            return False

        if self.options.auto_extract == AutoExtractOption.force_extract:
            return True
        elif self.options.auto_extract == AutoExtractOption.force_zip:
            return False

        # Format-specific extraction policies
        format_defaults = {
            "shp": False,  # Multiple files, keep zipped
            "pgdump": False,  # Large, specialized format
            "kml": True,  # Single file, extract
            "mbtiles": True,  # Single file, extract
            "flatgeobuf": True,
            "csv": True,
            "geopackage": True,
            "geojson": True,
        }

        return format_defaults.get(metadata.format_ext.lower(), True)

    async def process_download(
        self, file_path: Path, metadata: RawDataApiMetadata
    ) -> RawDataResult:
        """
        Process a downloaded file according to configured options.

        Args:
            file_path: Path to the downloaded file
            metadata: Data metadata from API response

        Returns:
            RawDataResult with processed file information

        Raises:
            DownloadError: If processing fails
        """
        if not self.should_extract(metadata):
            return RawDataResult(path=file_path, metadata=metadata, extracted=False)

        try:
            log.info("Extracting downloaded zip file")
            extract_result = await self._extract_archive(file_path, metadata)
            return extract_result
        except Exception as ex:
            log.warning("Could not extract zip file: %s - Keeping zip", str(ex))
            return RawDataResult(path=file_path, metadata=metadata, extracted=False)

    async def _extract_archive(
        self, zip_path: Path, metadata: RawDataApiMetadata
    ) -> RawDataResult:
        """
        Extract contents based on file size.

        Args:
            zip_path: Path to the zip file
            metadata: Data metadata

        Returns:
            RawDataResult with extraction information

        Raises:
            DownloadError: If extraction fails
        """
        if metadata.size_bytes <= self.config.memory_threshold_bytes:
            # Standard extraction for small files - fast and direct
            log.debug(
                "Using standard zipfile extraction (file size: %sMB, threshold: %sMB)",
                metadata.size_bytes // (1024 * 1024),
                self.config.memory_threshold_mb,
            )
            return await self._extract_with_zipfile(zip_path, metadata)
        else:
            # Stream extraction for large files - memory efficient
            log.debug(
                "Using stream-unzip for memory-efficient extraction (file size: %sMB, threshold: %sMB)",
                metadata.size_bytes // (1024 * 1024),
                self.config.memory_threshold_mb,
            )
            return await self._extract_with_stream_unzip(zip_path, metadata)

    async def _extract_with_zipfile(
        self, zip_path: Path, metadata: RawDataApiMetadata
    ) -> RawDataResult:
        """
        Extract using Python's standard zipfile module.

        Args:
            zip_path: Path to the zip file
            metadata: Data metadata

        Returns:
            RawDataResult with extraction information

        Raises:
            DownloadError: If extraction fails
        """
        output_directory = zip_path.parent
        extracted_files = []
        main_file_path = None

        try:
            # For shapefile extraction, create a dedicated directory
            if metadata.format_ext.lower() == "shp":
                extract_dir = output_directory / f"{metadata.file_name}_shp"
                extract_dir.mkdir(parents=True, exist_ok=True)

                with zipfile.ZipFile(str(zip_path), "r") as zip_ref:
                    file_list = zip_ref.namelist()
                    zip_ref.extractall(str(extract_dir))
                    extracted_files = [extract_dir / name for name in file_list]

                log.info("Extracted shapefile components to %s", extract_dir)
                return RawDataResult(
                    path=extract_dir,
                    metadata=metadata,
                    extracted=True,
                    original_path=zip_path,
                    extracted_files=extracted_files,
                )

            # For single-file formats, extract directly
            with zipfile.ZipFile(str(zip_path), "r") as zip_ref:
                file_list = zip_ref.namelist()
                log.debug("Zip contains: %s", file_list)

                # Find the main data file by extension
                target_ext = f".{metadata.format_ext.lower()}"
                main_files = [f for f in file_list if f.lower().endswith(target_ext)]

                if not main_files:
                    log.error("No %s file found in zip", metadata.format_ext)
                    raise DownloadError(
                        f"No {metadata.format_ext} file found in zip archive"
                    )

                # Extract the main file
                main_file = main_files[0]
                main_file_path = Path(zip_ref.extract(main_file, str(output_directory)))
                extracted_files.append(main_file_path)
                log.info("Extracted %s from zip", main_file)

                # Extract metadata file if exists
                metadata_files = [
                    f
                    for f in file_list
                    if f.lower().endswith(".json") and f.lower() != main_file.lower()
                ]

                if metadata_files:
                    metadata_file = metadata_files[0]
                    metadata_path = Path(
                        zip_ref.extract(metadata_file, str(output_directory))
                    )
                    extracted_files.append(metadata_path)
                    log.debug("Extracted metadata file: %s", metadata_path)

                    # Read and log metadata for debugging
                    with open(metadata_path, "r") as f:
                        try:
                            file_metadata = json.load(f)
                            log.debug("Metadata: %s", file_metadata)
                        except json.JSONDecodeError:
                            log.warning("Could not parse metadata file")

                return RawDataResult(
                    path=main_file_path,
                    metadata=metadata,
                    extracted=True,
                    original_path=zip_path,
                    extracted_files=extracted_files,
                )

        except zipfile.BadZipFile:
            log.error("Invalid zip file: %s", zip_path)
            raise DownloadError(f"Invalid zip file: {zip_path}")

    async def _extract_with_stream_unzip(
        self, zip_path: Path, metadata: RawDataApiMetadata
    ) -> RawDataResult:
        """
        Extract using stream-unzip for memory efficiency with the async interface.

        Args:
            zip_path: Path to the zip file
            metadata: Data metadata

        Returns:
            RawDataResult with extraction information

        Raises:
            DownloadError: If extraction fails
        """
        try:
            # Import the required package
            try:
                import aiofiles
                from stream_unzip import async_stream_unzip
            except ImportError:
                log.warning(
                    "Required packages not found. Install with: pip install stream-unzip aiofiles. "
                    "Falling back to standard extraction."
                )
                log.error(
                    "Cannot extract file safely: file size (%d MB) exceeds memory threshold (%d MB) "
                    "and stream-unzip is not available. Install required packages or increase threshold.",
                    metadata.size_bytes // (1024 * 1024),
                    self.config.memory_threshold_mb,
                )
                # Return the original zip file
                return RawDataResult(path=zip_path, metadata=metadata, extracted=False)

            output_directory = zip_path.parent

            # For shapefile extraction, create a dedicated directory
            if metadata.format_ext.lower() == "shp":
                extract_dir = output_directory / f"{metadata.file_name}_shp"
                extract_dir.mkdir(parents=True, exist_ok=True)
                output_base = extract_dir
            else:
                output_base = output_directory

            # Prepare a file list to track what we extract
            extracted_files = []
            main_file_path = None
            target_ext = f".{metadata.format_ext.lower()}"

            # Create a properly async file reader
            async def zip_file_chunks():
                async with aiofiles.open(zip_path, "rb") as f:
                    while True:
                        chunk = await f.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        yield chunk

            # Process the zip file asynchronously
            try:
                extract_count = 0
                main_file_candidates = []

                async for (
                    file_name_bytes,
                    file_size,
                    unzipped_chunks,
                ) in async_stream_unzip(zip_file_chunks()):
                    try:
                        file_name = file_name_bytes.decode("utf-8")
                        log.debug(
                            "Processing file from archive: %s (%d bytes)",
                            file_name,
                            file_size,
                        )

                        # Determine if we should extract this file
                        should_extract = False

                        # For shapefiles, extract all files
                        if metadata.format_ext.lower() == "shp":
                            should_extract = True
                        # For main file type, extract it
                        elif file_name.lower().endswith(target_ext):
                            should_extract = True
                            main_file_candidates.append(file_name)
                        # For metadata files, extract them too
                        elif file_name.lower().endswith(".json"):
                            should_extract = True

                        if should_extract:
                            # Calculate output path and create parent directories
                            output_path = output_base / file_name
                            output_path.parent.mkdir(parents=True, exist_ok=True)

                            # Stream the file data to disk
                            async with aiofiles.open(output_path, "wb") as f:
                                async for chunk in unzipped_chunks:
                                    await f.write(chunk)

                            extracted_files.append(output_path)
                            extract_count += 1

                            # If this is the main file, track it
                            if file_name.lower().endswith(target_ext):
                                main_file_path = output_path
                        else:
                            # Skip this file's content
                            async for _ in unzipped_chunks:
                                pass
                    except Exception as file_ex:
                        log.warning(
                            "Error extracting file %s: %s",
                            file_name_bytes.decode("utf-8", errors="replace"),
                            str(file_ex),
                        )

                log.info(
                    "Extracted %d files using async streaming extraction", extract_count
                )

                # For shapefiles, return the directory
                if metadata.format_ext.lower() == "shp":
                    result_path = extract_dir
                else:
                    if not main_file_path:
                        # If no main file was found, this is an error
                        if main_file_candidates:
                            log.error(
                                "Failed to extract any of the candidate main files: %s",
                                main_file_candidates,
                            )
                        else:
                            log.error("No %s files found in the archive", target_ext)
                        raise DownloadError(
                            f"Failed to extract main file with extension {target_ext}"
                        )
                    result_path = main_file_path

                # Create the result
                return RawDataResult(
                    path=result_path,
                    metadata=metadata,
                    extracted=True,
                    original_path=zip_path,
                    extracted_files=extracted_files,
                )

            except Exception as ex:
                log.error("Error during streaming extraction: %s", str(ex))
                raise

        except Exception as ex:
            log.error("Error in streaming extraction: %s", str(ex))
            log.warning("Falling back to standard extraction")
            return await self._extract_with_zipfile(zip_path, metadata)
