# Creating a New Project with Deploy-Kit

This guide walks you through creating a new Python project from scratch with deploy-kit integration built-in.

## What's Different from Adding to Existing Projects?

This guide covers the **complete setup** including:
- Creating project structure from scratch
- Setting up `pyproject.toml`
- Creating a basic `Dockerfile`
- Initializing git repository

If you already have a Python project with `pyproject.toml` and `Dockerfile`, see [Adding Deploy-Kit to an Existing Project](existing-project-guide.md) instead.

## Prerequisites

Ensure you have installed:

- [x] Python 3.11+ ([download](https://www.python.org/downloads/))
- [x] Docker ([download](https://www.docker.com/get-started))
- [x] `uv` package manager ([installation](https://docs.astral.sh/uv/getting-started/installation/))
- [x] Git ([download](https://git-scm.com/downloads))

**For Docker Compose deployments:**
- [x] SSH access to target server
- [x] Docker and docker-compose on remote server

**For Portainer deployments:**
- [x] Portainer instance URL
- [x] Portainer API key

## Step 1: Create Project Directory

```bash
mkdir my-app
cd my-app
git init
```

## Step 2: Initialize Python Project with uv

```bash
uv init
```

This creates:
- `pyproject.toml` - Project metadata
- `.python-version` - Python version specification
- `README.md` - Basic readme
- `.gitignore` - Python-specific ignores

## Step 3: Configure pyproject.toml

Edit `pyproject.toml` to include required fields for deploy-kit:

```toml
[project]
name = "my-app"                # Required: Docker image name
version = "0.1.0"              # Optional: version tracking
description = "My application"
requires-python = ">=3.11"
dependencies = [
    # Your app dependencies here, e.g.:
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Important fields for deploy-kit:**
- `project.name` → Used as Docker image name
- `project.version` → Optional, for reference

## Step 4: Create Your Application

Create a simple application structure:

```bash
mkdir -p src/my_app
touch src/my_app/__init__.py
touch src/my_app/main.py
```

Example `src/my_app/main.py` (FastAPI app):

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

## Step 5: Create Dockerfile

Create a production-ready `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

# Copy application code
COPY src/ ./src/

# Expose port (must match docker-compose template)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "my_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key points:**
- Install `curl` for health checks
- Internal port should match what's in compose template (default: 8000)
- Adjust CMD to match your app's entry point

## Step 6: Add Deploy-Kit to Your Project

### Option A: Git Submodule (Recommended for Teams)

```bash
git submodule add https://github.com/your-org/deploy-kit.git deploy-kit
git submodule update --init --recursive
```

### Option B: Global Install (Recommended for Personal Projects)

```bash
uv tool install /path/to/deploy-kit
```

See [existing project guide](existing-project-guide.md#step-1-add-deploy-kit-to-your-project) for detailed comparison.

## Step 7: Create Justfile

Create `justfile` for easy command access:

```just
import? "deploy-kit/justfile.include"

# Development
dev:
    uvicorn my_app.main:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
    pytest tests/

# Local Docker build
build:
    docker build -t my-app:latest .

# Local Docker run
run:
    docker run -p 8000:8000 --env-file .env my-app:latest
```

Now you have access to both your custom recipes and deploy-kit recipes:

```bash
just dev                    # Your custom recipe
just up-compose user@host   # Deploy-kit recipe
```

## Step 8: Configure Deploy-Kit

### 8.1 Create deploy-kit.toml

```bash
cp deploy-kit/templates/config/deploy-kit.toml.example deploy-kit.toml
```

Edit to customize (all optional):

```toml
[deploy]
port = 8000
healthcheck_path = "/health"
keep_tarballs = 3
# architecture = "linux/amd64"  # Uncomment to force platform
```

### 8.2 Create Environment Files

Create `.env` for local development:

```bash
cat > .env <<EOF
# Database
DATABASE_URL=postgresql://user:pass@localhost/myapp

# App settings
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=true
LOG_LEVEL=debug

# External APIs
API_KEY=your-api-key
EOF
```

### 8.3 Set Up SOPS for Production Secrets

Install SOPS and age:

```bash
brew install sops age
```

Generate encryption key:

```bash
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
```

**Save the public key** displayed (starts with `age1...`).

Configure SOPS:

```bash
cp deploy-kit/.sops.yaml.example .sops.yaml
```

Edit `.sops.yaml` and replace `<YOUR_AGE_PUBLIC_KEY>`:

```yaml
creation_rules:
  - path_regex: \.env(\.sops)?$
    age: >-
      age1your_public_key_here
```

Encrypt your environment file:

```bash
just env-encrypt
```

This creates `.env.sops` which is safe to commit.

## Step 9: Update .gitignore

Ensure proper files are ignored:

```bash
cat >> .gitignore <<EOF
# Environment
.env
.venv

# Deploy-kit
dist/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so

# Testing
.pytest_cache/
.coverage
htmlcov/

# IDE
.vscode/
.idea/
*.swp
*.swo
EOF
```

## Step 10: Create Docker Compose Template (Optional)

If you need custom deployment configuration, create a custom template:

```bash
cp deploy-kit/templates/docker/docker-compose.prod.yml.template docker-compose.prod.yml.template
```

Edit as needed. See [existing project guide](existing-project-guide.md#step-5-customize-docker-compose-template-optional) for details.

## Step 11: Test Locally

Before deploying, test your Docker setup locally:

```bash
# Build image
docker build -t my-app:test .

# Run container
docker run -p 8000:8000 --env-file .env my-app:test

# Test in another terminal
curl http://localhost:8000/
curl http://localhost:8000/health
```

## Step 12: Initial Git Commit

Commit your project structure:

```bash
git add .
git commit -m "feat: initial project setup with deploy-kit"
```

**Files committed:**
- `pyproject.toml`
- `Dockerfile`
- `justfile`
- `src/` (application code)
- `deploy-kit.toml`
- `.sops.yaml`
- `.env.sops` (encrypted)
- `.gitignore`

**Files NOT committed:**
- `.env` (plaintext secrets)
- `dist/` (tarballs)
- `.venv/` (virtual environment)

## Step 13: Deploy Your Application

### Docker Compose (SSH) Deployment

```bash
# Set target
export DEPLOY_TARGET=user@host.example.com

# Deploy
just up-compose user@host.example.com

# Or direct command
deploy-kit --compose user@host.example.com
```

### Portainer Deployment

```bash
# Set credentials
export PORTAINER_URL=https://portainer.example.com
export PORTAINER_API_KEY=ptr_xxx...

# Deploy
just up-portainer https://portainer.example.com

# Or direct command
deploy-kit --portainer https://portainer.example.com
```

See [existing project guide](existing-project-guide.md#step-6-deploy-your-application) for detailed deployment workflow explanation.

## Step 14: Verify Deployment

Check your application is running:

```bash
# For Compose deployment
ssh user@host.example.com "docker ps"
curl http://host.example.com:8000/health

# For Portainer deployment
# Check in Portainer UI or use API
curl https://your-app-url.com/health
```

## Project Structure Summary

Your final project structure:

```
my-app/
├── src/
│   └── my_app/
│       ├── __init__.py
│       └── main.py
├── tests/
│   └── test_main.py
├── deploy-kit/              # Git submodule (if using)
├── pyproject.toml          # Project metadata (required)
├── Dockerfile              # Container definition (required)
├── justfile                # Task runner with deploy-kit integration
├── deploy-kit.toml         # Deploy-kit config overrides (optional)
├── .env                    # Local dev secrets (git-ignored)
├── .env.sops               # Encrypted secrets (committed)
├── .sops.yaml              # SOPS configuration (committed)
├── .gitignore              # Git ignore rules
├── .python-version         # Python version pin
└── README.md               # Project documentation
```

## Development Workflow

Daily development flow:

```bash
# Local development with hot reload
just dev

# Run tests
just test

# Build and test locally
just build
just run

# Update dependencies
uv add requests
uv sync

# Deploy to production
just env-edit                    # Update secrets
just up-compose user@host        # Deploy
```

## Team Collaboration with SOPS

### Adding Team Members

1. **Team member generates their key:**
   ```bash
   age-keygen -o ~/.config/sops/age/keys.txt
   ```

2. **They share their public key** (starts with `age1...`)

3. **You add their key to `.sops.yaml`:**
   ```yaml
   creation_rules:
     - path_regex: \.env(\.sops)?$
       age: >-
         age1your_key_here,
         age1teammate_key_here
   ```

4. **Re-encrypt with new recipients:**
   ```bash
   just env-decrypt     # Decrypt with your key
   just env-encrypt     # Re-encrypt for all recipients
   git add .env.sops .sops.yaml
   git commit -m "feat: add teammate to SOPS recipients"
   ```

Now both of you can decrypt `.env.sops`!

## Next Steps

- **Add tests**: Create `tests/` directory with pytest
- **CI/CD**: Set up GitHub Actions or GitLab CI
- **Database**: Add PostgreSQL or other services to compose template
- **Monitoring**: Add logging, metrics, and alerting
- **Documentation**: Expand README.md with API docs
- **Production secrets**: Store age private key in password manager

## Troubleshooting

See [existing project guide troubleshooting section](existing-project-guide.md#troubleshooting) for common issues and solutions.

## Example Projects

Check out these example projects using deploy-kit:

```bash
# FastAPI example
git clone https://github.com/your-org/deploy-kit-example-fastapi

# Django example
git clone https://github.com/your-org/deploy-kit-example-django

# Flask example
git clone https://github.com/your-org/deploy-kit-example-flask
```

## Summary Checklist

- [x] Created project directory and initialized git
- [x] Initialized Python project with `uv init`
- [x] Configured `pyproject.toml` with name and dependencies
- [x] Created application code in `src/`
- [x] Created production `Dockerfile`
- [x] Added deploy-kit (submodule or global)
- [x] Created `justfile` with deploy-kit integration
- [x] Configured `deploy-kit.toml` (optional)
- [x] Set up SOPS encryption for secrets
- [x] Updated `.gitignore`
- [x] Tested Docker build locally
- [x] Made initial git commit
- [x] Deployed successfully

Your new project is ready for development and deployment! 🚀
