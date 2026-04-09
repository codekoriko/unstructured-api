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
