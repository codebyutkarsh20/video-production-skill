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

All local media references resolve within the project directory, including symlink targets. `--source-root` adds an explicit folder that relative paths and symlinks may reach; absolute paths and remote URLs stay refused. Scene durations snap to whole output frames and must fit the source. `fps` is a number or a fraction such as `"30000/1001"`. `source_audio` defaults to false, and each chunk has a normalized stereo track with hard cuts softened by short fades. HDR sources are tone-mapped to BT.709 when FFmpeg has `zscale`, and all output is tagged BT.709.

Optional scene fields:

| Field | Meaning |
|---|---|
| `fit` | `contain` (default, pads to fit) or `cover` (fills the frame by cropping); compose warns when `contain` leaves little picture |
| `focus_x`, `focus_y` | 0–1 position of the `cover` crop window |
| `crop` | `{x, y, w, h}` in source pixels, applied first; use a tighter rect for a punch-in |

A still image scene (png, jpg, webp, bmp, tif) is a scene with a `duration` and no audio.

Optional top-level fields, each a path with an asset provenance entry where it names a file:

| Field | Meaning |
|---|---|
| `narration` | Replaces source audio; padded to the timeline and refused if too long |
| `captions` | SRT on the output timeline |
| `burn_captions` | `{style, font}`, drawn last; style is `bold-center`, `clean-lower` or `minimal`; needs `captions` and FFmpeg's `ass` filter |
| `music` | `{path, gain_db, duck}`; loops to length and ducks under speech unless `duck` is false |
| `loudness` | `{target, true_peak}`; two-pass normalization of the final mix |

For `audio: none`, final export removes audio. Layered animation, overlays and animated zooms belong in a composition tool. Required audio means a stream exists; `verify --qc` reports silence.

Commands, run with the skill script's resolved location:
```
python3 video_tools.py check /path/to/project.json
python3 video_tools.py compose /path/to/project.json /path/to/output.mp4
python3 video_tools.py verify /path/to/output.mp4 --manifest /path/to/project.json --qc --loudness-target -14 --report /path/to/report.json
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

Use explicit review entries: method, timestamp, scope and findings. `visual: not_performed` and `listening: not_performed` are honest defaults. The helper's measurements and review images never set human-review fields. Publish only after the user authorizes that external action.
