"""Docker operations orchestration"""

from pathlib import Path
from .utils import logger
from .scripts import run_script


def build_image(config):
    """Build Docker image using bash script

    Args:
        config: DeployConfig instance with project_name, image_tag, and architecture
    """
    logger.info(
        f"Building {config.project_name}:{config.image_tag} for {config.architecture}..."
    )

    # Call bash script for build with architecture
    run_script(
        "docker_build.sh", [config.project_name, config.image_tag, config.architecture]
    )

    logger.success(f"Built: {config.project_name}:{config.image_tag}")


def save_image(config) -> Path:
    """Save Docker image to tarball using bash script

    Args:
        config: DeployConfig instance

    Returns:
        Path to created tarball
    """
    logger.info("Saving image to tarball...")

    dist = Path("dist")
    dist.mkdir(exist_ok=True)

    tarball = dist / f"{config.project_name}-{config.image_tag}.tar.gz"

    # Call bash script for save
    run_script("docker_save.sh", [config.project_name, config.image_tag, str(tarball)])

    logger.success(f"Saved: {tarball}")
    return tarball


def push_image(config, registry_url: str) -> str:
    """Tag and push Docker image to registry

    Args:
        config: DeployConfig instance
        registry_url: Registry URL (e.g., "localhost:5000" or "dockerhost:5000")

    Returns:
        Full image reference with registry prefix (e.g., "localhost:5000/myapp:abc123")
    """
    registry_image = f"{registry_url}/{config.project_name}:{config.image_tag}"
    logger.info(f"Pushing image to registry: {registry_image}")

    try:
        run_script(
            "docker_push.sh", [config.project_name, config.image_tag, registry_url]
        )
    except Exception as e:
        logger.error(f"Failed to push image to registry: {registry_image}")
        logger.error(f"Error: {e}")
        # Optionally, inspect the error message for common Docker push failures
        if hasattr(e, "output") and e.output:
            output = e.output.decode() if hasattr(e.output, "decode") else str(e.output)
            if "authentication required" in output.lower():
                logger.error("Docker registry authentication failed. Please check your credentials.")
            elif "connection refused" in output.lower() or "network" in output.lower():
                logger.error("Could not connect to Docker registry. Please check registry URL and network connectivity.")
        raise

    logger.success(f"Pushed: {registry_image}")
    return registry_image


def cleanup_old_tarballs(project_name: str, keep: int):
    """Remove old tarballs, keeping only the most recent N

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
