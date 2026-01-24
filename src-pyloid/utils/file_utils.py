"""File system utilities for model management."""

import hashlib
import shutil
import struct
from pathlib import Path
from typing import Optional


def get_models_directory(pyloid_app) -> Path:
    """Get or create the models directory using Pyloid app instance.
    
    Args:
        pyloid_app: Pyloid application instance
        
    Returns:
        Path to models directory
        
    Raises:
        OSError: If directory cannot be created
    """
    # Get user data directory from Pyloid app
    user_data_dir = pyloid_app.user_data_dir()
    models_dir = Path(user_data_dir) / "models"

    # Create directory if it doesn't exist
    models_dir.mkdir(parents=True, exist_ok=True)

    return models_dir


def validate_gguf_file(file_path: Path) -> bool:
    """Validate that a file is a valid GGUF format.
    
    GGUF files start with a magic number: 'GGUF' (0x46554747 in little-endian).
    
    Args:
        file_path: Path to file to validate
        
    Returns:
        True if file is valid GGUF format, False otherwise
    """
    if not file_path.exists() or not file_path.is_file():
        return False

    try:
        with open(file_path, "rb") as f:
            # Read first 4 bytes (magic number)
            magic = f.read(4)
            
            # Check if it matches GGUF magic number
            # GGUF in ASCII is: 0x47 0x47 0x55 0x46
            return magic == b"GGUF"
    except (OSError, IOError):
        return False


def calculate_file_hash(file_path: Path, algorithm: str = "sha256") -> Optional[str]:
    """Calculate hash of a file.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm (default: sha256)
        
    Returns:
        Hexadecimal hash string, or None if file doesn't exist
    """
    if not file_path.exists() or not file_path.is_file():
        return None

    hash_obj = hashlib.new(algorithm)
    
    try:
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except (OSError, IOError):
        return None


def get_available_space(path: Path) -> int:
    """Get available disk space at the given path.
    
    Args:
        path: Path to check (file or directory)
        
    Returns:
        Available space in bytes
    """
    # Get parent directory if path is a file
    if path.is_file():
        path = path.parent
    elif not path.exists():
        # If path doesn't exist, use parent
        path = path.parent

    stat = shutil.disk_usage(path)
    return stat.free


def cleanup_partial_download(file_path: Path) -> bool:
    """Remove incomplete download files (.part extension).
    
    Args:
        file_path: Base path to downloaded file
        
    Returns:
        True if cleanup was successful or no files to clean
    """
    try:
        # Check for .part file
        part_file = Path(str(file_path) + ".part")
        if part_file.exists():
            part_file.unlink()
        
        # Check for .lock file (if any)
        lock_file = Path(str(file_path) + ".lock")
        if lock_file.exists():
            lock_file.unlink()
            
        return True
    except (OSError, IOError):
        return False


def get_file_size(file_path: Path) -> int:
    """Get size of a file in bytes.
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in bytes, or 0 if file doesn't exist
    """
    if not file_path.exists() or not file_path.is_file():
        return 0
    return file_path.stat().st_size
