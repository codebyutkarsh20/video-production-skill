# Generated shots, avatars and hybrid media

Generation requires an available authorized tool/provider. The core skill does not bundle working integrations with every provider. Discover actual capability, account access, current limits and cost before selecting a route. A generic prompt is not an executed integration.

Prepare a shot list and continuity references: subject, setting, action, camera, lighting, style, duration, aspect, sound and exclusions when relevant. Keep factual statements separate from illustrative scenes. Choose references and reusable generated assets to improve continuity. Avoid baking exact instructional text into generated pixels when a deterministic overlay would be clearer.

Test the highest-risk representative shot before a batch: recognizable product, recurring character, camera movement or lip sync. Inspect real output. Quality defects may need a revised shot, approved alternative technique or an explicit limit. Limit retries by the user's time/cost contract; “retry until perfect” is not a budget.

When a product or character must stay recognizable and the tool supports it, approve stills first and pin them as the shot's first and last frames, so generation only fills the motion between.

Before delivering generated or manipulated media, raise disclosure. EU AI Act Article 50, in application from 2 August 2026, sets transparency duties for some synthetic media and deepfakes, and platforms have their own labelling rules. Tell the user which shots are generated, record them in `provider_jobs`, and recommend they check what applies to their audience and take legal advice where it matters. This is a prompt to check, not legal advice.

## Adapter contract for contributors

Document:
- Maturity and actual tested environment/date; supported inputs/outputs and current official references.
- Credential interface (names/references only), upload/data exposure and required authorization.
- Duration, aspect, resolution, FPS and audio constraints; whether outputs expire.
- Submit, status, retrieve and supported cancellation operations.
- Provider job IDs, idempotency behavior, known/uncertain charges and bounded retry policy.
- A minimal successful output and representative failure/recovery evidence.

A timeout leaves the job uncertain. Persist its ID and query the same job before another submission. If no inquiry is possible, report that uncertainty; do not treat it as free failure. Cancellation and client disconnection are not proof billing stopped. A fallback provider requires agreement when cost, data exposure or result changes materially.

Retrieve usable output into the authorized project, preserve provenance and expiry information, and compose it with source footage, narration and deterministic overlays. Never put API keys in assets, logs or a shareable manifest.
