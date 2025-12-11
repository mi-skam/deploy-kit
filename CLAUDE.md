# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Deploy-kit is a Docker deployment toolkit supporting two backends: Docker Compose over SSH and Portainer API. The architecture uses **Python for orchestration** and **Bash scripts for Docker operations**.

**Primary users:** Developers deploying containerized Python applications to remote servers or Portainer instances.

**Key differentiator:** Python orchestration layer that delegates actual Docker operations to bash scripts, with built-in SOPS integration for encrypted secrets management and multi-architecture build support.

## Core Architecture

### Orchestrator-Executor Pattern

```
Python (orchestration)  →  Bash scripts (execution)
  ├─ cli.py            →    docker_build.sh
  ├─ docker.py         →    docker_save.sh
  ├─ backends/         →    ssh_transfer.sh
  │   ├─ compose.py    →    ssh_remote_deploy.sh
  │   └─ portainer.py
  └─ config.py
```

**Key principle**: Python never executes Docker commands directly. All Docker/SSH operations happen in bash scripts invoked via `subprocess.run()`.

### Configuration Loading (4-Layer Precedence)

Configuration merges in this order (highest to lowest):

1. **Environment variables** - `DEPLOY_PORT`, `DEPLOY_ARCH`, `IMAGE_TAG`, etc.
2. **deploy-kit.toml** - Project-specific overrides in `[deploy]` section
3. **pyproject.toml** - Auto-detected `project.name` and `project.version`
4. **Built-in defaults** - Hardcoded in `config.py`

Implementation pattern:
```python
value = os.getenv("ENV_VAR",                    # Layer 1
         deploy_config.get("toml_key",          # Layer 2
                           default_value))      # Layer 4
# Layer 3 (pyproject.toml) is loaded separately as required base
```

### Architecture Detection

System architecture is normalized to Docker platform format:
- `arm64` or `aarch64` → `linux/arm64`
- `x86_64` or `amd64` → `linux/amd64`

Detected via `uname -m` in `get_platform_architecture()`. Used in `docker build --platform`.

**Cross-compilation example:**
```bash
# Build amd64 image on M1 Mac
DEPLOY_ARCH=linux/amd64 deploy-kit --compose user@host
```

## Backend Implementations

### Compose Backend (SSH-based)

Workflow:
1. Build image locally
2. Save to tarball: `docker save | gzip > dist/{name}-{tag}.tar.gz`
3. SCP transfer: tarball + compose template + .env to `/tmp/` on remote
4. SSH heredoc execution:
   ```bash
   gunzip -c tarball | docker load
   envsubst < template > docker-compose.yml
   docker compose down && docker compose up -d
   ```
5. Cleanup old tarballs (keeps N most recent by mtime)

### Portainer Backend (REST API)

Workflow:
1. Build image locally
2. Query Portainer endpoints: `GET /api/endpoints`
3. Check if stack exists: `GET /api/stacks`
4. Create or update:
   - Create: `POST /api/stacks/create/standalone/string`
   - Update: `PUT /api/stacks/{id}`
5. Sends compose YAML + env vars as JSON (no tarball transfer)

**Authentication**: `X-API-Key` header with `PORTAINER_API_KEY`

## SOPS Integration

Secret decryption workflow:
1. Check if `.env.sops` exists
2. Decrypt to temp file: `sops -d --output-type dotenv .env.sops > /tmp/...`
3. Store path in module-level global `_temp_env_file`
4. Pass temp file path to backend
5. Cleanup via `finally` block in `cli.py`

**Important**: Uses module-level global state in `sops.py` to track temp files across function calls.

## Script Execution Model

All bash scripts are invoked via:
```python
from .scripts import run_script

run_script("script_name.sh", [arg1, arg2, arg3])
```

- Scripts located via `Path(__file__).parent`
- All scripts use `set -euo pipefail` (fail-fast)
- Positional arguments only (no environment variable dependencies in scripts)
- `subprocess.run(check=True)` propagates failures

