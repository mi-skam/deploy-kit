# Deploy-Kit

Reusable Docker deployment toolkit for containerized applications with support for Docker Compose (SSH) and Portainer API backends.

## Features

Works with Docker Compose over SSH or Portainer's API. If you're deploying Python projects with `pyproject`.toml, it picks up the config automatically. Handles multi-arch builds (arm64/amd64) based on what you're running, though you can override that. When it finds `.env.sops` files, it decrypts them. Includes health check setup and cleans up old image tarballs. The Python code handles orchestration while bash scripts do the actual work. You can install it with uv tool, direnv, or just add it to your PATH.

## Getting Started

New to deploy-kit? Start with one of these guides:

- **[Adding Deploy-Kit to an Existing Project](docs/existing-project-guide.md)** - Step-by-step integration guide for existing Python projects
- **[Creating a New Project with Deploy-Kit](docs/new-project-guide.md)** - Complete setup guide for new projects from scratch

Quick reference sections:
- [Installation](#installation) - Different installation methods
- [Usage](#usage) - Command-line examples
- [Configuration](#configuration) - Config file and environment variables
- [SOPS Integration](#sops-integration) - Encrypted secrets management

## Installation

Choose based on your workflow:

### Option 1: Global install (recommended for personal machines)

Install once, use everywhere:

```bash
uv tool install /path/to/deploy-kit
```

This installs `deploy-kit` to `~/.local/bin/` (added to PATH automatically via `uv tool update-shell`).

### Option 2: Project submodule (recommended for teams/repos)

Add as git submodule for version-controlled deployment config:

```bash
git submodule add https://github.com/your-org/deploy-kit.git deploy-kit
```

No installation needed - `justfile.include` auto-detects and uses `uvx --from ./deploy-kit`.

### Option 3: Ephemeral/direct use (nix shells, direnv, CI)

Run without installing:

```bash
uvx --from /path/to/deploy-kit deploy-kit --compose user@host
```

Works in any environment with `uv` available.

## Usage

Deploy-kit requires explicit backend selection via command-line flags.

### Docker Compose deployment (SSH)

Deploy to a remote server via SSH and docker-compose:

```bash
# With explicit target
deploy-kit --compose user@host.example.com
deploy-kit -c user@host.example.com

# Via environment variable
export DEPLOY_TARGET=user@host.example.com
deploy-kit --compose
```

### Portainer deployment (API)

Deploy to Portainer via REST API:

```bash
# With explicit URL
export PORTAINER_API_KEY=ptr_xxx...
deploy-kit --portainer https://portainer.example.com
deploy-kit -p https://portainer.example.com

# Via environment variables
export PORTAINER_URL=https://portainer.example.com
export PORTAINER_API_KEY=ptr_xxx...
deploy-kit --portainer
```

### Via just recipes

```just
import? "deploy-kit/justfile.include"

# Deployment
just up-compose user@host           # Compose with SSH
just up-portainer https://url       # Portainer with API

# Teardown
just down-compose user@host         # Full cleanup
just down-portainer https://url     # Remove Portainer stack
```

### Deployment workflow

Both backends follow this pipeline:

1. Load configuration from `pyproject.toml` + `deploy-kit.toml`
2. Detect and decrypt env file (`.env.sops` → `.env` or use `.env` directly)
3. Build Docker image for target architecture
4. Deploy using selected backend:
   - **Compose**: Save as tarball → SCP transfer → SSH remote load & compose up
   - **Portainer**: Create/update stack via REST API
5. Cleanup old tarballs and temporary files

## Configuration

Deploy-kit reads configuration from your project's `pyproject.toml` and optional `deploy-kit.toml`:

**Auto-detected from pyproject.toml:**
- `project.name` → Docker image name
- `project.version` → Project version

**Optional deploy-kit.toml overrides:**

```toml
[deploy]
port = 8001
healthcheck_path = "/health"
keep_tarballs = 5
architecture = "linux/amd64"
```

**Environment variable overrides:**

Configuration:
- `DEPLOY_PORT` - Override service port (default: 8000)
- `DEPLOY_HEALTHCHECK_PATH` - Override health check path (default: `/`)
- `DEPLOY_ARCH` - Override target architecture (default: auto-detected, options: `linux/arm64`, `linux/amd64`)
- `IMAGE_TAG` - Override image tag (default: git short hash, fallback: `latest`)

Deployment:
- `DEPLOY_TARGET` - SSH target for Compose backend (e.g., `user@host.example.com`)
- `PORTAINER_URL` - Portainer API URL (e.g., `https://portainer.example.com`)
- `PORTAINER_API_KEY` - Portainer API key (required for Portainer backend)

**Configuration precedence (highest to lowest):**
1. Environment variables
2. `deploy-kit.toml` overrides
3. `pyproject.toml` auto-detection
4. Built-in defaults

## Multi-Architecture Builds

Deploy-kit supports building Docker images for different CPU architectures, enabling cross-platform deployments (e.g., building on M1 Mac for x86_64 servers).

**Automatic detection:**
```bash
deploy-kit --compose user@host  # Auto-detects system architecture
# arm64/aarch64 → linux/arm64
# x86_64/amd64 → linux/amd64
```

**Override via environment variable:**
```bash
# Build for x86_64 on arm64 Mac
DEPLOY_ARCH=linux/amd64 deploy-kit --compose user@host
```

**Override via config file:**
```toml
[deploy]
architecture = "linux/amd64"  # Always build for amd64
```

**Supported architectures:**
- `linux/arm64` - ARM 64-bit (Raspberry Pi, M1/M2 Macs, AWS Graviton)
- `linux/amd64` - x86_64 (Traditional servers, Intel/AMD CPUs)

## SOPS Integration

Deploy-kit automatically detects and decrypts `.env.sops` files during deployment.

### Setup (one-time)

1. **Install SOPS and age**:
   ```bash
   brew install sops age
   ```

2. **Generate your age encryption key**:
   ```bash
   age-keygen -o ~/.config/sops/age/keys.txt
   # Save the public key shown (starts with age1...)
   ```

3. **Configure SOPS in your project**:
   ```bash
   cp deploy-kit/.sops.yaml.example .sops.yaml
   # Edit .sops.yaml and replace <YOUR_AGE_PUBLIC_KEY> with your key
   ```

### Usage

**Encrypt secrets**:
```bash
just sops-encrypt     # .env → .env.sops
```

**Edit encrypted secrets**:
```bash
just sops-edit        # Opens editor with decrypted content
```

**Decrypt for local dev**:
```bash
just sops-decrypt     # .env.sops → .env (don't commit!)
```

**Deploy** (auto-decrypts):
```bash
deploy-kit --compose user@host     # Auto-decrypts .env.sops
deploy-kit --portainer https://...  # Works with both backends
```

### How it works

1. Deploy-kit detects `.env.sops` in project root
2. Decrypts to temporary file using `sops -d --output-type dotenv`
3. Passes temporary file to deployment backend
4. Cleans up temporary file after deployment (even on failure)
5. Falls back to `.env` if `.env.sops` doesn't exist
6. Can deploy without any env file (optional)

**Security best practices**:
- ✅ **Commit**: `.env.sops`, `.sops.yaml`
- ❌ **Never commit**: `.env`, `~/.config/sops/age/keys.txt`
- Add `.env` to your `.gitignore`
- Share age public keys with team members for collaboration
- Store private keys (`~/.config/sops/age/keys.txt`) securely (backup to password manager)

## Requirements

**System requirements:**
- Python 3.11+
- Docker (for building images)
- SSH + SCP (for Compose backend)
- Git (for automatic image tagging)

**Optional:**
- `sops` CLI (for encrypted secrets management)
- `age` (recommended SOPS encryption method)

**Python dependencies:**
- `click>=8.1.0` - CLI framework
- `httpx>=0.27.0` - HTTP client for Portainer API
- `python-dotenv>=1.0.0` - Environment file parsing
- `rich>=13.0.0` - Colored terminal output

## Project Structure

```
deploy-kit/
├── src/deploy_kit/
│   ├── cli.py                              # Main CLI logic
│   ├── config.py                           # Configuration loading
│   ├── docker.py                           # Docker operations
│   ├── sops.py                             # SOPS integration
│   ├── utils.py                            # Logging utilities
│   ├── backends/
│   │   ├── compose.py                      # Docker Compose backend
│   │   └── portainer.py                    # Portainer API backend
│   └── scripts/
│       ├── docker_build.sh                 # Image build script
│       ├── docker_save.sh                  # Image export script
│       ├── ssh_transfer.sh                 # File transfer script
│       └── ssh_remote_deploy.sh            # Remote deployment script
├── templates/
│   ├── config/
│   │   └── deploy-kit.toml.example         # Configuration template
│   └── docker/
│       ├── docker-compose.dev.yml.template # Dev compose template
│       └── docker-compose.prod.yml.template # Prod compose template
├── justfile.include                        # Just recipes for integration
└── pyproject.toml                          # Project metadata
```

## Health Checks

Production deployments include automatic health checks:

**Default configuration:**
- Health check path: `/` (configurable via `DEPLOY_HEALTHCHECK_PATH`)
- Interval: 30 seconds
- Timeout: 10 seconds
- Retries: 3
- Start period: 40 seconds

**Override health check path:**
```toml
[deploy]
healthcheck_path = "/api/health"
```

Or via environment variable:
```bash
DEPLOY_HEALTHCHECK_PATH=/api/health deploy-kit --compose user@host
```

## Tarball Management

Docker images are saved as compressed tarballs in `dist/` directory. Old tarballs are automatically cleaned up to save disk space.

**Default retention:**
```bash
# Keeps 3 most recent tarballs
dist/myapp-abc123.tar.gz  # Current
dist/myapp-def456.tar.gz  # Previous
dist/myapp-ghi789.tar.gz  # Older
# dist/myapp-jkl012.tar.gz  ← Automatically deleted
```

**Configure retention:**
```toml
[deploy]
keep_tarballs = 5  # Keep 5 most recent
```

Tarballs are sorted by modification time (newest first) and older ones are removed after each deployment.

## License

MIT
