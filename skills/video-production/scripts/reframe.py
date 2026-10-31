#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["opencv-python-headless<5", "numpy>=1.26,<3"]
# ///
"""Choose a horizontal crop position per scene by following detected faces. Experimental.

Run with `uv run reframe.py project.json`, inspect the report, then rerun with --apply.
It uses a frontal-face detector: profiles, backs of heads and non-human subjects need a manual focus_x.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from video_tools import fps_value, scene_frames  # noqa: E402


def choose_focus(faces, previous):
    return statistics.median(faces) if faces else previous


def faces_inside(faces, focus, window):
    left = min(max(0, focus-window/2), 1-window)
    return sum(left <= x <= left+window for x in faces)


def face_center(x, w, width):
    return float(x+w/2)/width


def sample_faces(capture, start, seconds, width, height, detector, cv2, step=.2):
    faces, t = [], start
    while t < start+seconds:
        capture.set(cv2.CAP_PROP_POS_MSEC, t*1000); ok, frame = capture.read(); t += step
        if not ok: continue
        found = detector.detectMultiScale(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 1.15, 6, minSize=(height//10, height//10))
        if len(found):
            x, _, w, _ = max(found, key=lambda r: r[2]*r[3]); faces.append(face_center(x, w, width))
    return faces


def analyze(data, base):
    import cv2
    detector = cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    rate = fps_value(data['spec']['fps']); target = data['spec']['width']/data['spec']['height']
    scenes, previous, captures = [], .5, {}
    for scene in data['scenes']:
        if scene.get('fit') != 'cover': continue
        path = str((Path(base)/scene['asset']).resolve())
        capture = captures.setdefault(path, cv2.VideoCapture(path))
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        seconds = float(scene_frames(scene, rate)/rate); window = min(1, height*target/width)
        faces = sample_faces(capture, scene.get('trim_start', 0), seconds, width, height, detector, cv2)
        focus = round(choose_focus(faces, previous), 4); previous = focus
        scenes.append({'id':scene['id'],'focus_x':focus,'samples_with_face':len(faces),'kept_by_tracking':faces_inside(faces,focus,window),
                       'kept_by_center_crop':faces_inside(faces,.5,window),'needs_visual_check':not faces})
    for capture in captures.values(): capture.release()
    return scenes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest'); p.add_argument('--apply', action='store_true', help='write focus_x into the manifest')
    a = p.parse_args()
    path = Path(a.manifest).resolve(); data = json.loads(path.read_text(encoding='utf-8'))
    scenes = analyze(data, path.parent)
    if a.apply:
        chosen = {x['id']:x['focus_x'] for x in scenes}
        for scene in data['scenes']:
            if scene['id'] in chosen: scene['focus_x'] = chosen[scene['id']]
        fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.json')
        with os.fdopen(fd, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
        os.replace(temp, path)
    print(json.dumps({'applied':a.apply,'scenes':scenes,'kept_by_tracking':sum(x['kept_by_tracking'] for x in scenes),
                      'kept_by_center_crop':sum(x['kept_by_center_crop'] for x in scenes),'samples_with_face':sum(x['samples_with_face'] for x in scenes)}, indent=2))
    return 0


if __name__ == '__main__': sys.exit(main())
