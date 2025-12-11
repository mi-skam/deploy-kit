#!/usr/bin/env python3
"""Deploy-kit CLI - Explicit backend selection"""
import click
import os
import sys
from . import config, docker, sops
from .backends import compose, portainer
from .utils import logger


@click.group()
@click.version_option(version="0.1.0", prog_name="deploy-kit")
def main():
    """Deploy-kit: Docker deployment toolkit"""
    pass


@main.command()
@click.option(
    "--compose",
    "-c",
    "backend",
    flag_value="compose",
    help="Deploy via Docker Compose (SSH)",
)
@click.option(
    "--portainer",
    "-p",
    "backend",
    flag_value="portainer",
    help="Deploy via Portainer API",
)
@click.argument("target", required=False)
def up(backend: str | None, target: str | None):
    """Deploy to target server

    TARGET can be:
    - SSH target (user@host) for Compose backend
    - Portainer URL for Portainer backend
    - Omitted if set in environment variables

    \b
    Examples:
      deploy-kit up --compose user@host.example.com   # Compose with SSH target
      deploy-kit up --portainer https://portainer.io  # Portainer with URL
      deploy-kit up -c user@host                      # Short form
      deploy-kit up -p https://portainer.io           # Short form

    \b
    Environment variables:
      DEPLOY_TARGET       - SSH target for Compose
      PORTAINER_URL       - Portainer URL
      PORTAINER_API_KEY   - Portainer API key (required for Portainer)
    """
    try:
        # Load config from project's pyproject.toml
        cfg = config.load_config()
        logger.info(f"Project: {cfg.project_name} (tag: {cfg.image_tag})")

        # Detect and prepare env file (handles SOPS if present)
        # Returns None if no env file exists (which is valid for apps without env vars)
        env_file = sops.detect_env_file()

        # Validate backend selection
        if not backend:
            logger.error("No backend specified!")
            logger.error("Use --compose/-c or --portainer/-p")
            raise click.UsageError(
                "Backend required: use --compose user@host or --portainer"
            )

        # Validate backend-specific requirements BEFORE building
        if backend == "compose":
            ssh_target = target or os.getenv("DEPLOY_TARGET")
            if not ssh_target:
                logger.error("SSH target required for Compose backend")
                logger.error("Provide as argument or set DEPLOY_TARGET env var")
                raise click.UsageError(
                    "Usage: deploy-kit --compose user@host.example.com"
                )
        elif backend == "portainer":
            portainer_url = target or os.getenv("PORTAINER_URL")
            portainer_key = os.getenv("PORTAINER_API_KEY")
            if not portainer_url:
                logger.error("Portainer URL required")
                logger.error("Provide as argument or set PORTAINER_URL env var")
                raise click.UsageError(
                    "Usage: deploy-kit --portainer https://portainer.example.com"
                )
            if not portainer_key:
                logger.error("PORTAINER_API_KEY environment variable required")
                raise click.UsageError(
                    "Set PORTAINER_API_KEY before deploying to Portainer"
                )

        # Build Docker image (only after all validation passes)
        docker.build_image(cfg)

        # Deploy based on backend
        try:
            if backend == "compose":
                ssh_target = target or os.getenv("DEPLOY_TARGET")  # Already validated
                logger.info(f"Using Compose backend → {ssh_target}")
                compose.deploy(ssh_target, cfg, env_file)

            elif backend == "portainer":
                portainer_url = target or os.getenv("PORTAINER_URL")  # Already validated
                portainer_key = os.getenv("PORTAINER_API_KEY")  # Already validated
                logger.info(f"Using Portainer backend → {portainer_url}")
                portainer.deploy(cfg, env_file, portainer_url, portainer_key)
        finally:
            # Always cleanup temp files
            sops.cleanup_temp_files()

        logger.success(f"Deployment complete: {cfg.project_name}")

    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except click.UsageError:
        raise  # Let click handle usage errors
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--compose",
    "-c",
    "backend",
    flag_value="compose",
    help="Teardown via Docker Compose (SSH)",
)
@click.option(
    "--portainer",
    "-p",
    "backend",
    flag_value="portainer",
    help="Teardown via Portainer API",
)
@click.option(
    "--keep-images",
    is_flag=True,
    help="Keep Docker images (don't remove)",
)
@click.option(
    "--keep-files",
    is_flag=True,
    help="Keep transferred files in /tmp/",
)
@click.argument("target", required=False)
def down(backend: str | None, target: str | None, keep_images: bool, keep_files: bool):
    """Remove deployed resources from remote server or Portainer

    TARGET can be:
    - SSH target (user@host) for Compose backend
    - Portainer URL for Portainer backend
    - Omitted if set in environment variables

    \b
    Examples:
      deploy-kit down --compose user@host.example.com   # Compose teardown
      deploy-kit down --portainer https://portainer.io  # Portainer teardown
      deploy-kit down -c user@host --keep-images        # Keep Docker images
      deploy-kit down -c user@host --keep-files         # Keep /tmp/ files

    \b
    Environment variables:
      DEPLOY_TARGET       - SSH target for Compose
      PORTAINER_URL       - Portainer URL
      PORTAINER_API_KEY   - Portainer API key (required for Portainer)
    """
    try:
        # Load config from project's pyproject.toml
        cfg = config.load_config()
        logger.info(f"Project: {cfg.project_name} (tag: {cfg.image_tag})")

        # Validate backend selection
        if not backend:
            logger.error("No backend specified!")
            logger.error("Use --compose/-c or --portainer/-p")
            raise click.UsageError(
                "Backend required: use --compose user@host or --portainer"
            )

        # Teardown based on backend
        if backend == "compose":
            ssh_target = target or os.getenv("DEPLOY_TARGET")
            if not ssh_target:
                logger.error("SSH target required for Compose backend")
                logger.error("Provide as argument or set DEPLOY_TARGET env var")
                raise click.UsageError(
                    "Usage: deploy-kit down --compose user@host.example.com"
                )
            logger.info(f"Using Compose backend → {ssh_target}")
            compose.teardown(ssh_target, cfg, keep_images, keep_files)

        elif backend == "portainer":
            portainer_url = target or os.getenv("PORTAINER_URL")
            portainer_key = os.getenv("PORTAINER_API_KEY")
            if not portainer_url:
                logger.error("Portainer URL required")
                logger.error("Provide as argument or set PORTAINER_URL env var")
                raise click.UsageError(
                    "Usage: deploy-kit down --portainer https://portainer.example.com"
                )
            if not portainer_key:
                logger.error("PORTAINER_API_KEY environment variable required")
                raise click.UsageError(
                    "Set PORTAINER_API_KEY before tearing down from Portainer"
                )
            logger.info(f"Using Portainer backend → {portainer_url}")
            portainer.teardown(cfg, portainer_url, portainer_key)

        logger.success(f"Teardown complete: {cfg.project_name}")

    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except click.UsageError:
        raise  # Let click handle usage errors
    except Exception as e:
        logger.error(f"Teardown failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
