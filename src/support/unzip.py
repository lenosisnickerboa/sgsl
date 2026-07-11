"""
unzip.py

A small utility to extract a zip archive to a target directory.
"""

import zipfile
from pathlib import Path
from typing import Optional, Union


def unzip(archive_path: Union[str, Path], target_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Extract all files in the zip archive at `archive_path` into
    `target_path`.

    Parameters
    ----------
    archive_path : Union[str, Path]
        Path to the .zip archive to extract.
    target_path : Optional[Union[str, Path]]
        Directory to extract the archive's contents into. If not
        given, the archive is extracted into the same directory it
        resides in. Created if it doesn't already exist.

    Returns
    -------
    Path
        The directory the archive was extracted into.

    Raises
    ------
    FileNotFoundError
        If archive_path does not exist.
    zipfile.BadZipFile
        If archive_path is not a valid zip archive.
    """
    archive_path = Path(archive_path)
    if not archive_path.is_file():
        raise FileNotFoundError(f"No such archive: {archive_path}")

    target_path = Path(target_path) if target_path is not None else archive_path.parent
    target_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path) as zf:
        zf.extractall(target_path)

    return target_path


def unzip_with_return(archive_path: Union[str, Path], target_path: Optional[Union[str, Path]] = None) -> bool:
    """
    Same as unzip(), but never raises: returns True on success and
    False if anything went wrong (missing archive, invalid zip file,
    filesystem error, etc.).

    Parameters
    ----------
    archive_path : Union[str, Path]
        Path to the .zip archive to extract.
    target_path : Optional[Union[str, Path]]
        Same as unzip()'s target_path.

    Returns
    -------
    bool
        True if the archive was extracted successfully, False otherwise.
    """
    try:
        unzip(archive_path, target_path)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Example usage
    extracted_to = unzip(r"C:\temp\archive.zip")
    print(f"Extracted to {extracted_to}")
