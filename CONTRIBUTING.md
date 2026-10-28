# Contributing

Contribute a focused change that improves an observable production outcome. Useful contributions include tool adapters, rendering routes, accessible templates, industry-specific guidance and regression cases.

1. Describe the user problem and current behavior. Check existing routes before adding another.
2. Keep shared decisions in `SKILL.md`; put route-specific detail behind a relevant reference. Maintain one source for each rule.
3. Add a realistic example and tests that prove behavior, not exact wording. Use fictional or appropriately licensed assets. For agent behavior, run comparable with/without-skill cases and preserve honest results, including controls that already behaved correctly.
4. Run `python3 -m unittest discover -s tests -v`. Run the relevant real render/browser/provider path. List unavailable dependencies and skipped checks explicitly.
5. Update support maturity, current availability requirements, asset credits and the changelog. Include artifact properties and validation evidence.

When changing output-affecting composition behavior, increment the helper's pipeline cache version so earlier chunks cannot bypass the new behavior. Narration and example renders must similarly invalidate dependent audio, captions and frames.

## Provider/renderer contributions

Follow the [adapter contract](skills/video-production/references/generated-media.md). Declare the credential interface, data exposure, limits, cost/idempotency, status polling, cancellation and retrieval behavior. A provider timeout must preserve the original job ID and uncertain cost. Cancellation cannot be treated as a billing receipt.

Add one real minimal successful result and meaningful failure/recovery evidence. Never commit keys, private prompts, customer records, browser sessions or signed URLs. Sanitized fixtures are welcome; they do not establish live-provider acceptance. Until a path is genuinely exercised, label it experimental/planned.

## Review criteria

- Does the change improve the requested artifact while preserving the user's scope?
- Are requirements discovered from supplied sources instead of repeatedly asked?
- Can another person reproduce the example without private local paths?
- Are partial files, stale caches and uncertain external jobs handled honestly?
- Are technical, visual, listening and owner-review evidence distinguished?
- Are original or third-party asset rights documented without relicensing them?

The maintainers may request a smaller change or a reproducible failure. Do not claim broad compatibility from one machine. Publishing and paid-provider tests require their own authorization; opening a contribution is not permission to use someone else's account.
