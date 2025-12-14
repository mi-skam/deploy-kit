"""Docker operations using the Docker SDK"""

import gzip
from pathlib import Path

import docker
from docker.errors import BuildError, APIError, ImageNotFound

from .config import DeployConfig
from .utils import logger


def build_image(config: DeployConfig) -> None:
    """Build Docker image using Docker SDK.

    Args:
        config: DeployConfig instance with project_name, image_tag, and architecture
    """
    logger.info(
        f"Building {config.project_name}:{config.image_tag} for {config.architecture}..."
    )

    with docker.from_env() as client:
        try:
            # Build image with platform specification
            image, build_logs = client.images.build(
                path=".",
                tag=f"{config.project_name}:{config.image_tag}",
                platform=config.architecture,
                rm=True,  # Remove intermediate containers
                decode=True,  # Decode log chunks as dicts
            )

            # Stream build output for visibility
            for chunk in build_logs:
                if "stream" in chunk:
                    line = chunk["stream"].strip()
                    if line:
                        print(line)  # Direct output for build progress

            # Also tag as latest
            image.tag(config.project_name, "latest")

        except BuildError as e:
            logger.error(f"Build failed: {e.msg}")
            for log in e.build_log:
                if "stream" in log:
                    print(log["stream"].strip())
            raise
        except APIError as e:
            logger.error(f"Docker API error: {e}")
            raise

    logger.success(f"Built: {config.project_name}:{config.image_tag}")


def save_image(config: DeployConfig) -> Path:
    """Save Docker image to gzipped tarball using Docker SDK.

    Args:
        config: DeployConfig instance

    Returns:
        Path to created tarball
    """
    logger.info("Saving image to tarball...")

    dist = Path("dist")
    dist.mkdir(exist_ok=True)

    tarball = dist / f"{config.project_name}-{config.image_tag}.tar.gz"

    with docker.from_env() as client:
        try:
            image = client.images.get(f"{config.project_name}:{config.image_tag}")

            # Save image and compress with gzip
            with gzip.open(tarball, "wb") as f:
                for chunk in image.save(named=True):
                    f.write(chunk)

        except ImageNotFound:
            logger.error(f"Image not found: {config.project_name}:{config.image_tag}")
            raise
        except APIError as e:
            logger.error(f"Docker API error: {e}")
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
