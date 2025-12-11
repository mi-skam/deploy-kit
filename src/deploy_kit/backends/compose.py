"""Docker Compose deployment backend (SSH + SCP)"""
from pathlib import Path
from .. import docker
from ..utils import logger
from ..scripts import run_script


def deploy(target: str, config, env_file: Path | None):
    """Deploy via docker-compose (SSH + SCP)

    Args:
        target: SSH target (user@host)
        config: DeployConfig instance
        env_file: Path to env file, or None if no env file exists
    """
    # Save image to tarball
    tarball = docker.save_image(config)

    # Find compose template
    template = find_compose_template()

    # Transfer files
    logger.info(f"Transferring files to {target}...")
    run_script(
        "ssh_transfer.sh",
        [target, str(tarball), str(template), str(env_file) if env_file else ""],
    )
    logger.success("Files transferred")

    # Remote deploy
    logger.info(f"Deploying on {target}...")
    run_script(
        "ssh_remote_deploy.sh",
        [
            target,
            config.project_name,
            config.image_tag,
            str(config.port),
            config.healthcheck_path,
        ],
    )
    logger.success("Remote deployment complete")

    # Cleanup old tarballs
    docker.cleanup_old_tarballs(config.project_name, config.keep_tarballs)


def find_compose_template() -> Path:
    """Find docker-compose template (project root or deploy-kit fallback)

    Returns:
        Path to docker-compose.prod.yml.template

    Raises:
        FileNotFoundError: If template not found
    """
    # Check project root first
    local = Path("docker-compose.prod.yml.template")
    if local.exists():
        return local

    # Fallback to deploy-kit template
    try:
        from .. import __file__ as pkg_file

        toolkit_templates = Path(pkg_file).parent.parent / "templates" / "docker"
        template_path = toolkit_templates / "docker-compose.prod.yml.template"
        if template_path.exists():
            return template_path
    except Exception:
        pass

    raise FileNotFoundError(
        "docker-compose.prod.yml.template not found in project root or deploy-kit templates"
    )