## Template System

Two substitution mechanisms:

1. **Compose backend**: Uses `envsubst` on remote server
   ```bash
   envsubst < template > docker-compose.yml
   ```

2. **Portainer backend**: Uses Python `string.Template`
   ```python
   Template(compose_content).safe_substitute(env_dict)
   ```

Template search order:
1. Project root: `./docker-compose.prod.yml.template`
2. Deploy-kit templates: `templates/docker/docker-compose.prod.yml.template`

## Development Commands

### Installation Methods

```bash
# Global install (persistent)
uv tool install /path/to/deploy-kit

# Ephemeral run (no install)
uvx --from /path/to/deploy-kit deploy-kit --compose user@host

# Development (editable)
cd deploy-kit
uv pip install -e .
```

### Testing the Tool

```bash
# Test config loading
cd /some/project/with/pyproject.toml
uvx --from /path/to/deploy-kit deploy-kit --help

# Test build (won't deploy)
# Modify cli.py to exit after docker.build_image(cfg)
```

### Integration via Justfile

Projects using deploy-kit as submodule get automatic detection:

```just
# In project's justfile
import? "deploy-kit/justfile.include"

# Auto-detects:
# - If deploy-kit/ exists → uses "uvx --from ./deploy-kit deploy-kit"
# - Otherwise → uses "deploy-kit" (assumes global install)
```

## Key Implementation Details

### Fail-Fast Validation

CLI validates all requirements BEFORE building Docker image:

```python
# Validate backend requirements first
if backend == "compose":
    if not ssh_target:
        raise click.UsageError(...)
elif backend == "portainer":
    if not portainer_url or not portainer_key:
        raise click.UsageError(...)

# Only build after validation passes
docker.build_image(cfg)
```

### Tarball Retention

Cleanup strategy in `docker.py`:
```python
tarballs = sorted(dist.glob(f"{project_name}-*.tar.gz"),
                  key=lambda p: p.stat().st_mtime,
                  reverse=True)
for old in tarballs[keep:]:
    old.unlink()
```

Keeps N most recent by modification time (newest first).

### Error Handling Pattern

Bash scripts use `set -euo pipefail`:
- `-e`: Exit on any command failure
- `-u`: Error on undefined variables
- `-o pipefail`: Fail if any command in pipeline fails

Python propagates via `subprocess.run(check=True)`.

Cleanup guaranteed via `try/finally`:
```python
try:
    if backend == "compose":
        compose.deploy(...)
    elif backend == "portainer":
        portainer.deploy(...)
finally:
    sops.cleanup_temp_files()  # Always runs
```

## Common Patterns to Follow

### Adding a New Configuration Option

1. Add field to `DeployConfig` dataclass in `config.py`
2. Add to `load_config()` with 4-layer precedence:
   ```python
   new_option=os.getenv("DEPLOY_NEW_OPTION",
               deploy_config.get("new_option",
                                 "default_value"))
   ```
3. Update `templates/config/deploy-kit.toml.example`
4. Update README.md with environment variable and config file examples

### Adding a New Bash Script

1. Create script in `src/deploy_kit/scripts/`
2. Add shebang and fail-fast: `#!/usr/bin/env bash\nset -euo pipefail`
3. Use positional arguments (no env vars)
4. Invoke via `run_script("script_name.sh", [args])`

### Modifying Backend Deployment

Both backends implement similar interface:
```python
def deploy(config, env_file, ...):
    # 1. Prepare resources (tarball/API payload)
    # 2. Transfer/send to target
    # 3. Execute deployment
    # 4. Return success/failure
```

Environment file is optional (can be `None`).

## Important Constraints & Gotchas

**Design Limitations:**
- **No unit tests** - Manual testing required
- **Global state in sops.py** - `_temp_env_file` module variable tracks cleanup (makes testing harder)
- **No rollback mechanism** - Failed deployments leave system in intermediate state
- **Configuration is project-local** - Tool must run from project root with `pyproject.toml`

