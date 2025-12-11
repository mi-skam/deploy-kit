"""SOPS detection and decryption"""

import subprocess
import tempfile
from pathlib import Path
from .utils import logger

# Global to track temp file for cleanup
_temp_env_file: Path | None = None


def detect_env_file() -> Path | None:
    """Detect and prepare env file (decrypt .env.sops if present)

    Returns:
        Path to env file (either .env or decrypted temp file), or None if no env file exists
    """
    global _temp_env_file

    cwd = Path.cwd()
    env_sops = cwd / ".env.sops"
    env_plain = cwd / ".env"

    if env_sops.exists():
        logger.info("Detected .env.sops, decrypting...")
        _temp_env_file = decrypt_to_temp(env_sops)
        return _temp_env_file
    elif env_plain.exists():
        logger.info("Using .env file")
        return env_plain
    else:
        logger.warning(
            "No .env or .env.sops found - deploying without environment variables"
        )
        return None


def decrypt_to_temp(env_sops: Path) -> Path:
    """Decrypt .env.sops using sops CLI to temporary file

    Args:
        env_sops: Path to .env.sops file

    Returns:
        Path to temporary decrypted file

    Raises:
        RuntimeError: If sops is not installed or decryption fails
    """
    # Create temp file
    temp = tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False)
    temp_path = Path(temp.name)
    temp.close()

    try:
        # Call sops CLI directly with dotenv format
        with open(temp_path, "w") as f:
            subprocess.run(
                [
                    "sops",
                    "--input-type",
                    "dotenv",
                    "--output-type",
                    "dotenv",
                    "-d",
                    str(env_sops),
                ],
                stdout=f,
                check=True,
                text=True,
            )
    except FileNotFoundError:
        temp_path.unlink()
        raise RuntimeError(
            "SOPS not found. Install with: brew install sops (or your package manager)"
        )
    except subprocess.CalledProcessError as e:
        temp_path.unlink()
        raise RuntimeError(
            f"SOPS decryption failed. Check your age/PGP keys are configured correctly. Error: {e}"
        )

    logger.success("Decrypted .env.sops successfully")
    return temp_path


def cleanup_temp_files():
    """Remove temporary decrypted env file if it was created"""
    global _temp_env_file

    if _temp_env_file and _temp_env_file.exists():
        try:
            _temp_env_file.unlink()
            logger.info("Cleaned up temporary env file")
        except Exception as e:
            logger.warn(f"Failed to cleanup temp file: {e}")
        finally:
            _temp_env_file = None
