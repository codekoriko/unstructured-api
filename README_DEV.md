# Development Documentation

This document explains the process for building, tagging, and pushing Docker images for this repository.

## GitLab CI (recommended for production)

The GitLab project and its container registry are **private**. CI runs on **merge requests and pushes to `main` only** (other branch pushes are skipped):

| Stage | Job | What it does |
|-------|-----|----------------|
| `lint` | `lint` | ruff format/check + CHANGELOG version sync |
| `lint` | `shellcheck` | shell script lint |
| `typecheck` | `typecheck` | mypy on `prepline_general/api` |
| `test` | `test` | pytest + coverage (≥ 60%) |
| `publish` | `docker-publish` | **main only** — build and push image after `test` passes |

On push to `main`, the pipeline also publishes the Docker image:

`registry.gitlab.com/contradic/contradic-unstructured-api`

Tags published:

- `latest`
- `<git short sha>` (e.g. `8d833a4`)
- `<__version__>` from `prepline_general/api/__version__.py` (e.g. `0.1.2`)

### CI push (automatic)

The pipeline authenticates with GitLab's built-in `CI_JOB_TOKEN` (`CI_REGISTRY_USER` / `CI_REGISTRY_PASSWORD`) to push to this project's registry.

If your group restricts job-token registry access, create a **deploy token** with `write_registry`, then add masked CI/CD variables:

- `REGISTRY_DEPLOY_USER`
- `REGISTRY_DEPLOY_TOKEN`

Also verify **Settings → CI/CD → Job token permissions** allows this project to access its container registry.

Other prerequisites:

1. **Container Registry** enabled on the project.
2. A GitLab runner with Docker-in-Docker and enough disk for image builds.

### Pull on servers (manual auth required)

Images are not public. Log in before `docker pull` or `docker compose pull`:

```bash
# Deploy token (read_registry) or personal/group access token with read_registry
docker login registry.gitlab.com -u <gitlab-username-or-deploy-token-name> -p <token>
docker pull registry.gitlab.com/contradic/contradic-unstructured-api:latest
```

On deployment hosts, store credentials in `~/.docker/config.json` or your orchestrator's secret store (Elestio, Infisical, etc.).

**Note:** `uv.lock` is resolved for **Linux** (`tool.uv.environments` in `pyproject.toml`) because `unstructured` 0.23.x depends on `torch` wheels that are not published for macOS x86_64. `torch` / `torchvision` are pinned to the [PyTorch CPU index](https://download.pytorch.org/whl/cpu) so CI and Docker images avoid multi-GB NVIDIA CUDA packages. Use Docker or GitLab CI to build and test; local `uv sync` on Intel Mac may not install the full runtime graph.

## Async outbound URL environment variables

These variables apply when callers use **async partition** (`destination_url` set). The API validates every outbound HTTPS URL (`source_url` GET, `destination_url` PUT, `callback_url` POST) against a **single shared allowlist**. Requests do not follow redirects; `source_url` downloads pin DNS at connect time.

### Configuration

| Variable | Default | When you need it |
|----------|---------|------------------|
| `OUTBOUND_URL_ALLOWED_HOST_SUFFIXES` | `.supabase.co` | **Production minimum.** Matches multi-tenant hosts (`*.supabase.co` per project). Add your Kestra domain suffix here too (e.g. `.your-kestra-domain.com`). |
| `OUTBOUND_URL_ALLOWED_HOSTS` | *(empty)* | **Optional.** Exact hostnames or IPs that suffixes cannot express: local dev (`127.0.0.1`, `localhost`, `kong`), or a single Kestra host when you do not want to allow an entire domain suffix. |
| `OUTBOUND_URL_ALLOW_HTTP` | off | Dev only |
| `OUTBOUND_URL_TIMEOUT_SECONDS` | `300` | PUT/POST timeout |
| `SOURCE_URL_MAX_BYTES` | 500 MiB | Download cap |
| `SOURCE_URL_FETCH_TIMEOUT_SECONDS` | `300` | Download timeout |

**Do you need both suffix and hosts?** Usually **suffixes only** in production:

```yaml
OUTBOUND_URL_ALLOWED_HOST_SUFFIXES: .supabase.co,.your-kestra-domain.com
```

Use `OUTBOUND_URL_ALLOWED_HOSTS` only when exact matching is clearer or required (single Kestra hostname without widening to `.example.com`, or local Supabase/Kong on `localhost` / `127.0.0.1`).

Deprecated per-role variables (`SOURCE_URL_*`, `DESTINATION_URL_*`, `CALLBACK_URL_*`) were removed; use `OUTBOUND_URL_*` only.

### Contradic deployment example

```yaml
UNSTRUCTURED_API_KEY: ${API_KEY}
OUTBOUND_URL_ALLOWED_HOST_SUFFIXES: .supabase.co,.your-kestra-domain.com
```

Local Supabase/Kong:

```yaml
OUTBOUND_URL_ALLOW_HTTP: "true"
OUTBOUND_URL_ALLOWED_HOST_SUFFIXES: .supabase.co
OUTBOUND_URL_ALLOWED_HOSTS: 127.0.0.1,localhost,host.docker.internal,kong
```

## Manual push to Docker Hub (legacy)

To push a new version of the API manually to Docker Hub, follow these steps:

**prerequisite:** Launch Docker 🐋

### 1. Build the image

You can use the provided build script. Ensure you have the `DOCKER_IMAGE` variable exported (see below) before running it to build with the correct tag.

```bash
./scripts/docker-build.sh
```

*(Note: The script defaults to building `pipeline-family-general-dev` if `DOCKER_IMAGE` is not set.)*

### 2. Set the Version Environment Variable

Set the `DOCKER_IMAGE` variable to the version you want to build and push. **Note: Each time you perform a push, ensure you increment the version suffix.**

For example:

- previous push: `zeuxippus/unstructured-api:0.1.2-contradic.3`
- This push should be: `zeuxippus/unstructured-api:0.1.2-contradic.4`

```bash
export DOCKER_IMAGE="zeuxippus/unstructured-api:0.1.2-contradic.4"
```

### 3. Tag the Image

Tag the image you just built with the `latest` tag.

```bash
# Tag as latest
docker tag $DOCKER_IMAGE zeuxippus/unstructured-api:latest
```

### 4. Push to Docker Hub

Push both the versioned tag and the latest tag.

```bash
# Push the versioned tag
docker push $DOCKER_IMAGE

# Push the latest tag
docker push zeuxippus/unstructured-api:latest
```
