# Video Production contributor instructions

This repository distributes an Agent Skill and local production helpers. Start with README.md, INSTALL.md and the support matrix. `skills/video-production/SKILL.md` is the installed entry point; route references are loaded only when relevant.

- Preserve the distinction between a requested brief, playable preview, full production and repair. Keep scope and existing review decisions.
- Keep portable skill files inside `skills/video-production/`. Repository-only examples and contributor tools belong outside the installed skill.
- Use relative paths and discover host tools. Keep credentials, real customer data, model weights, local caches and machine-specific paths out of Git and release archives.
- Record maturity separately from current availability. A documented adapter is not a tested provider. Technical decoding is not visual/listening acceptance.
- Test meaningful behavior and run `python3 -m unittest discover -s tests -v`. FFmpeg/ffprobe enable actual media integration tests; Pillow enables the example cache tests. State skipped tests.
- Run `python3 scripts/package_release.py` after distribution changes and inspect both source and standalone skill ZIPs. Preserve LICENSE, relative references, helper code and agent metadata.
- Increment output-affecting cache keys when changing rendering or narration behavior. Preserve completed work and uncertain paid-job state.
- Public uploads, provider calls and paid usage follow the user's authorization. Never obtain credentials by reading private files into agent context.

For new routes/providers, follow CONTRIBUTING.md and the adapter contract in `skills/video-production/references/generated-media.md`. Report reproducible evidence and honest limits; do not expand SKILL.md into a copied vendor manual.