**Deployment Gotchas:**
- **Health checks require curl** - Won't work in minimal images without curl binary
- **Portainer assumes single endpoint** - Uses first endpoint returned by API (usually ID 1)
- **Git required for tags** - Falls back to "latest" but loses image traceability
- **Port mapping** - Internal port hardcoded to 8000 in compose template
- **SOPS temp files** - Brief window where decrypted secrets exist on disk (cleanup in finally block)

**Template Issues:**
- Compose template has `env_file: .env` even when no env file exists (may cause warnings)

## File Structure Notes

```
src/deploy_kit/
├── cli.py              # Click-based CLI, validates BEFORE build
├── config.py           # 4-layer config merge, arch detection
├── docker.py           # Orchestrates bash scripts (build/save/cleanup)
├── sops.py             # Global state for temp file tracking
├── utils.py            # Rich-based logger (info/success/warn/error)
├── backends/
│   ├── compose.py      # SSH + SCP + heredoc deployment
│   └── portainer.py    # REST API deployment
└── scripts/
    ├── __init__.py     # run_script() helper
    ├── docker_build.sh # docker build --platform
    ├── docker_save.sh  # docker save | gzip
    ├── ssh_transfer.sh # scp to /tmp/
    └── ssh_remote_deploy.sh  # gunzip | docker load + compose up
```

Templates are in `templates/`:
- `config/deploy-kit.toml.example` - Configuration template
- `docker/docker-compose.{dev,prod}.yml.template` - Compose templates

## Common Command Examples

```bash
# Basic deployment
deploy-kit --compose user@host.example.com
deploy-kit --portainer https://portainer.example.com

# Override architecture (cross-compile)
DEPLOY_ARCH=linux/amd64 deploy-kit --compose user@host

# Override image tag
IMAGE_TAG=v1.2.3 deploy-kit --compose user@host

# Custom port and healthcheck
DEPLOY_PORT=8001 DEPLOY_HEALTHCHECK_PATH=/health deploy-kit --compose user@host

# SOPS workflow
just sops-encrypt                  # .env → .env.sops
just sops-edit                     # Edit encrypted file
deploy-kit --compose user@host     # Auto-decrypts .env.sops

# Ephemeral execution (no install)
uvx --from ./deploy-kit deploy-kit --compose user@host
```

## Tech Stack

- **Python 3.11+** with Click (CLI), httpx (API client), rich (terminal output)
- **Bash** for Docker CLI operations (`set -euo pipefail` fail-fast pattern)
- **UV** for package management and installation
- **SOPS** for encrypted secret management (optional)
- **Docker** for image building and deployment
- **SSH/SCP** for Compose backend file transfer

## Architecture Evolution

Recent changes:
- **v0.1.0**: Added multi-architecture build support (`--platform` flag)
- **Configuration rename**: `deploy.toml` → `deploy-kit.toml`
- **Invocation simplification**: Removed bash wrapper, use `uvx` or `uv tool install`
- **Justfile auto-detection**: Detects submodule vs global install automatically

## File Locations by Deployment Phase

**Build Phase (local):**
- Input: `./Dockerfile`, `./pyproject.toml`, `./deploy-kit.toml` (optional)
- Output: `./dist/{project}-{tag}.tar.gz`

**Transfer Phase (Compose only):**
- Destination: `/tmp/` on remote server
- Files: tarball, docker-compose.prod.yml.template, .env (if exists)

**Deploy Phase (Compose remote):**
- Working dir: `/tmp/` on remote server
- Generated: `/tmp/docker-compose.yml` (from template via envsubst)
- Runtime: Docker Compose reads `/tmp/.env` and `/tmp/docker-compose.yml`

**Deploy Phase (Portainer):**
- No file transfer - sends compose content and env vars via REST API
- Portainer stores stack config in its database
