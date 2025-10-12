"""File operations utilities for plugin modules."""

import datetime
from pathlib import Path
from typing import Any

import structlog

from utils.obsidian import read_obsidian_file


def ensure_directory_exists(directory_path: Path | str) -> bool:
    """Ensure directory exists, creating it if necessary.

    Args:
        directory_path: Path to directory (Path object or string)

    Returns:
        True if directory exists or was created successfully, False otherwise
    """
    path = Path(directory_path) if isinstance(directory_path, str) else directory_path

    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except PermissionError:
        structlog.get_logger().error(f"Permission denied creating directory: {path}")
        return False
    except Exception as e:
        structlog.get_logger().error(f"Error creating directory {path}: {e}")
        return False


def get_file_modification_date(file_path: Path, timezone: Any) -> datetime.date | None:
    """Get file modification date in specified timezone.

    Args:
        file_path: Path to the file
        timezone: Timezone object for date conversion

    Returns:
        Date of last modification or None if file doesn't exist or error occurs
    """
    try:
        file_stat = file_path.stat()
        return datetime.datetime.fromtimestamp(file_stat.st_mtime, tz=timezone).date()
    except FileNotFoundError:
        structlog.get_logger().debug(f"File not found: {file_path}")
        return None
    except Exception as e:
        structlog.get_logger().error(f"Error getting modification date for {file_path}: {e}")
        return None


def is_file_modified_today(file_path: Path, timezone: Any) -> bool:
    """Check if file was modified today.

    Args:
        file_path: Path to the file
        timezone: Timezone object for date comparison

    Returns:
        True if file was modified today, False otherwise
    """
    today = datetime.datetime.now(timezone).date()
    file_date = get_file_modification_date(file_path, timezone)
    return file_date == today if file_date else False


def backup_file(file_path: Path, backup_suffix: str = ".backup") -> bool:
    """Create a backup copy of a file.

    Args:
        file_path: Path to the original file
        backup_suffix: Suffix to add to backup filename

    Returns:
        True if backup was created successfully, False otherwise
    """
    if not file_path.exists():
        structlog.get_logger().warning(f"Cannot backup non-existent file: {file_path}")
        return False

    backup_path = file_path.with_suffix(f"{file_path.suffix}{backup_suffix}")

    try:
        content = read_obsidian_file(file_path)
        if content is None:
            # read_obsidian_file already logs the error
            return False

        with open(backup_path, "w", encoding="utf-8") as file:
            file.write(content)
        structlog.get_logger().debug(f"Successfully wrote backup to {backup_path}")
        return True
    except Exception as e:
        structlog.get_logger().error(f"Error creating backup of {file_path}: {e}")
        return False


def list_files_by_pattern(directory: Path | str, pattern: str) -> list[Path]:
    """List files in directory matching a glob pattern.

    Args:
        directory: Directory to search in
        pattern: Glob pattern to match (e.g., "*.md", "**/*.txt")

    Returns:
        List of matching file paths, empty list if directory doesn't exist or error occurs
    """
    dir_path = Path(directory) if isinstance(directory, str) else directory

    if not dir_path.exists() or not dir_path.is_dir():
        structlog.get_logger().debug(f"Directory does not exist or is not a directory: {dir_path}")
        return []

    try:
        return list(dir_path.glob(pattern))
    except Exception as e:
        structlog.get_logger().error(f"Error listing files in {dir_path} with pattern {pattern}: {e}")
        return []


def get_file_size(file_path: Path) -> int | None:
    """Get file size in bytes.

    Args:
        file_path: Path to the file

    Returns:
        File size in bytes or None if file doesn't exist or error occurs
    """
    try:
        return file_path.stat().st_size
    except FileNotFoundError:
        structlog.get_logger().debug(f"File not found: {file_path}")
        return None
    except Exception as e:
        structlog.get_logger().error(f"Error getting file size for {file_path}: {e}")
        return None
