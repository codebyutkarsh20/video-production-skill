# Repeatable agent cases

`cases.json` holds realistic requests and checkable pass conditions, including a no-skill baseline for each case. **No paired fresh-context benchmark has been run yet.** One supervised `vertical-clip` execution was completed on 31 October 2026; its evidence and limits are recorded in `docs/evaluations.md` and `evals/results/2026-10-31-vertical-clip.json`. This is not a with/without-skill comparison or a fully accepted video. Run each case in a fresh agent context with and without the skill, ideally several times, and record the actual results and skips in `docs/evaluations.md`, including cases where the baseline already passes.

Inputs are not bundled. Use your own licensed clips or a clip from an openly licensed film such as *Tears of Steel* (CC BY 3.0, Blender Foundation), and record which file you used.

`trigger_phrases` lists requests that should and should not start the skill, to measure the description.

`upstream-feedback-cases.json` separately exercises agent contribution decisions: proactive preparation, authorization, private evidence, missing host support, focused PRs and duplicate/uncertain writes. These are read-only scenario probes, not real GitHub integration tests. See `docs/evaluations.md` for the executions and limits.

`results/2026-10-31-live-feedback-issue.json` separately records one live, explicitly approved issue lifecycle through the connected GitHub integration. It is not part of unattended tests: repeating it requires a new run ID, an exact public packet and actual authorization for the external writes. It establishes neither a second contributor account nor a PR lifecycle; see the evaluation receipt for boundaries.
