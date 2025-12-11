#!/usr/bin/env python3
"""Project initialization logic for deploy-kit."""

import os
import shutil
from pathlib import Path
from typing import Optional

from .utils import logger


def init_project(
    project_name: str,
    description: str = "A new Python application",
    python_version: str = "3.13",
    port: int = 8000,
) -> None:
    """Initialize a new project with deploy-kit configuration.
    
    Args:
        project_name: Name of the project (used for docker image, directories)
        description: Project description for pyproject.toml
        python_version: Python version to use (default: 3.13)
        port: Port for the application (default: 8000)
    """
    current_dir = Path.cwd()
    
    # Check if directory is empty (except for hidden files like .git)
    visible_files = [f for f in os.listdir(current_dir) if not f.startswith('.')]
    if visible_files:
        raise FileExistsError(
            f"Directory {current_dir} is not empty. "
            "Please run 'deploy-kit init' in an empty directory."
        )
    
    logger.info(f"Initializing project: {project_name}")
    
    # Create directory structure
    create_directory_structure(current_dir, project_name)
    
    # Create configuration files
    create_pyproject_toml(current_dir, project_name, description, python_version)
    create_deploy_kit_toml(current_dir, port)
    create_dockerfile(current_dir, project_name, python_version, port)
    create_docker_compose_template(current_dir)
    create_gitignore(current_dir)
    create_justfile(current_dir, project_name)
    create_sops_yaml(current_dir)
    create_env_example(current_dir)
    
    # Create application files
    create_app_files(current_dir, project_name)
    
    # Create README
    create_readme(current_dir, project_name)
    
    logger.success(f"✓ Project {project_name} initialized successfully!")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Install dependencies:")
    logger.info("     uv venv && source .venv/bin/activate")
    logger.info("     uv pip install -e .")
    logger.info("")
    logger.info("  2. Test locally:")
    logger.info("     just dev")
    logger.info("")
    logger.info("  3. Build Docker image:")
    logger.info("     docker build -t {}-test .".format(project_name))
    logger.info("")
    logger.info("  4. Deploy:")
    logger.info("     deploy-kit up --compose user@host")


def create_directory_structure(base_dir: Path, project_name: str) -> None:
    """Create the basic directory structure."""
    module_name = project_name.replace("-", "_")
    
    (base_dir / "src" / module_name).mkdir(parents=True, exist_ok=True)
    logger.info(f"Created directory: src/{module_name}/")


def create_pyproject_toml(
    base_dir: Path, project_name: str, description: str, python_version: str
) -> None:
    """Create pyproject.toml with basic configuration."""
    module_name = project_name.replace("-", "_")
    
    content = f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "{description}"
readme = "README.md"
requires-python = ">={python_version}"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{module_name}"]
"""
    
    (base_dir / "pyproject.toml").write_text(content)
    logger.info("Created: pyproject.toml")


def create_deploy_kit_toml(base_dir: Path, port: int) -> None:
    """Create deploy-kit.toml configuration file."""
    content = f"""# Deploy-kit configuration

[deploy]
# Override default port (default: 8000)
port = {port}

# Custom healthcheck path (default: /)
healthcheck_path = "/health"

# Number of old tarballs to keep (default: 3)
keep_tarballs = 3

# SSH target for Compose backend (alternatively use DEPLOY_TARGET env var or CLI arg)
# ssh_target = "deploy@production.example.com"

# Portainer URL for API backend (alternatively use PORTAINER_URL env var or CLI arg)
# portainer_url = "https://portainer.example.com"
"""
    
    (base_dir / "deploy-kit.toml").write_text(content)
    logger.info("Created: deploy-kit.toml")


def create_dockerfile(
    base_dir: Path, project_name: str, python_version: str, port: int
) -> None:
    """Create a production-ready Dockerfile."""
    module_name = project_name.replace("-", "_")
    
    content = f"""FROM python:{python_version}-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files (README.md required by hatchling)
COPY pyproject.toml README.md ./

# Install dependencies
RUN pip install --no-cache-dir uv && \\
    uv pip install --system --no-cache .

# Copy application code
COPY src/ ./src/

# Expose port
EXPOSE {port}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
  CMD curl -f http://localhost:{port}/health || exit 1

# Set PYTHONPATH so module can be imported
ENV PYTHONPATH=/app/src

# Run application
CMD ["uvicorn", "{module_name}.main:app", "--host", "0.0.0.0", "--port", "{port}"]
"""
    
    (base_dir / "Dockerfile").write_text(content)
    logger.info("Created: Dockerfile")


def create_docker_compose_template(base_dir: Path) -> None:
    """Create docker-compose.prod.yml.template."""
    deploy_kit_dir = Path(__file__).parent.parent.parent
    template_path = (
        deploy_kit_dir / "templates" / "docker" / "docker-compose.prod.yml.template"
    )
    
    if template_path.exists():
        content = template_path.read_text()
    else:
        # Fallback template
        content = """name: ${PROJECT_NAME}

services:
  ${PROJECT_NAME}:
    image: ${PROJECT_NAME}:${IMAGE_TAG}
    container_name: ${PROJECT_NAME}
    env_file:
      - .env
    ports:
      - "${PORT}:8000"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000${HEALTHCHECK_PATH}"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
"""
    
    (base_dir / "docker-compose.prod.yml.template").write_text(content)
    logger.info("Created: docker-compose.prod.yml.template")


def create_gitignore(base_dir: Path) -> None:
    """Create .gitignore with sensible defaults."""
    content = """# Environment
.env
.venv
venv/

# Deploy-kit
dist/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# IDE
.vscode/
.idea/
*.swp
*.swo
.DS_Store

