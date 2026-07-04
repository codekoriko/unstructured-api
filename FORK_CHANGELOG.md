# Fork changelog

This file records **semantic changes** in this fork compared to **upstream** (`unstructured-io/unstructured-api` or your configured `upstream` remote). It is meant for humans and for **LLM agents** that need a concise, intent-level view of divergence without inferring it from the full git graph. When a change is coordinated with another repo (e.g. edge functions or infra), note **Related** under the entry so agents know the full contract across codebases.

## How to use (agents)

1. After any fork-specific change (not routine merges from upstream), append a new entry under **Entries** using the template below.
2. Prefer **what changed and why** over file lists; link to PRs or commits when useful.
3. Do **not** log pure `Merge branch 'upstream/main'` commits here unless the merge itself introduces or resolves fork-specific conflicts worth documenting.

### Entry template

```markdown
### YYYY-MM-DD — short title

- **Area:** (e.g. API, Docker, CI)
- **Summary:** One or two sentences.
- **Related (optional):** Other repo path + what changed there to match this fork.
- **Commit(s) / PR:** `abc1234` (optional)
```

---

## Entries

### 2026-07-03 — Simplify outbound URL allowlist and harden async egress

- **Area:** API, security
- **Summary:** Consolidated six per-role allowlist env vars into `OUTBOUND_URL_ALLOWED_HOST_SUFFIXES` (default `.supabase.co`) and `OUTBOUND_URL_ALLOWED_HOSTS`. Disabled redirect following on PUT/POST; `source_url` fetch uses DNS-pinned urllib3 connections. Async worker now POSTs `callback_url` on failure so Kestra does not hang after `202`.
- **Related:** `backend-infra-stack/unstructured-elestio/docker-compose.yaml` — use `OUTBOUND_URL_*` instead of `SOURCE_/DESTINATION_/CALLBACK_URL_*`.

### 2026-07-03 — Bump unstructured library to 0.23.1

- **Area:** Dependencies
- **Summary:** Upgraded `unstructured[all-docs]` from 0.22.18 to 0.23.1 (latest PyPI). Lockfile now resolves for Linux only (`tool.uv.environments`) because 0.23.x pulls `torch` via `unstructured-inference` without macOS x86_64 wheels. API release bumped to `0.1.8`.
- **Breaking:** `pandas` constraint lowered to `>=2.2.0, <3.0.0` to match `unstructured` 0.23.x. Chunking callers using `isolate_tables` must use `isolate_table` (upstream rename in 0.22.31; not exposed by this API today).

### 2026-07-04 — CPU-only PyTorch for CI and production

- **Area:** Dependencies, CI
- **Summary:** Pin `torch` and `torchvision` to the PyTorch CPU index via `tool.uv.sources`, avoiding multi-GB NVIDIA CUDA wheels that exhausted GitLab runner disk during `uv sync`. CI uses `UV_LINK_MODE=hardlink` and apt cache cleanup before the test job.

### 2026-07-03 — GitLab CI lint and test pipeline

- **Area:** CI
- **Summary:** Extended `.gitlab-ci.yml` with `lint`, `shellcheck`, and `test` jobs on merge requests and branch pushes. `docker-publish` on `main` now depends on `test` passing.
- **Related:** `README_DEV.md` — CI stage table.

### 2026-06-29 — Outbound URL allowlists and auth hardening

- **Area:** API, security
- **Summary:** Added SSRF allowlist validation for `destination_url` and `callback_url` (env: `DESTINATION_URL_*`, `CALLBACK_URL_*`), tightened hostname suffix matching to require a dot boundary, and stopped echoing API keys in 401 responses.
- **Related:** `backend-infra-stack/unstructured-elestio/docker-compose.yaml` — set `CALLBACK_URL_ALLOWED_HOST_SUFFIXES` or `CALLBACK_URL_ALLOWED_HOSTS` to match your Kestra API host; `DESTINATION_URL_ALLOWED_HOST_SUFFIXES` defaults to `.supabase.co` like `source_url`. Env var reference: `README_DEV.md` § Async outbound URL environment variables.

### 2026-06-29 — Sync upstream to 0.1.7

- **Area:** Dependencies, Docker, API
- **Summary:** Merged `upstream/main` after release `0.1.2`, bringing versions `0.1.3`–`0.1.7` (transitive dependency CVE fixes, ffmpeg-free opencv Docker build, starlette/lxml/python-multipart bumps). Fork features retained: async `destination_url`/`callback_url`/`callback_headers`, `source_url`, `include_orig_elements`, selective tessdata Dockerfile, GitLab CI publish.
- **Commit(s):** merge `6604b55`

### 2026-06-29 — GitLab CI Docker publish to private registry

- **Area:** CI
- **Summary:** Added `.gitlab-ci.yml` job that builds the API image on `main` and pushes to the private registry `registry.gitlab.com/contradic/contradic-unstructured-api` with `latest`, commit SHA, and `__version__` tags. CI uses `CI_JOB_TOKEN` by default; optional `REGISTRY_DEPLOY_*` variables support restricted groups. Pull requires `docker login` on deployment hosts.
- **Related:** Deployments should pull `registry.gitlab.com/contradic/contradic-unstructured-api:latest` (or a pinned SHA/version tag) instead of public Docker Hub images where applicable.

### 2026-06-29 — Signed source_url for async partition input

- **Area:** API
- **Summary:** Added `source_url` and `source_filename` form parameters for async requests (`destination_url` set). The worker fetches the input file over HTTPS from an allowlisted host instead of requiring a multipart upload, with SSRF protections (host suffix allowlist, DNS/IP checks, redirect blocking, size limits). Mutually exclusive with file upload.
- **Related:** Edge / infra repo `backend-infra-stack`: `ingest-unstructured` now creates a short-lived signed download URL via `createSignedUrl` and passes it as `source_url`, avoiding edge-function memory limits on large files. Configure `SOURCE_URL_ALLOWED_HOST_SUFFIXES` / `SOURCE_URL_ALLOWED_HOSTS` on the API deployment.

### 2026-04-09 — Asynchronous webhook callbacks for extraction

- **Area:** API
- **Summary:** Added `destination_url` and `callback_url` parameters to the partitioning flow to run the unstructured extraction asynchronously in the background using FastAPI `BackgroundTasks`. The API now returns `202 Accepted` immediately, and upon completion, performs an HTTP PUT to upload the parsed JSON and an HTTP POST to trigger the webhook callback.
- **Related:** Edge / infra repo `~/dev/js/contradic_mvp_backend_infra_stack`: `ingest-unstructured` edge function was refactored to use these parameters (passing a signed storage PUT URL and a Kestra resume webhook). It no longer blocks and waits for processing; Kestra pauses and waits for the callback to resume to a new `ingest-unstructured-finalize` step.

### 2026-02-17 — Partitioning API option and faster OCR image builds

- **Area:** API, Docker
- **Summary:** Exposed an `include_orig_elements` parameter on the partitioning flow so callers can turn original element metadata in chunks on or off. Reworked the Docker image build to install only the required Tesseract language data via direct downloads instead of cloning the full language-data repository, cutting image build time.
- **Related:** Edge / infra repo `~/dev/js/contradic_mvp_backend_infra_stack`: `ingest-unstructured` now sends `include_orig_elements: false` on requests to this API, and **`stripOrigElements` was removed** (including its call sites) because orig-element fields are no longer returned when omitted—so client-side stripping of stale fields is obsolete.
- **Commit(s):** `c368e70`

---

*Upstream sync merges (e.g. bringing `upstream/main` into this fork) are normal maintenance and are not listed above unless they carry fork-only resolution notes.*
