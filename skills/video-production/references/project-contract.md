# Project state and outputs

Use one canonical `project.json` when a build benefits from persistent state. Human reports may summarize it; do not maintain competing timing/asset lists. Plain brief requests need only the requested brief.

Minimal local composition contract (version 1):

```json
{
  "version": 1,
  "title": "A clear product journey",
  "mode": "preview",
  "spec": {
    "width": 1920, "height": 1080, "fps": 30,
    "min_duration": 45, "max_duration": 60, "audio": "required"
  },
  "assets": [
    {"path": "recording.mp4", "provenance": "Fictional local app recording", "rights": "Original recording with authorized assets"}
  ],
  "scenes": [
    {"id": "workflow", "asset": "recording.mp4", "duration": 50, "trim_start": 0, "source_audio": true}
  ]
}
```

All local media references resolve within the project directory, including symlink targets. The helper accepts video clips (not still images or remote URLs), scales them to fit with padding and normalizes FPS/audio. Clip durations must align to whole output frames and fit the source; input stills must first be rendered to clips. `source_audio` defaults to false. Each chunk has a normalized stereo track, including silence when source audio is disabled.

Optional `narration` and `captions` fields are relative paths with asset provenance entries. Narration replaces source audio; it is padded to the timeline and refused if too long. Music mixing, animation and burned-in captions belong in the composition tool, not this simple clip assembler. For `audio: none`, final export removes audio. Required audio currently means a stream exists; check audibility separately.

Commands, run with the skill script's resolved location:
```
python3 video_tools.py check /path/to/project.json
python3 video_tools.py compose /path/to/project.json /path/to/output.mp4
python3 video_tools.py verify /path/to/output.mp4 --manifest /path/to/project.json --report /path/to/report.json
```

Composition caches by source bytes, scene settings, output spec, tool version and pipeline version. A partial file is not promoted to a final artifact. Existing output requires `--overwrite`; original inputs remain protected. Cache files are disposable, source assets are not. Retain the cache only as needed; it may contain private footage.

For richer pipelines, extend state with `brief`, `style`, `facts`, `provider_jobs`, `reviews` and `deliverables`; these are agent-maintained records, not features automatically executed by this helper. Provider job records include operation, input digest, provider job ID, status, known/uncertain cost and last inquiry. Store credential references, never secret values.

## Deliverable contract

| Mode | Required result |
|---|---|
| Brief | Concise self-contained brief, declared defaults and unresolved dependencies |
| Preview | Playable representative segment, script, requested captions, source and short review notes |
| Production | Requested master/variants/captions, editable source, provenance and actual validation evidence |
| Repair | Repaired artifact when possible, specific changes/checks and unresolved limits |

Use explicit review entries: method, timestamp, scope and findings. `visual: not_performed` and `listening: not_performed` are honest defaults. The helper's metadata/decoder success never sets human-review fields. Publish only after the user authorizes that external action.