# Logs
*.log
"""
    
    (base_dir / ".gitignore").write_text(content)
    logger.info("Created: .gitignore")


def create_justfile(base_dir: Path, project_name: str) -> None:
    """Create justfile with deploy-kit integration."""
    module_name = project_name.replace("-", "_")
    
    content = f"""import? "deploy-kit/justfile.include"

# Development server with hot reload
[group('development')]
dev:
    uvicorn {module_name}.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
[group('testing')]
test:
    pytest tests/

# Build Docker image locally
[group('docker')]
build:
    docker build -t {project_name}:latest .

# Run Docker container locally
[group('docker')]
run:
    docker run -p 8000:8000 --env-file .env {project_name}:latest
"""
    
    (base_dir / "justfile").write_text(content)
    logger.info("Created: justfile")


def create_sops_yaml(base_dir: Path) -> None:
    """Create .sops.yaml.example for SOPS configuration."""
    deploy_kit_dir = Path(__file__).parent.parent.parent
    template_path = deploy_kit_dir / ".sops.yaml.example"
    
    if template_path.exists():
        content = template_path.read_text()
    else:
        # Fallback template
        content = """# SOPS configuration for encrypted secrets
#
# Setup:
# 1. Install: brew install sops age
# 2. Generate key: age-keygen -o ~/.config/sops/age/keys.txt
# 3. Replace <YOUR_AGE_PUBLIC_KEY> with your public key
# 4. Encrypt: just env-encrypt

creation_rules:
  - path_regex: \\.env(\\.sops)?$
    age: >-
      <YOUR_AGE_PUBLIC_KEY>
"""
    
    (base_dir / ".sops.yaml.example").write_text(content)
    logger.info("Created: .sops.yaml.example")


def create_env_example(base_dir: Path) -> None:
    """Create .env.example with common environment variables."""
    content = """# Application settings
DEBUG=true
LOG_LEVEL=info

# Database (example)
# DATABASE_URL=postgresql://user:pass@localhost/myapp

# External APIs (example)
# API_KEY=your-api-key-here

# For Portainer deployments
# PORTAINER_API_KEY=ptr_xxx...
"""
    
    (base_dir / ".env.example").write_text(content)
    logger.info("Created: .env.example")


def create_app_files(base_dir: Path, project_name: str) -> None:
    """Create basic FastAPI application files."""
    module_name = project_name.replace("-", "_")
    app_dir = base_dir / "src" / module_name
    
    # __init__.py
    (app_dir / "__init__.py").write_text(f'""""{project_name} application."""\n')
    
    # main.py with basic FastAPI app
    main_content = """from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
"""
    
    (app_dir / "main.py").write_text(main_content)
    logger.info(f"Created: src/{module_name}/__init__.py")
    logger.info(f"Created: src/{module_name}/main.py")


def create_readme(base_dir: Path, project_name: str) -> None:
    """Create README.md with getting started instructions."""
    module_name = project_name.replace("-", "_")
    
    content = f"""# {project_name}

A Python application created with deploy-kit.

## Quick Start

### Local Development

1. **Install dependencies:**
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
   uv pip install -e .
   ```

2. **Run development server:**
   ```bash
   just dev
   ```

3. **Test the application:**
   ```bash
   curl http://localhost:8000/
   curl http://localhost:8000/health
   ```

### Docker

1. **Build image:**
   ```bash
   docker build -t {project_name}:latest .
   ```

2. **Run container:**
   ```bash
   docker run -p 8000:8000 {project_name}:latest
   ```

### Deployment

#### Docker Compose (SSH)

```bash
# Configure target in deploy-kit.toml or use environment variable
export DEPLOY_TARGET=user@host.example.com

# Deploy
deploy-kit up --compose
# or
just up-compose user@host.example.com
```

#### Portainer

```bash
# Configure in deploy-kit.toml and set API key
export PORTAINER_URL=https://portainer.example.com
export PORTAINER_API_KEY=ptr_xxx...

# Deploy
deploy-kit up --portainer
# or
just up-portainer https://portainer.example.com
```

## Configuration

### Environment Variables

Create `.env` file for local development:

```bash
cp .env.example .env
# Edit .env with your configuration
```

### Encrypted Secrets (Production)

For production deployments, use SOPS to encrypt secrets:

1. **Setup SOPS:**
   ```bash
   brew install sops age
   age-keygen -o ~/.config/sops/age/keys.txt
   ```

2. **Configure:**
   ```bash
   cp .sops.yaml.example .sops.yaml
   # Edit .sops.yaml and add your age public key
   ```

3. **Encrypt secrets:**
   ```bash
   cp .env.example .env
   # Edit .env with production secrets
   just env-encrypt
   # This creates .env.sops which is safe to commit
   ```

## Project Structure

```
{project_name}/
├── src/
│   └── {module_name}/
│       ├── __init__.py
│       └── main.py
├── pyproject.toml
├── Dockerfile
├── docker-compose.prod.yml.template
├── deploy-kit.toml
├── justfile
├── .env.example
├── .sops.yaml.example
└── README.md
```

## Available Commands

```bash
# Development
just dev                    # Start development server

# Docker
just build                  # Build Docker image
just run                    # Run Docker container

# Deployment
just up-compose <target>    # Deploy via SSH
just up-portainer <url>     # Deploy via Portainer
just down-compose <target>  # Teardown from server
just down-portainer <url>   # Teardown from Portainer

# Secrets (SOPS)
just env-encrypt            # Encrypt .env -> .env.sops
just env-decrypt            # Decrypt .env.sops -> .env
just env-edit               # Edit encrypted secrets
```

## Learn More

- [Deploy-kit Documentation](https://github.com/mi-skam/deploy-kit)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)

## License

MIT
"""
    
    (base_dir / "README.md").write_text(content)
    logger.info("Created: README.md")
