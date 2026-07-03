# Development Documentation

This document explains the process for building, tagging, and pushing Docker images for this repository.

## GitLab CI (recommended for production)

The GitLab project and its container registry are **private**. CI runs on **every merge request and branch push**:

| Stage | Job | What it does |
|-------|-----|----------------|
| `lint` | `lint` | `uv sync --only-group lint` + `make check` (ruff, mypy, version sync) |
| `lint` | `shellcheck` | `scripts/shellcheck.sh` |
| `test` | `test` | Full test suite (`make test`, coverage ≥ 60%) with poppler, LibreOffice, Tesseract, pandoc |
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

## Async outbound URL environment variables

These variables apply when callers use **async partition** (`destination_url` set). The API validates every outbound HTTPS URL before fetching input (`source_url`), uploading results (`destination_url`), or resuming orchestration (`callback_url`). Hostnames must match an allowlist; suffix rules require a **dot boundary** (e.g. `project.supabase.co` matches `.supabase.co`, but `evil-supabase.co` does not).

See also `FORK_CHANGELOG.md` for fork-specific API behaviour.

### Which variables are mandatory?

| Variable | Required? | When |
|----------|-----------|------|
| `CALLBACK_URL_ALLOWED_HOST_SUFFIXES` **or** `CALLBACK_URL_ALLOWED_HOSTS` | **Yes** | Whenever requests include `callback_url` (Contradic `ingest-unstructured` always does). At least one of these must be non-empty. |
| `SOURCE_URL_ALLOWED_HOST_SUFFIXES` | No | Default: `.supabase.co`. Only evaluated when `source_url` is sent. |
| `SOURCE_URL_ALLOWED_HOSTS` | No | Extra exact hostnames for `source_url` (comma-separated). |
| `DESTINATION_URL_ALLOWED_HOST_SUFFIXES` | No | Default: `.supabase.co`. Evaluated whenever `destination_url` is sent. |
| `DESTINATION_URL_ALLOWED_HOSTS` | No | Extra exact hostnames for `destination_url`. |
| `OUTBOUND_URL_ALLOW_HTTP` | No | Dev/local only. Allow `http://` for all outbound async URLs. |
| `SOURCE_URL_ALLOW_HTTP` | No | Same as above; kept for backward compatibility. |
| `SOURCE_URL_MAX_BYTES` | No | Default: `524288000` (500 MiB). Max download size for `source_url`. |
| `SOURCE_URL_FETCH_TIMEOUT_SECONDS` | No | Default: `300`. HTTP timeout when fetching `source_url`. |

**Synchronous** partition requests (no `destination_url`) do not use these allowlists.

**Contradic production minimum:** set `CALLBACK_URL_*` to your Kestra API host. Supabase signed URLs are covered by the default `.supabase.co` suffix for `source_url` and `destination_url` unless you use a custom storage domain (then add `*_ALLOWED_HOSTS` or change the suffix).

### Variable reference

#### `SOURCE_URL_ALLOWED_HOST_SUFFIXES`

Comma-separated hostname suffixes allowed for `source_url` downloads.

- **Default:** `.supabase.co`
- **Example:** `.supabase.co,.storage.example.com`

#### `SOURCE_URL_ALLOWED_HOSTS`

Comma-separated exact hostnames additionally allowed for `source_url` (in addition to suffixes).

- **Default:** *(empty)*
- **Example (local Supabase):** `127.0.0.1,localhost,host.docker.internal,kong`

#### `DESTINATION_URL_ALLOWED_HOST_SUFFIXES`

Comma-separated hostname suffixes allowed for `destination_url` PUT uploads.

- **Default:** `.supabase.co`
- **Example:** `.supabase.co`

#### `DESTINATION_URL_ALLOWED_HOSTS`

Comma-separated exact hostnames additionally allowed for `destination_url`.

- **Default:** *(empty)*
- **Example (local Supabase):** `127.0.0.1,localhost,host.docker.internal,kong`

#### `CALLBACK_URL_ALLOWED_HOST_SUFFIXES` *(mandatory for async + callback)*

Comma-separated hostname suffixes allowed for `callback_url` POST webhooks (e.g. Kestra resume).

- **Default:** *(none — must be configured)*
- **Example:** `.kestra.example.com` if Kestra is at `https://kestra.example.com`

#### `CALLBACK_URL_ALLOWED_HOSTS` *(mandatory for async + callback)*

Comma-separated exact hostnames allowed for `callback_url`. Use when a single host is easier than a suffix.

- **Default:** *(none — must be configured unless suffixes are set)*
- **Example:** `kestra.internal` (hostname from `KESTRA_API_BASE_URL` without path)

Set **either** `CALLBACK_URL_ALLOWED_HOST_SUFFIXES` **or** `CALLBACK_URL_ALLOWED_HOSTS` (or both). If both are empty, every `callback_url` is rejected with `callback_url host is not allowed (no outbound allowlist configured)`.

#### `OUTBOUND_URL_ALLOW_HTTP` / `SOURCE_URL_ALLOW_HTTP`

When set to `true`, `1`, or `yes`, permits `http://` URLs for `source_url`, `destination_url`, and `callback_url`. HTTPS remains required in production.

- **Default:** unset (HTTPS only)

#### `SOURCE_URL_MAX_BYTES`

Maximum bytes downloaded from `source_url`.

- **Default:** `524288000` (500 MiB)

#### `SOURCE_URL_FETCH_TIMEOUT_SECONDS`

Socket read timeout (seconds) for `source_url` fetch.

- **Default:** `300`

### Contradic deployment example

`ingest-unstructured` sends:

- `source_url` — Supabase signed download URL (`*.supabase.co`)
- `destination_url` — Supabase signed upload URL (`*.supabase.co`)
- `callback_url` — `{KESTRA_API_BASE_URL}/api/v1/main/executions/{id}/resume`

Example `docker-compose` / Elestio environment block:

```yaml
UNSTRUCTURED_API_KEY: ${API_KEY}
SOURCE_URL_ALLOWED_HOST_SUFFIXES: .supabase.co
DESTINATION_URL_ALLOWED_HOST_SUFFIXES: .supabase.co
# Required: match the host in KESTRA_API_BASE_URL (no path)
CALLBACK_URL_ALLOWED_HOST_SUFFIXES: .your-kestra-domain.com
# Or exact host:
# CALLBACK_URL_ALLOWED_HOSTS: kestra.your-domain.com
```

Derive the callback allowlist from `KESTRA_API_BASE_URL`:

```bash
# If KESTRA_API_BASE_URL=https://kestra.example.com
# use CALLBACK_URL_ALLOWED_HOST_SUFFIXES=.example.com
# or CALLBACK_URL_ALLOWED_HOSTS=kestra.example.com
```

### Local development example

When Supabase/Kong run on the Docker host or in compose:

```yaml
OUTBOUND_URL_ALLOW_HTTP: "true"
SOURCE_URL_ALLOWED_HOST_SUFFIXES: .supabase.co
SOURCE_URL_ALLOWED_HOSTS: 127.0.0.1,localhost,host.docker.internal,kong
DESTINATION_URL_ALLOWED_HOST_SUFFIXES: .supabase.co
DESTINATION_URL_ALLOWED_HOSTS: 127.0.0.1,localhost,host.docker.internal,kong
CALLBACK_URL_ALLOWED_HOSTS: host.docker.internal
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
