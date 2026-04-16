# Development Documentation

This document explains the process for building, tagging, and pushing Docker images for this repository to Docker Hub.

## Pushing to Docker Hub

To push a new version of the API, follow these steps:

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
