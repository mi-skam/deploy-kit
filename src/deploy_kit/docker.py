"""Docker operations using python-on-whales (CLI wrapper)"""

import gzip
import shutil
from pathlib import Path

from python_on_whales import docker, exceptions

from .config import DeployConfig
from .utils import logger


def build_image(config: DeployConfig) -> None:
    """Build Docker image using Docker CLI via python-on-whales.

    Args:
        config: DeployConfig instance with project_name, image_tag, and architecture
    """
    image_tag = f"{config.project_name}:{config.image_tag}"
    logger.info(f"Building {image_tag} for {config.architecture}...")

    try:
        docker.build(
            context_path=".",
            tags=[image_tag, f"{config.project_name}:latest"],
            platforms=[config.architecture],
        )
        logger.success(f"Built: {image_tag}")

    except exceptions.DockerException as e:
        logger.error(f"Build failed: {e}")
        raise


def save_image(config: DeployConfig) -> Path:
    """Save Docker image to gzipped tarball.

    Args:
        config: DeployConfig instance

    Returns:
        Path to created tarball
    """
    logger.info("Saving image to tarball...")

    dist = Path("dist")
    dist.mkdir(exist_ok=True)

    tarball = dist / f"{config.project_name}-{config.image_tag}.tar.gz"
    tar_uncompressed = dist / f"{config.project_name}-{config.image_tag}.tar"
    image_tag = f"{config.project_name}:{config.image_tag}"

    try:
        # Save uncompressed tar first
        docker.image.save(image_tag, output=tar_uncompressed)

        # Compress with gzip
        with open(tar_uncompressed, "rb") as f_in:
            with gzip.open(tarball, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove uncompressed tar
        tar_uncompressed.unlink()

    except exceptions.DockerException as e:
        logger.error(f"Save failed: {e}")
        raise

    logger.success(f"Saved: {tarball}")
    return tarball


def cleanup_old_tarballs(project_name: str, keep: int) -> None:
    """Remove old tarballs, keeping only the most recent N.

    Args:
        project_name: Project name to match tarball pattern
        keep: Number of recent tarballs to keep
    """
    dist = Path("dist")
    if not dist.exists():
        return

    pattern = f"{project_name}-*.tar.gz"
    tarballs = sorted(dist.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

    for old in tarballs[keep:]:
        old.unlink()
        logger.info(f"Removed old tarball: {old.name}")
