# Adding Deploy-Kit to an Existing Project

This guide walks you through integrating deploy-kit into an existing Python project that you want to deploy using either Docker Compose (SSH) or Portainer.

## Prerequisites

Before starting, ensure your project has:

- [x] `pyproject.toml` with `[project]` section containing `name` and `version`
- [x] `Dockerfile` that builds your application
- [x] Python 3.11+ installed locally
- [x] Docker installed locally
- [x] `uv` package manager installed ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))

**For Docker Compose deployments:**
- [x] SSH access to your target server
- [x] Docker and docker-compose installed on remote server

**For Portainer deployments:**
- [x] Portainer instance URL
- [x] Portainer API key ([how to generate](https://docs.portainer.io/api/access))

## Step 1: Add Deploy-Kit to Your Project

Choose your preferred installation method:

### Option A: Git Submodule

Add deploy-kit as a version-controlled dependency:

```bash
cd /path/to/your-project
git submodule add https://github.com/your-org/deploy-kit.git deploy-kit
git submodule update --init --recursive
```

**Benefits:**
- Entire team uses same deploy-kit version
- Version pinned in git
- Easy to update with `git submodule update --remote deploy-kit`

### Option B: Global Install

Install once, use across all projects:

```bash
uv tool install /path/to/deploy-kit
```

This adds `deploy-kit` command to `~/.local/bin/` (automatically added to PATH).

**Benefits:**
- No submodule in your repo
- Single installation for all projects
- Easy to update with `uv tool upgrade deploy-kit`

## Step 2: Create Justfile for Easy Commands

Create a `justfile` in your project root:

```bash
touch justfile
```

Add this line to import deploy-kit recipes (if using the submodule install):

```just
import? "deploy-kit/justfile.include"
```

**If using global install**,  copy the contents of [justfile.include](../justfile.include) manually in your existing `justfile`.


Now you have access to these commands:

```bash
just up-compose user@host.example.com      # Deploy via SSH
just up-portainer https://portainer.url    # Deploy via Portainer
just down-compose user@host.example.com    # Teardown from server
just down-portainer https://portainer.url  # Teardown from Portainer
```

## Step 3: Configure Your Project

### 3.1 Verify pyproject.toml

Ensure your `pyproject.toml` has these required fields:

```toml
[project]
name = "my-app"           # Used as Docker image name
version = "1.0.0"         # Optional, for reference
```

Deploy-kit will auto-detect these values.

### 3.2 Create deploy-kit.toml (Optional)

If you need to override defaults, copy the example config:

```bash
cp deploy-kit/templates/config/deploy-kit.toml.example deploy-kit.toml
```

Edit `deploy-kit.toml` to customize:

```toml
[deploy]
# Deployment targets
ssh_target = "user@host.example.com"           # SSH target for Compose
portainer_url = "https://portainer.example.com" # Portainer URL for API

# Build configuration
port = 8001                          # Override default port (8000)
healthcheck_path = "/api/health"     # Custom health check endpoint
keep_tarballs = 5                    # Keep more old images (default: 3)
architecture = "linux/amd64"         # Force specific platform
```

**Note:** You can also override these via environment variables:
- `DEPLOY_PORT=8001`
- `DEPLOY_HEALTHCHECK_PATH=/api/health`
- `DEPLOY_ARCH=linux/amd64`

### 3.3 Create .env File

Create a `.env` file for environment variables your app needs:

```bash
# .env (example)
DATABASE_URL=postgresql://user:pass@localhost/db
SECRET_KEY=your-secret-key
DEBUG=false
```

**Important:** Add `.env` to `.gitignore` - this file should NEVER be committed!

```bash
echo ".env" >> .gitignore
echo "dist/" >> .gitignore
```

## Step 4: Set Up SOPS for Encrypted Secrets (Recommended)

Instead of git-ignoring `.env`, encrypt it with SOPS so you can commit it safely.

### 4.1 Install SOPS and age

```bash
brew install sops age
```

### 4.2 Generate Encryption Key

```bash
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
```

**Save the public key** shown (starts with `age1...`) - you'll need it next.

### 4.3 Configure SOPS in Your Project

```bash
cp deploy-kit/.sops.yaml.example .sops.yaml
```

Edit `.sops.yaml` and replace `<YOUR_AGE_PUBLIC_KEY>` with your actual key:

```yaml
creation_rules:
  - path_regex: \.env(\.sops)?$
    age: >-
      age1abc123yourpublickeyhere
```

### 4.4 Encrypt Your .env File

```bash
just env-encrypt
```

This creates `.env.sops` - an encrypted version that's safe to commit.

**Now update .gitignore:**

```bash
# Commit encrypted version, ignore plaintext
echo ".env" >> .gitignore
echo ".env.sops" > .gitignore  # Remove if already there
```

Add `.sops.yaml` and `.env.sops` to git:

```bash
git add .sops.yaml .env.sops
git commit -m "feat: add encrypted environment configuration"
```

**SOPS Workflow:**

```bash
just env-edit        # Edit encrypted secrets (opens editor)
just env-decrypt     # Decrypt to .env for local dev (don't commit!)
just env-encrypt     # Re-encrypt after editing plaintext .env
```

Deploy-kit **automatically decrypts** `.env.sops` during deployment.

## Step 5: Customize Docker Compose Template (Optional)

Deploy-kit includes production-ready templates, but you can customize them.

### 5.1 Copy Template to Your Project

```bash
cp deploy-kit/templates/docker/docker-compose.prod.yml.template docker-compose.prod.yml.template
```

### 5.2 Edit the Template

The template uses variable substitution:

```yaml
services:
  ${PROJECT_NAME}:
    image: ${PROJECT_NAME}:${IMAGE_TAG}
    container_name: ${PROJECT_NAME}
    ports:
      - "${PORT}:8000"  # External:Internal
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000${HEALTHCHECK_PATH}"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

**Available variables:**
- `${PROJECT_NAME}` - From `pyproject.toml`
- `${IMAGE_TAG}` - Git short hash or "latest"
- `${PORT}` - From config (default: 8000)
- `${HEALTHCHECK_PATH}` - From config (default: `/`)

**Important:** If your app doesn't run on port 8000 internally, change the right side of the port mapping:

```yaml
ports:
  - "${PORT}:3000"  # If your app listens on port 3000
```

### 5.3 Template Fallback Order

Deploy-kit searches for templates in this order:

1. `./docker-compose.prod.yml.template` (your custom template)
2. `deploy-kit/templates/docker/docker-compose.prod.yml.template` (built-in)

If you create a custom template in your project root, it will be used instead of the default.

## Step 6: Deploy Your Application

### For Docker Compose (SSH) Deployment

**Set your deployment target (choose one method):**

```bash
# Option 1: Via deploy-kit.toml (recommended - persistent config)
# Edit deploy-kit.toml: ssh_target = "user@host.example.com"
deploy-kit --compose

# Option 2: Via environment variable
export DEPLOY_TARGET=user@host.example.com
deploy-kit --compose

# Option 3: Via CLI argument (one-off override)
deploy-kit --compose user@host.example.com
```

**Via justfile:**

```bash
just up-compose user@host.example.com
# Or if ssh_target is set in deploy-kit.toml:
just up-compose
```

**What happens:**

1. Loads configuration from `pyproject.toml` + `deploy-kit.toml`
2. Decrypts `.env.sops` → temporary `.env` (if exists)
3. Builds Docker image: `docker build --platform linux/arm64 -t my-app:abc123 .`
4. Saves image to tarball: `dist/my-app-abc123.tar.gz`
5. SCPs tarball + compose template + .env to remote `/tmp/`
6. SSHs to server and runs:
   ```bash
   gunzip -c /tmp/my-app-abc123.tar.gz | docker load
   envsubst < /tmp/docker-compose.prod.yml.template > /tmp/docker-compose.yml
   docker compose -f /tmp/docker-compose.yml down
   docker compose -f /tmp/docker-compose.yml up -d
   ```
7. Cleans up old tarballs (keeps 3 most recent by default)
8. Cleans up temporary decrypted env file

### For Portainer Deployment

**Set your API credentials:**

```bash
# Option 1: URL in deploy-kit.toml + API key in .env.sops (recommended)
# Edit deploy-kit.toml: portainer_url = "https://portainer.example.com"
# Add to .env.sops: PORTAINER_API_KEY=ptr_xxx...
deploy-kit --portainer

# Option 2: Via environment variables
export PORTAINER_URL=https://portainer.example.com
export PORTAINER_API_KEY=ptr_xxx...
deploy-kit --portainer

# Option 3: Via CLI argument (URL) + env var (API key)
export PORTAINER_API_KEY=ptr_xxx...
deploy-kit --portainer https://portainer.example.com
```

**Via justfile:**

```bash
just up-portainer https://portainer.example.com
# Or if portainer_url is set in deploy-kit.toml:
export PORTAINER_API_KEY=ptr_xxx...  # Still need API key
just up-portainer
```

**What happens:**

1. Loads configuration from `pyproject.toml` + `deploy-kit.toml`
2. Decrypts `.env.sops` → temporary `.env` (if exists)
3. Builds Docker image locally: `docker build --platform linux/arm64 -t my-app:abc123 .`
4. Queries Portainer API for endpoints
5. Checks if stack already exists
6. Creates or updates stack via REST API:
   - Sends compose template content (with variables substituted)
   - Sends environment variables from `.env`
7. Portainer pulls and deploys your image
8. Cleans up temporary decrypted env file

**Note:** Portainer deployment does NOT transfer the image tarball. Your Portainer server must be able to pull the image from a registry, or you need to manually push the image after building.

## Step 7: Teardown

When you need to remove your deployment:

### Docker Compose Teardown

```bash
just down-compose user@host.example.com

# Or direct
deploy-kit --compose user@host.example.com --teardown
```

**What happens:**
- SSHs to remote server
- Runs `docker compose down`
- Removes containers, networks, and volumes
- Cleans up deployment files from `/tmp/`

### Portainer Teardown

```bash
just down-portainer https://portainer.example.com

# Or direct
export PORTAINER_URL=https://portainer.example.com
export PORTAINER_API_KEY=ptr_xxx...
deploy-kit --portainer --teardown
```

**What happens:**
- Queries Portainer API for stack
- Deletes stack via REST API
- Removes containers and networks

## Step 8: Update .gitignore

Ensure these are git-ignored:

```bash
# .gitignore
.env
.venv
dist/
__pycache__/
*.pyc
```

And these are committed:

```bash
git add .sops.yaml .env.sops deploy-kit.toml justfile
git commit -m "feat: add deploy-kit integration"
```

## Common Configuration Patterns

### Cross-Architecture Deployment

Build for x86_64 servers on arm64 Mac:

```bash
DEPLOY_ARCH=linux/amd64 just up-compose user@host
```

Or set permanently in `deploy-kit.toml`:

```toml
[deploy]
architecture = "linux/amd64"
```

### Custom Image Tag

Override the auto-generated git hash tag:

```bash
IMAGE_TAG=v1.2.3 just up-compose user@host
```

### Custom Port

```bash
DEPLOY_PORT=8001 just up-compose user@host
```

Or in `deploy-kit.toml`:

```toml
[deploy]
port = 8001
```

### Custom Health Check

```bash
DEPLOY_HEALTHCHECK_PATH=/api/health just up-compose user@host
```

Or in `deploy-kit.toml`:

```toml
[deploy]
healthcheck_path = "/api/health"
```

## Troubleshooting

### "No such file: pyproject.toml"

Deploy-kit must run from your project root where `pyproject.toml` exists.

```bash
cd /path/to/your-project
deploy-kit --compose user@host
```

### "Permission denied (publickey)"

Your SSH key isn't authorized on the target server.

```bash
ssh-copy-id user@host.example.com
```

### "Health check failed"

Your Docker image doesn't have `curl` installed. Add to Dockerfile:

```dockerfile
RUN apt-get update && apt-get install -y curl
```

Or use a different health check command in your custom `docker-compose.prod.yml.template`.

### "Failed to decrypt .env.sops"

Ensure your age key exists:

```bash
ls ~/.config/sops/age/keys.txt
```

If missing, regenerate and re-encrypt:

```bash
age-keygen -o ~/.config/sops/age/keys.txt
# Update .sops.yaml with new public key
just env-encrypt
```

### Portainer: "Stack not found" or API errors

Check your API key is valid:

```bash
curl -H "X-API-Key: $PORTAINER_API_KEY" \
  "$PORTAINER_URL/api/endpoints"
```

Should return JSON list of endpoints. If unauthorized, regenerate API key in Portainer UI.

## Next Steps

- **Set up CI/CD**: Use deploy-kit in GitHub Actions or GitLab CI
- **Team collaboration**: Share `.sops.yaml` age public key with team members
- **Production secrets**: Store age private key securely (password manager, vault)
- **Monitoring**: Add logging and monitoring to your deployed containers
- **Backups**: Set up regular backups of your deployed data volumes

## Summary Checklist

- [x] Added deploy-kit (submodule or global install)
- [x] Created `justfile` with `import? "deploy-kit/justfile.include"`
- [x] Verified `pyproject.toml` has `[project]` section
- [x] Created `.env` file (git-ignored)
- [x] Set up SOPS encryption (optional but recommended)
- [x] Customized `deploy-kit.toml` (optional)
- [x] Customized compose template (optional)
- [x] Updated `.gitignore`
- [x] Deployed successfully with `just up-compose` or `just up-portainer`
- [x] Verified deployment with health checks

Your existing project is now deploy-kit ready! 🚀
