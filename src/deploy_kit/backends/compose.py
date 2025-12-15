"""Docker Compose deployment backend (SSH + SCP)"""

import re
import subprocess
from pathlib import Path

from .. import docker
from ..utils import logger
from ..scripts import run_script, run_script_capture

SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


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

    # Check if tarball already exists on remote with same hash
    local_hash = docker.compute_file_hash(tarball)
    tarball_name = tarball.name

    try:
        remote_hash = run_script_capture("ssh_check_hash.sh", [target, tarball_name])
        if not SHA256_PATTERN.match(remote_hash):
            remote_hash = ""
    except subprocess.CalledProcessError:
        remote_hash = ""

    skip_tarball = remote_hash and remote_hash == local_hash
    if skip_tarball:
        logger.info(f"Tarball already on {target} with matching hash, skipping tarball transfer")

    # Transfer files (tarball transfer is conditional)
    logger.info(f"Transferring files to {target}...")
    run_script(
        "ssh_transfer.sh",
        [
            target,
            str(tarball),
            str(template),
            str(env_file) if env_file else "",
            "true" if skip_tarball else "false",
        ],
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


def teardown(target: str, config, keep_images: bool, keep_files: bool):
    """Remove deployed resources from remote server via SSH.

    Args:
        target: SSH target (user@host)
        config: DeployConfig instance
        keep_images: If True, preserve Docker images on remote
        keep_files: If True, preserve transferred files in /tmp/
    """
    logger.info(f"Tearing down {config.project_name} from {target}")

    run_script(
        "ssh_remote_teardown.sh",
        [
            target,
            config.project_name,
            config.image_tag,
            "true" if keep_images else "false",
            "true" if keep_files else "false",
        ],
    )

    logger.success(f"Teardown complete for {config.project_name}")


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
