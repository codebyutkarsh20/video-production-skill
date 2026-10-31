# Actual screen workflows

Inspect the real interface and authorization before scripting. If an app was not supplied, ask for its location or agree on an original fictional interface; building an extra app is a distinct scope choice. Use a disposable recording account/dataset when available and preserve the user's active application/data.

Follow one meaningful task through action and visible result. Select exact current route labels and states. Separate loading, saved, submitted, externally accepted and completed states. Edited transitions between prepared cases must not suggest an external system replied instantly.

Use the host's supported browser automation or recorder. Check the capture mechanism with a short clip; screenshots alone do not establish moving workflow quality. For a repeatable recording, set viewport, start state, record cursor/action timings and remove idle waits in editing. Match the requested aspect ratio before capturing.

With Playwright, plan for two gaps. Headless recordings show no pointer, and `recordVideo` is 25 fps at 1× detail, so a zoom goes soft; asking it for 2560×1440 at 2× device scale fills only the top-left quadrant. `scripts/screen_capture.cjs` handles both: `installCursor` draws a pointer and click ripple that follow real mouse events, and `recordFrames` captures 2× screenshots with their real timing. On a simple page it reached about 18 fps, and heavier pages will be lower, so check the returned `fps`. Encode with `ffmpeg -f concat -safe 0 -i capture/frames.ffconcat -vf fps=30,format=yuv420p -c:v libx264 -crf 16 capture.mp4`. Use `crop` on a tighter scene for a static zoom; animated zooms need a composition tool.

Capture the application viewport with legible controls. Exclude browser chrome, unrelated tabs and private credentials. Preserve meaningful warnings and conditions. Decorative “demo” titles are optional branding choices; never erase an important product warning to make a feature look ready.

Zoom to the action while retaining orientation. Hold the resulting state long enough to read. Avoid making narration describe a click after the recording has already moved elsewhere. Sample frames at scene transitions and after form submission. A desktop responsive recording is not evidence of a native mobile app.

Keep footage, captions, audio and callouts editable. Obtain a browser-workflow receipt separately from the video-encode receipt. Follow [project state](project-contract.md) for clips, provenance and validation.
