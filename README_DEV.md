# Development Documentation

This document explains the process for building, tagging, and pushing Docker images for this repository.

## GitLab CI (recommended for production)

The GitLab project and its container registry are **private**. CI publishes on every push to `main`:

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
