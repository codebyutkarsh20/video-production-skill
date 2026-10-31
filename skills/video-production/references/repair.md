# Diagnose and repair

Preserve the source, last usable output and job/cache state. Reproduce the smallest failing stage before changing tools or regenerating everything. Bound retries and retain errors that explain the outcome.

| Symptom | Inspect | Targeted response |
|---|---|---|
| Missing tool or access | Executable, supported host tool, authorized configuration | Report the precise dependency; complete independent work |
| Submission timeout | Saved job ID, provider status, uncertain cost | Inquire/retrieve first; resubmit only after the prior outcome is resolved |
| Decode/encode failure | Full decoder errors, streams, codec availability, storage | Repair the failing segment or normalize inputs; verify before promotion |
| Wrong crop or unreadable text | Target aspect ratio, representative frames, active controls | Reframe or recompose, then inspect at delivery size |
| Silence or music masking voice | `verify --qc` silence and loudness, `timeline` waveform, listening | Fix source/mix; set `music.gain_db` and `duck`, recompose |
| Caption drift or wrong words | `speech-check` against a fresh transcript of the export | Regenerate with `captions` from word timings after any timing change |
| Fast, long or overlapping captions | `verify --qc` findings, compose warnings, frames | Lower `--max-chars` or choose a smaller style; keep whole sentences together |
| Black, frozen or low-coverage picture | `verify --qc` intervals and `picture_coverage` | Check the source and trim; use `fit: cover` or `crop` for bars |
| Washed-out or wrong colours from a phone | Source transfer in `ffprobe`, compose `tone_mapped_scenes` | Recompose to tone-map; judge the result in frames |
| Cuts that fail or pop | Compose error, frame count, `review` at the cut | Rerun `cuts` for frame-aligned scenes; a stale cache rebuilds automatically |
| Character/product inconsistency | Reference assets and neighboring shots | Adjust references/shot design; bounded regeneration or agreed alternative |
| Stale scene | Content/settings hash and dependency graph | Invalidate affected results; keep unchanged approved scenes |

Use `video_tools.py verify --qc` for metadata, full decode, SRT bounds and suspicious intervals. Intended fades and pauses require interpretation. It flags faults and does not certify quality.

After repair, rerun the failed check and downstream checks the change affects. State actual evidence and remaining uncertainty. Never relabel an unviewed or unheard export “fully quality checked.”
