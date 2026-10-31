#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["faster-whisper==1.2.1", "numpy>=1.26,<3"]
# ///
"""Local word-level transcription for footage reading and caption timing.

Run with `uv run transcribe.py MEDIA --out words.json`. No audio leaves the machine.
A missing model is refused until --download-model is passed, since it is a large download.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def cached_transcript(media, out, model, glossary):
    """Return an existing transcript only if it came from these exact bytes and settings."""
    try:
        data = json.loads(Path(out).read_text(encoding='utf-8'))
        if data['sha256'] == digest(media) and data['model'] == model and data.get('glossary', []) == list(glossary): return data
    except (OSError, ValueError, KeyError, TypeError): pass
    return None


def word_record(w):
    return {'w':w.word.strip(),'s':round(float(w.start),3),'e':round(float(w.end),3),'p':round(float(w.probability),3)}


def transcribe(media, model_name, language, glossary, download):
    # Decoding through FFmpeg avoids faster-whisper's PyAV path and its version constraints.
    import numpy as np
    from faster_whisper import WhisperModel
    raw = subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(media),'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True,check=True).stdout
    try: model = WhisperModel(model_name, device='cpu', compute_type='int8', local_files_only=not download)
    except Exception as e:
        if download: raise
        raise SystemExit(f'Model {model_name} is not on this machine. Ask before downloading it, then rerun with --download-model. ({type(e).__name__})')
    segments, _ = model.transcribe(np.frombuffer(raw, dtype=np.float32), language=language, word_timestamps=True, vad_filter=True, beam_size=5,
                                   hotwords=' '.join(glossary) or None)
    return [word_record(w) for s in segments for w in s.words]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('media'); p.add_argument('--out', required=True); p.add_argument('--model', default='base.en')
    p.add_argument('--language'); p.add_argument('--glossary', default='', help='comma-separated names to favor, such as product names')
    p.add_argument('--download-model', action='store_true'); p.add_argument('--force', action='store_true')
    a = p.parse_args()
    glossary = [x.strip() for x in a.glossary.split(',') if x.strip()]
    data = None if a.force else cached_transcript(a.media, a.out, a.model, glossary)
    reused = data is not None
    if not reused:
        words = transcribe(a.media, a.model, a.language, glossary, a.download_model)
        data = {'source':Path(a.media).name,'sha256':digest(a.media),'model':a.model,'glossary':glossary,'words':words}
        out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(data), encoding='utf-8')
    words = data['words']
    print(json.dumps({'out':a.out,'reused_cache':reused,'words':len(words),'low_confidence_words':sum(w['p'] < .5 for w in words),'model':a.model}, indent=2))
    return 0


if __name__ == '__main__': sys.exit(main())
