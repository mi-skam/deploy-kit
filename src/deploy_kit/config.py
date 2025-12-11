"""Configuration detection and loading from project's pyproject.toml"""

import tomllib
import subprocess
import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class DeployConfig:
    """Deployment configuration"""

    project_name: str
    project_version: str
    image_tag: str
    port: int
    healthcheck_path: str
    keep_tarballs: int
    architecture: str
    ssh_target: str | None
    portainer_url: str | None


def get_platform_architecture() -> str:
    """Detect current system architecture and convert to Docker platform format

    Returns:
        Docker platform string like "linux/arm64" or "linux/amd64"
    """
    result = subprocess.run(
        ["uname", "-m"],
        capture_output=True,
        text=True,
        check=True,
    )
    arch = result.stdout.strip()

    # Normalize to Docker platform format
    if arch in ("arm64", "aarch64"):
        return "linux/arm64"
    elif arch in ("x86_64", "amd64"):
        return "linux/amd64"

    raise ValueError(f"Unsupported architecture: {arch}")


def load_config() -> DeployConfig:
    """Load config from project's pyproject.toml (CWD, not deploy-kit's)

    Configuration precedence (highest to lowest):
    1. Environment variables (DEPLOY_PORT, IMAGE_TAG, etc.)
    2. deploy-kit.toml overrides
    3. pyproject.toml auto-detection
    4. Built-in defaults
    """
    # Look in current working directory (the project using deploy-kit)
    cwd = Path.cwd()
    pyproject = cwd / "pyproject.toml"

    if not pyproject.exists():
        raise FileNotFoundError(f"pyproject.toml not found in {cwd}")

    # Load pyproject.toml (required)
    with open(pyproject, "rb") as f:
        pyproject_data = tomllib.load(f)

    project_name = pyproject_data["project"]["name"]
    project_version = pyproject_data["project"].get("version", "0.0.0")

    # Load deploy-kit.toml from project (optional overrides)
    deploy_toml = cwd / "deploy-kit.toml"
    deploy_config = {}
    if deploy_toml.exists():
        with open(deploy_toml, "rb") as f:
            deploy_data = tomllib.load(f)
            deploy_config = deploy_data.get("deploy", {})

    # Git hash for image tag
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        git_hash = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_hash = "latest"

    # Merge with precedence: env vars > deploy-kit.toml > defaults
    return DeployConfig(
        project_name=project_name,
        project_version=project_version,
        image_tag=os.getenv("IMAGE_TAG", git_hash),
        port=int(os.getenv("DEPLOY_PORT", deploy_config.get("port", 8000))),
        healthcheck_path=os.getenv(
            "DEPLOY_HEALTHCHECK_PATH", deploy_config.get("healthcheck_path", "/")
        ),
        keep_tarballs=int(deploy_config.get("keep_tarballs", 3)),
        architecture=os.getenv(
            "DEPLOY_ARCH",
            deploy_config.get("architecture", get_platform_architecture()),
        ),
        ssh_target=os.getenv("DEPLOY_TARGET", deploy_config.get("ssh_target")),
        portainer_url=os.getenv("PORTAINER_URL", deploy_config.get("portainer_url")),
    )
