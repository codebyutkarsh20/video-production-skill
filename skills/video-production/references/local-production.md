# Motion graphics and footage editing

Choose an existing local composition environment when it fits. Remotion or another frame-addressable engine suits layered animation; FFmpeg suits transformations and assembly; an original Pillow renderer can suit lightweight diagrams. Check installed versions and current official docs. Keep tool-specific dependencies optional.

Choose a visual system tied to the brief: hierarchy, typography, palette, layout, motion and caption treatment. Plan each scene around a concrete picture. Keep titles short and narration informative; avoid text screens that repeat every spoken word. Prefer coherent movement and useful diagrams over decorative motion.

Build the narration or source-footage timeline first. Measure audio and preserve speech when adjusting duration. Align captions to phrase boundaries using actual timings or alignment output; word count is only an estimate. Keep music beneath narration and check transitions with sound.

For existing clips, inspect orientation, FPS, duration, audio and rights. Decide whether scaling should contain, crop or preserve the original aspect; a new crop can remove a subject or subtitle. Normalize before concatenating incompatible sources. Use fade handles outside important action.

Render a moving excerpt early. Keep scene parameters and assets separate from rendering mechanics. Cache work by content and settings, not just filenames. After editing narration, invalidate dependent timing and captions. After editing the style, invalidate dependent frames. A cached render must still decode before reuse.

The bundled clip assembler provides fitting/padding, trims, normalized output and narration replacement. It does not supply a visual designer, semantic caption alignment or a universal animation engine. The repository examples demonstrate original motion, fictional browser recording and clip assembly. Create user-specific visuals instead of treating those examples as a mandatory template.

References: [Remotion docs](https://www.remotion.dev/docs/), [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html), [FFprobe](https://ffmpeg.org/ffprobe.html).
