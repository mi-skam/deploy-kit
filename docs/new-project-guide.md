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
git branch -m main  # Rename to main (recommended)
```

## Step 2: Initialize Python Project with uv

```bash
uv init
```

This creates:
- `pyproject.toml` - Project metadata
- `.python-version` - Python version specification
- `README.md` - Basic readme
- `main.py` - Sample application file

## Step 3: Configure pyproject.toml

Edit `pyproject.toml` to include required fields for deploy-kit:

```toml
[project]
name = "my-app"                # Required: Docker image name
version = "0.1.0"              # Optional: version tracking
description = "My application"
readme = "README.md"
requires-python = ">=3.13"     # Matches uv init default
dependencies = [
    # Your app dependencies here, e.g.:
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/my_app"]      # Required: tells hatchling where to find your package
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
FROM python:3.13-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files (README.md required by hatchling)
COPY pyproject.toml README.md ./

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

# Set PYTHONPATH so module can be imported
ENV PYTHONPATH=/app/src

# Run application
CMD ["uvicorn", "my_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key points:**
- Install `curl` for health checks
- Internal port should match what's in compose template (default: 8000)
- Adjust CMD to match your app's entry point

## Step 6: Add Deploy-Kit to Your Project

### Option A: Global Install (Recommended)

Install deploy-kit from GitHub:

```bash
uv tool install --from git+https://github.com/mi-skam/deploy-kit deploy-kit
```

Verify installation:

```bash
deploy-kit --version  # Should show 0.2.3 or higher
```

### Option B: Git Submodule (For Teams)

If you prefer to version-control deploy-kit with your project:

```bash
git submodule add https://github.com/mi-skam/deploy-kit.git deploy-kit
git submodule update --init --recursive
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

## Step 7.5: Install Dependencies for Local Development

Before you can run the development server, install your project dependencies:

```bash
# Create virtual environment and install in editable mode
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

This installs your app in "editable" mode, meaning:
- Code changes are immediately available without reinstalling
- The `my_app` module is importable from anywhere
- All dependencies from `pyproject.toml` are installed

**Verify installation:**

```bash
# Test that uvicorn can import your app
python -c "from my_app.main import app; print('✓ Import successful')"
```

Now you can run the development server:

```bash
just dev  # Starts uvicorn with hot-reload
```

## Step 8: Configure Deploy-Kit

### 8.1 Create deploy-kit.toml

```bash
cp deploy-kit/templates/config/deploy-kit.toml.example deploy-kit.toml
```

Edit to customize (all optional):

```toml
[deploy]
# Deployment targets (choose based on your backend)
ssh_target = "user@host.example.com"           # For Compose backend
portainer_url = "https://portainer.example.com" # For Portainer backend

# Build configuration
port = 8000
healthcheck_path = "/health"
keep_tarballs = 3

# Architecture (uncomment if needed for cross-platform deployment)
# architecture = "linux/amd64"   # For x86_64 servers (most common)
# architecture = "linux/arm64"   # For ARM servers (Raspberry Pi, AWS Graviton)
```

**Cross-platform builds:** If you're building on M1/M2 Mac (ARM) but deploying to x86_64 servers, uncomment and set `architecture = "linux/amd64"` to avoid platform mismatch warnings.

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

## Step 10: Add Docker Compose Template (Required for Deployment)

For deployment to work, you need the docker-compose template file:

**Option A: Use default template (recommended for most projects)**

```bash
# Copy the default template from deploy-kit
cp deploy-kit/templates/docker/docker-compose.prod.yml.template ./
```

**Option B: Customize the template**

If you need custom deployment configuration (additional services, volumes, etc.):

```bash
cp deploy-kit/templates/docker/docker-compose.prod.yml.template docker-compose.prod.yml.template
# Then edit as needed
```

**Note:** If you installed deploy-kit globally (Option A in Step 6), the template path would be different. In that case, you can download it:

```bash
curl -O https://raw.githubusercontent.com/mi-skam/deploy-kit/main/templates/docker/docker-compose.prod.yml.template
```

See [existing project guide](existing-project-guide.md#step-5-customize-docker-compose-template-optional) for customization details.

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
# Option 1: Using deploy-kit.toml (if ssh_target is set)
deploy-kit --compose
just up-compose

# Option 2: Using environment variable
export DEPLOY_TARGET=user@host.example.com
deploy-kit --compose

# Option 3: Via CLI argument
deploy-kit --compose user@host.example.com
just up-compose user@host.example.com
```

### Portainer Deployment

```bash
# Option 1: Using deploy-kit.toml + .env.sops (if portainer_url is set)
# PORTAINER_API_KEY should be in .env.sops
deploy-kit --portainer
just up-portainer

# Option 2: Using environment variables
export PORTAINER_URL=https://portainer.example.com
export PORTAINER_API_KEY=ptr_xxx...
deploy-kit --portainer

# Option 3: Via CLI argument + env var
export PORTAINER_API_KEY=ptr_xxx...
deploy-kit --portainer https://portainer.example.com
just up-portainer https://portainer.example.com
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

### Common Issues

**Port already in use during deployment:**

If deployment fails with "port is already allocated":

1. **Change the port** in `deploy-kit.toml`:
   ```toml
   port = 8001  # or any free port
   ```

2. **Or stop the conflicting service** on the remote server:
   ```bash
   ssh user@host "docker ps"  # Find the container using the port
   ssh user@host "docker stop <container-name>"
   ```

**Docker build fails with "Readme file does not exist":**

Make sure your Dockerfile includes:
```dockerfile
COPY pyproject.toml README.md ./
```

**Runtime error: "ModuleNotFoundError: No module named 'my_app'":**

Add to your Dockerfile before the CMD:
```dockerfile
ENV PYTHONPATH=/app/src
```

**Development server won't start (command not found):**

Install dependencies first:
```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

**Platform mismatch warning during deployment:**

If building on ARM Mac but deploying to x86_64 server, add to `deploy-kit.toml`:
```toml
architecture = "linux/amd64"
```

See [existing project guide troubleshooting section](existing-project-guide.md#troubleshooting) for more issues and solutions.

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

- [ ] Created project directory and initialized git with main branch
- [ ] Initialized Python project with `uv init`
- [ ] Configured `pyproject.toml` with:
  - [ ] `readme = "README.md"`
  - [ ] `requires-python = ">=3.13"`
  - [ ] Dependencies (fastapi, uvicorn, etc.)
  - [ ] `[tool.hatch.build.targets.wheel]` with packages
- [ ] Created application code in `src/my_app/`
- [ ] Created production `Dockerfile` with:
  - [ ] `COPY pyproject.toml README.md ./`
  - [ ] `ENV PYTHONPATH=/app/src`
- [ ] Installed deploy-kit globally (`uv tool install`)
- [ ] Created `justfile` with deploy-kit integration
- [ ] Installed local dependencies (`uv pip install -e .`)
- [ ] Configured `deploy-kit.toml` (ssh_target or portainer_url)
- [ ] Added docker-compose template (required for deployment)
- [ ] Set up SOPS encryption for secrets (optional)
- [ ] Created `.gitignore`
- [ ] Tested Docker build locally
- [ ] Made initial git commit
- [ ] Deployed successfully

Your new project is ready for development and deployment! 🚀
