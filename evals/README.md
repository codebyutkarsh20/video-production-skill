# Repeatable agent cases

`cases.json` holds realistic requests and checkable pass conditions, including a no-skill baseline for each case. **No paired fresh-context benchmark has been run yet.** One supervised `vertical-clip` execution was completed on 31 October 2026; its evidence and limits are recorded in `docs/evaluations.md` and `evals/results/2026-10-31-vertical-clip.json`. This is not a with/without-skill comparison or a fully accepted video. Run each case in a fresh agent context with and without the skill, ideally several times, and record the actual results and skips in `docs/evaluations.md`, including cases where the baseline already passes.

Inputs are not bundled. Use your own licensed clips or a clip from an openly licensed film such as *Tears of Steel* (CC BY 3.0, Blender Foundation), and record which file you used.

`trigger_phrases` lists requests that should and should not start the skill, to measure the description.
