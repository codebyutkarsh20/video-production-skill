# Diagnose and repair

Preserve the source, last usable output and job/cache state. Reproduce the smallest failing stage before changing tools or regenerating everything. Bound retries and retain errors that explain the outcome.

| Symptom | Inspect | Targeted response |
|---|---|---|
| Missing tool or access | Executable, supported host tool, authorized configuration | Report the precise dependency; complete independent work |
| Submission timeout | Saved job ID, provider status, uncertain cost | Inquire/retrieve first; resubmit only after the prior outcome is resolved |
| Decode/encode failure | Full decoder errors, streams, codec availability, storage | Repair the failing segment or normalize inputs; verify before promotion |
| Wrong crop or unreadable text | Target aspect ratio, representative frames, active controls | Reframe or recompose, then inspect at delivery size |
| Silence or music masking voice | Audio streams, waveform/loudness diagnostics, listening | Fix source/mix; existence of a stream is insufficient |
| Caption drift | Measured speech, source changes, cue bounds | Realign to actual audio and review speech-to-text correspondence |
| Character/product inconsistency | Reference assets and neighboring shots | Adjust references/shot design; bounded regeneration or agreed alternative |
| Stale scene | Content/settings hash and dependency graph | Invalidate affected results; keep unchanged approved scenes |

Use `video_tools.py verify` for metadata, full decode and SRT bounds. It deliberately does not certify content quality or semantic synchronization. FFmpeg black/silence/loudness diagnostics can flag suspicious intervals; intended fades and pauses require interpretation.

After repair, rerun the failed check and downstream checks the change affects. State actual evidence and remaining uncertainty. Never relabel an unviewed or unheard export “fully quality checked.”
