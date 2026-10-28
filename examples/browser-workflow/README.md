# Fictional browser workflow

This original local interface is a small recording fixture, not a customer product. The browser script records actual form interaction and verifies that the new employee appears with separate portal-access status. No network backend or external delivery is involved.

From the repository root:

```sh
npm install --no-save playwright
npx playwright install chromium
node examples/browser-workflow/record.cjs
ffmpeg -i artifacts/browser-workflow/workflow.webm -c:v libx264 -pix_fmt yuv420p -an artifacts/browser-workflow/workflow.mp4
```

Create `artifacts/browser-workflow/project.json` using the project contract. Set the source to `workflow.mp4`, `audio` to `none`, width/height to 1280/720, FPS to 30, and a whole-frame duration shorter than the measured source. List its original provenance/rights. Then:

```sh
python3 skills/video-production/scripts/video_tools.py compose artifacts/browser-workflow/project.json artifacts/browser-workflow/workflow-edited.mp4
python3 skills/video-production/scripts/video_tools.py verify artifacts/browser-workflow/workflow-edited.mp4 --manifest artifacts/browser-workflow/project.json
```

This exercises browser recording and existing-footage composition. It does not demonstrate speech synthesis or a production product's server behavior.
