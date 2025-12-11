"""Portainer API deployment backend"""

import httpx
from pathlib import Path
from string import Template
from ..utils import logger


def deploy(config, env_file: Path | None, url: str, api_key: str):
    """Deploy via Portainer API

    Args:
        config: DeployConfig instance
        env_file: Path to env file, or None if no env file exists
        url: Portainer URL
        api_key: Portainer API key
    """
    client = httpx.Client(base_url=url, headers={"X-API-Key": api_key}, timeout=30.0)

    try:
        endpoint_id = get_endpoint(client)
        compose_content = prepare_compose_content(config)
        env_vars = parse_env_file(env_file) if env_file else []

        stack_id = check_stack_exists(client, config.project_name)

        if stack_id:
            update_stack(client, stack_id, endpoint_id, compose_content, env_vars)
        else:
            create_stack(
                client, config.project_name, endpoint_id, compose_content, env_vars
            )

        logger.success(f"Portainer deployment complete: {config.project_name}")
    finally:
        client.close()


def teardown(config, url: str, api_key: str):
    """Remove stack from Portainer via REST API.

    Args:
        config: DeployConfig instance
        url: Portainer URL
        api_key: Portainer API key
    """
    logger.info(f"Tearing down stack '{config.project_name}' from Portainer")

    client = httpx.Client(base_url=url, headers={"X-API-Key": api_key}, timeout=30.0)

    try:
        endpoint_id = get_endpoint(client)
        stack_id = check_stack_exists(client, config.project_name)

        if not stack_id:
            logger.warn(f"Stack '{config.project_name}' not found - already torn down?")
            return

        # Delete stack
        resp = client.delete(
            f"/api/stacks/{stack_id}", params={"endpointId": endpoint_id}
        )
        resp.raise_for_status()

        logger.success(f"Stack '{config.project_name}' removed from Portainer")
    finally:
        client.close()


def get_endpoint(client: httpx.Client) -> int:
    """Get Portainer endpoint ID (usually 1 for single-node)

    Args:
        client: Authenticated httpx client

    Returns:
        Endpoint ID

    Raises:
        RuntimeError: If no endpoints found
    """
    resp = client.get("/api/endpoints")
    resp.raise_for_status()
    endpoints = resp.json()

    if not endpoints:
        raise RuntimeError("No Portainer endpoints found")

    return endpoints[0]["Id"]


def check_stack_exists(client: httpx.Client, name: str) -> int | None:
    """Check if stack with given name exists

    Args:
        client: Authenticated httpx client
        name: Stack name to check

    Returns:
        Stack ID if exists, None otherwise
    """
    resp = client.get("/api/stacks")
    resp.raise_for_status()

    for stack in resp.json():
        if stack["Name"] == name:
            return stack["Id"]

    return None


def create_stack(
    client: httpx.Client, name: str, endpoint_id: int, compose: str, env_vars: list
):
    """Create new Portainer stack

    Args:
        client: Authenticated httpx client
        name: Stack name
        endpoint_id: Portainer endpoint ID
        compose: Docker compose content
        env_vars: Environment variables as list of dicts
    """
    logger.info(f"Creating Portainer stack: {name}")

    resp = client.post(
        f"/api/stacks/create/standalone/string?endpointId={endpoint_id}",
        json={"name": name, "stackFileContent": compose, "env": env_vars},
    )
    resp.raise_for_status()


def update_stack(
    client: httpx.Client,
    stack_id: int,
    endpoint_id: int,
    compose: str,
    env_vars: list,
):
    """Update existing Portainer stack

    Args:
        client: Authenticated httpx client
        stack_id: Existing stack ID
        endpoint_id: Portainer endpoint ID
        compose: Docker compose content
        env_vars: Environment variables as list of dicts
    """
    logger.info(f"Updating Portainer stack ID: {stack_id}")

    resp = client.put(
        f"/api/stacks/{stack_id}?endpointId={endpoint_id}",
        json={"stackFileContent": compose, "env": env_vars, "prune": False},
    )
    resp.raise_for_status()


def prepare_compose_content(config) -> str:
    """Load and substitute compose template

    Args:
        config: DeployConfig instance

    Returns:
        Substituted compose content
    """
    from .compose import find_compose_template

    template_path = find_compose_template()
    template = Template(template_path.read_text())

    return template.substitute(
        PROJECT_NAME=config.project_name,
        IMAGE_TAG=config.image_tag,
        PORT=config.port,
        HEALTHCHECK_PATH=config.healthcheck_path,
    )


def parse_env_file(env_file: Path | None) -> list[dict]:
    """Convert .env file to Portainer format

    Args:
        env_file: Path to .env file, or None if no env file exists

    Returns:
        List of dicts with 'name' and 'value' keys (empty list if env_file is None)
    """
    if not env_file:
        return []

    env_vars = []

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env_vars.append({"name": key.strip(), "value": value.strip()})

    return env_vars
