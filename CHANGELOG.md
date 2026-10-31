# Changelog

## 0.3.0 — unreleased — local footage editing and automated checks

**Fixed**

- Cuts at most source times no longer fail: half of random cut points failed in a two-scene edit before this, and none in 40 now. Chunks are checked for exact frame counts. The pipeline cache version is now 3.
- Hard audio cuts get 30 ms fades, reducing the level jump on a test tone from ×19 to about ×1.
- HDR sources are tone-mapped when FFmpeg supports it, and output carries real BT.709 tags.
- Vertical specs no longer leave wide footage as a thin strip without warning. `fit: cover`, `focus_x/y` and `crop` fill the frame.
- Rational frame rates such as `30000/1001` work, durations snap to whole frames, and still images are real scenes.

**Added**

- `verify --qc`: black and frozen picture, silence, loudness, true peak, picture coverage and caption limits. A failing check exits 1.
- Footage reading: `transcribe.py` (local word timings), `pack`, `shots`, `timeline`, `cuts`, `captions`, `review` and `speech-check`.
- Finishing in `compose`: narration or scene audio, looped ducked music, two-pass loudness and burned captions in three styles, with a warning when a burned cue is likely to run past two lines.
- `reframe.py`: experimental per-scene face-tracked crop. `screen_capture.cjs`: visible cursor and 2× capture for Playwright.
- `--source-root` for sources outside the project, and `doctor` reporting by route.
- References for footage editing, craft and named looks; routing notes for specialist tools; first and last frame pinning and a disclosure step for generated media; repeatable agent cases in `evals/`.

**Changed**

- Rewrote the skill description around the words people use, such as edit, reel, TikTok, subtitles and silences. The effect on triggering is unmeasured.
- The caption-to-speech check moved off the “cannot check” list as a warning signal.
- Showcase captions wrap to two lines of at most 42 characters, and the stale version label is gone. The audio pipeline version is now 5.

No provider adapter is bundled and no new provider was tested.

## 0.2.0 — 2026-10-29 — proactive production guidance

- Added proactive creative recommendations, missing-input discovery and scoped improvement suggestions.
- Added visual/audio capability discovery, relevant tool-connection recommendations and voice-audition guidance.
- Preserved honest availability claims, user scope and paid/external-use boundaries; no new provider adapter is bundled.

## 0.1.0 — 2026-10-29 — first public release

- Added brief, preview, production and repair workflows with progressive route references.
- Added local manifest validation, SRT timing checks, full media decoding and resumable clip composition.
- Added original motion-graphics and fictional browser-recording examples.
- Added independent behavioral probes, actual media integration tests and a public-package allowlist.
- Documented provider integration contracts and distinct maturity/availability states.
- Added standard Skills CLI installation, a standalone skill ZIP, an agent-readable installation/index guide, contribution templates and GitHub Actions checks.

External video-generation providers and advanced 3D/lip-sync integrations remain unverified. Local execution and hosted CI evidence are recorded separately in the release evidence.
