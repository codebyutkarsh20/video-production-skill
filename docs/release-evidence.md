# Release evidence

The owner approved implementation and subsequently authorized public GitHub publication on 29 October 2026. The original local verification receipt follows; public installation and CI evidence are recorded separately. No external video-generation provider has been activated.

## v0.2.0 publication candidate — 29 October 2026

The owner authorized pushing the proactive-production update and publishing a new public release. This version adds creative direction and missing-input discovery, visual/audio tool recommendations and voice-audition guidance. It adds no provider integration, bundled voice engine or new generated showcase; the v0.1.0 sample remains an illustration of the existing rendering route.

Local release checks: all **31 tests passed with no skips**, including updated assertions for the v0.2.0 archive names and inclusion of the creative-direction reference. Skill format validation and whitespace checks passed. Package/download/installation checks and hosted CI results belong to their actual execution receipts; local success does not imply public availability. Bounded independent instruction probes and their limits are recorded in `docs/evaluations.md`.

Both distribution archives use v0.2.0 names and contain the updated skill metadata and references. INSTALL.md points to the versioned v0.2.0 skill source and standalone download. Existing v0.1.0 release history and sample links are preserved.

## v0.1.0 verification record

## Executed checks

- `python3 -m unittest discover -s tests -v`: **31 tests**, including actual FFmpeg integration cases; no skips on this machine.
- Skill-creator format validation: valid. Markdown reference targets checked locally.
- Media integration covers real decode/compose/cache reuse, corrupt media, requested source audio, crop dimensions, trim limits, audio-tail/picture-duration mismatch, caption timing, safe paths, source protection and release-package content.
- Independent review identified four material issues: container duration masking short video, stale narration settings, corrupt cached clips and a missing packaging script in the archive. Each was addressed with regression coverage. Additional source-protection and malformed-state tests also passed.
- The allowlisted archive includes installable skill, license, helpers, examples, tests and contribution/release documentation. It excludes private/runtime artifacts, generated voice/media, environment files and local design/planning notes. The extracted archive passed all **31 tests** and successfully ran its bundled packaging command.

## Actual media

The original motion-graphics showcase is **55.000 seconds, 1920×1080, 30 fps, H.264/yuv420p with AAC audio**. The final review version uses local Piper female US-English narration, original vector graphics, original mathematical ambient music and sentence/phrase captions. It is a showcase of the skill's workflow, not a recording of GMC/KYP or evidence of live video-generation-provider integration. Voice/model provenance and dependency licenses are recorded in `ASSET-CREDITS.md`.

The initial system-voice master passed metadata, full decoding and SRT timeline checks; its audio diagnostics found nonzero sound and no detected clipping/black interval under the selected checks. Seven designed stills and fourteen exported scene/transition frames were visually inspected. The final Piper version is checked separately after rendering and its receipt is recorded below. These checks do not establish frame-by-frame motion review or perceptual listening acceptance.

**Final Piper preview receipt:** master duration and video-stream duration both **55.000 seconds**, **1920×1080**, **30fps**, H.264/yuv420p, one AAC audio stream, **2,011,908 bytes**. Metadata, full decoding and all **17 measured-sentence SRT cues** passed. Audio diagnostics: mean **−18.1 dB**, maximum **−1.2 dB**. Black detection reported no intervals at `d=0.1:pix_th=0.05`. All **21 exported frames** spanning scene starts, middles and transitions were inspected; no framing/caption collisions were observed in those samples. A 1280×720 sharing copy was also encoded. Listening quality and full-motion acceptance remain for owner review.

A separate actual Chromium recording exercised the original fictional employee interface: opening the form, typing details, saving, checking count/result and capturing output. Browser assertions passed without page errors. The captured footage also passed the local composition/export path. It has no external backend, real invitations or insurance operations.

The recorder used Playwright **1.64.0** with its installed Chromium. Its final saved-result frame was visually checked with all three employee rows visible. The motion example used Piper **1.8.0** with the model/config hashes in the asset credits. These are tool-specific local receipts, not acceptance of other versions or external services.

An independent agent consumed the skill and rendered a **3.000-second, 640×360, 30fps** clip from supplied local source footage, with source audio retained. Its output and checks were inspected separately. See `docs/evaluations.md` for the bounded behavioral evidence.

## Review and release limits

- Owner quality review of the preview is pending; full perceptual listening and caption-to-speech review remain for that review.
- Final captions use separately synthesized, measured sentences and explicit inter-sentence pauses, not proportional word estimates or word-level forced alignment. Naturalness and perceptual synchronization remain part of owner review.
- The final review video replaces the earlier system voice with Piper/LJ Speech narration, with primary-source provenance recorded. The source archive does not bundle either voice model or either generated narration file.
- The helper was exercised on macOS/Python 3.12 with installed FFmpeg. Other OS/runtime combinations are not accepted by this receipt.
- No paid/generated-video provider adapter has been integrated or tested. Complex 3D, exact lip sync and long-form continuity are not claimed as tested capabilities.
- The package contains original public instructions/code and fictional examples. Public repository/release publication is authorized; no separate outreach or external provider activation follows from that instruction.

## Public distribution checks · 29 October 2026

The repository is public at https://github.com/codebyutkarsh20/video-production-skill with `main` as default, Issues and Discussions enabled, and contributor templates. Anonymous HTTP reads of repository metadata, the raw skill entry and the agent-readable index returned 200.

A fresh isolated project installed the complete skill from GitHub using Skills CLI **1.7.4**, Node **24.19.0**, and explicit Codex, Claude Code and Cursor selections. All installed skill files matched source bytes. The CLI selected the shared `.agents/skills` location for Codex/Cursor and a Claude Code symlink. The installed helper's `doctor` command completed successfully. This verifies distribution and file placement; it does not claim full native application execution for all hosts.

The Codex built-in GitHub skill installer also downloaded `skills/video-production` into a separate temporary destination; the entry, references, license and helper were present and the installed `doctor` completed. Both tests preserved the owner's existing installation. The source package now also produces a standalone nine-file skill ZIP and checksums.

Local tests still pass **31/31**, including the standalone archive's complete layout and exclusion of contributor/test material. GitHub-hosted CI runs separately on Ubuntu/Python 3.10 and 3.12; use the repository's Actions page for its actual current result.
