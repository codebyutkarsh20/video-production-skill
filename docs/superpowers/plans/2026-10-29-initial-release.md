# Video Production Initial Release Implementation Plan

> **For agentic workers:** Implement inline with independent behavioral evaluation and a final fresh review. The owner approved the design and execution on 29 October 2026; proceed without another design checkpoint.

**Goal:** Deliver a public-ready, portable video-production skill, useful local helpers, actual regression evidence and a polished playable preview before publication.

**Architecture:** A concise skill routes to production-specific references. Python helpers validate a canonical manifest, inspect media, and compose local footage with content-addressed scene caching. Examples supply an original frame renderer and fictional browser recording; external generation providers have an extension contract and explicit untested status.

**Tech stack:** Python 3.10+, FFmpeg/ffprobe; Pillow for the motion example; available local browser automation for the recording example. macOS `say` supplies optional preview narration, never a portable prerequisite.

**Spec:** `design.html` (owner approved).

## Global constraints

- Broad video types, explicit maturity and current availability.
- Actual media required in production mode; brief mode must remain brief-only.
- Preview scope ends at the requested review; existing decisions persist.
- Public package contains original instructions/code and fictional/licensed assets, no private app data, credentials, machine paths or paid-provider activation.
- Technical validation, visual review, listening review and owner approval are separate evidence.
- No push or publication before preview review.

## Review focus

- Path traversal and unsupported remote resources must be refused by local helpers.
- Missing/invalid streams, non-finite durations and captions outside the timeline fail clearly.
- Interrupted jobs never promote partial output or repeat uncertain paid work.
- A changed source invalidates only dependent cached segments.
- Agent instructions preserve brief-only, preview-only and already-approved requests.

## Tasks

### 1. Baseline behavioral probes and package skeleton
- [x] Run independent brief-only, uncertain-job and quality-claim probes without the skill; preserve outputs and score honestly.
- [x] Initialize an isolated Git repository on `codex/initial-release`; add package layout and concise original skill/reference documents.
- [x] Validate skill format and relative references.

### 2. Local production helpers
- [x] Write failing unit/integration tests for manifest errors, path safety, SRT timing, stream validation and content-cache invalidation.
- [x] Implement `skills/video-production/scripts/video_tools.py`: `doctor`, `check`, `verify`, `compose`.
- [x] Run full tests against actual generated video/audio fixtures. Include corrupt-file rejection and resumable clip composition.

### 3. Actual examples and quality preview
- [x] Create an original 45–60 second animated skill showcase, narration, captions, stills and reproducible source.
- [x] Capture a real fictional browser workflow and render a footage-edit example through the helper.
- [x] Verify exports and inspect visual frames; document actual listening-review scope.

### 4. Public readiness and independent evaluation
- [x] Add installation, MIT license, contribution/adapter contracts, support matrix and release evidence.
- [x] Run independent with-skill scenarios, including an actual executable consumer task.
- [x] Perform a fresh code/package review and fix material findings with regression tests.
- [x] Build and inspect a distributable archive; commit only this project's scoped files after fresh checks.
- [x] Show the playable preview and clear limits; await owner review before publication.
