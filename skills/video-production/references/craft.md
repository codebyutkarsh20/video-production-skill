# Editing craft

Starting points for decisions a checklist cannot make. Numbers are defaults from common practice; the material and the brief can override them, so state the reason when you do. Platform figures change: check the platform's official pages before promising compliance.

## Cuts

- **Padding.** Keep 30–200 ms around speech: toward 30 ms for fast social pacing, toward 200 ms for interviews and anything calm. Word timestamps are approximate, so a chopped word at the padding limit needs more room. `VT cuts` takes `--pad-before` and `--pad-after`.
- **Breaths and pauses.** Remove filler and dead air, and keep a pause that lands a point. Removing every breath sounds machine-made.
- **Hard cuts inside one shot** read as jumps. Cover them with a punch-in (`crop` with a tighter rect on the second scene), a cutaway or a caption change.
- **L and J cuts.** Let one shot's sound run under the next picture, or let the next sound begin early. The helper's `narration` covers the whole timeline, which makes the picture cuts under it behave like this. A per-scene L or J cut needs a timeline editor or a custom FFmpeg graph.
- **Sentence order.** Reordering can change what a person said. Keep meaning, and flag any reorder of a real person's speech to the user.

## Structure

- **Hook.** The first 1–3 seconds of social video show the payoff or pose the question. Skip greetings, logos and setup.
- **Length.** Cut to the strongest version, not a target that forces padding. Reels and Shorts usually hold one idea; demos follow one task to its visible result.
- **Pacing.** Short-form often changes picture every 1–3 seconds; explainers 3–8; interviews can hold longer on a strong speaker. Change picture for a reason.
- **Ending.** Stop soon after the payoff, with one clear next action if there is one.

## Captions

- Aim for up to 42 characters per line, 2 lines, 20 characters per second and 0.5 seconds minimum. `verify --qc` reports breaches.
- Styles: `bold-center` (uppercase, for sound-off short-form, keep `--max-chars` near 32), `clean-lower` (boxed, for talks and demos), `minimal` (small, for long watches).
- Burn captions for social delivery where a sidecar may be dropped. Also deliver the SRT, for accessibility and platform upload.
- Spell names from the brief, not from the transcript.

## Sound

- Keep speech clearly above music: start music around −18 dB with `gain_db` and let `duck` lower it under voice. Check the ducked sections with sound before delivering.
- Common loudness targets: about −14 LUFS for social and streaming and −16 for speech-led video, with true peak at or under −1 dBTP. Sources disagree and platforms normalize differently. Very short clips measure less reliably; the helper reached −15.0 against a −14 target on a 10-second dialogue clip.
- Sound design earns its place when it marks a change, such as a soft tick on a key UI action. Use licensed sounds and record them in `assets`.

## Platform starting points

Secondary-source figures; verify current official specifications.

| Destination | Frame | Safe area |
|---|---|---|
| Reels, TikTok, Shorts | 1080×1920, 9:16 | Keep text out of about the bottom 25–30% and top 10–15%, plus a right-hand strip for buttons |
| YouTube | 1920×1080, 16:9 | Keep text clear of the player controls along the bottom |
| LinkedIn or feed | 1080×1080 or 1080×1350 | Captions on, since many watch without sound |

Footage below the output size gets upscaled and looks soft: say so, and offer a smaller output when it matters.
