#!/usr/bin/env python3
"""Local-only footage reading, resumable composition, finishing and QC (Python 3.10+)."""
import argparse
import difflib
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'}
HDR_TRANSFERS = {'smpte2084', 'arib-std-b67'}
TONEMAP = 'zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p'
BT709 = 'setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709'
LOW_COVERAGE = 0.6
# Size is a share of the frame's short side; margin_v is a share of height (portrait, landscape).
CAPTION_STYLES = {
    'bold-center': {'size': .08, 'bold': 1, 'upper': True, 'border': 1, 'outline': .08, 'margin_v': (.29, .1)},
    'clean-lower': {'size': .05, 'bold': 0, 'upper': False, 'border': 3, 'outline': .15, 'margin_v': (.24, .07)},
    'minimal': {'size': .04, 'bold': 0, 'upper': False, 'border': 1, 'outline': .05, 'margin_v': (.24, .05)},
}


class VideoError(Exception):
    pass


def run(args, timeout=300, cwd=None):
    try:
        return subprocess.run([str(x) for x in args], capture_output=True, text=True,
                              check=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError as e:
        raise VideoError(f'Missing executable: {args[0]}') from e
    except subprocess.TimeoutExpired as e:
        raise VideoError(f'{args[0]} exceeded {timeout}s; no successful result recorded') from e
    except subprocess.CalledProcessError as e:
        raise VideoError(f'{args[0]} failed: {(e.stderr or e.stdout or "")[-2000:]}') from e


def number(value, positive=False):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > 0 if positive else value >= 0))


def fps_value(value):
    """Exact frame rate from a number or an "N/D" string; None when invalid."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)): return None
    try: rate = Fraction(str(value))
    except (ValueError, ZeroDivisionError): return None
    return rate if 0 < rate <= 120 else None


def scene_frames(scene, rate):
    return max(1, round(Fraction(str(scene['duration'])) * rate))


def is_still(path):
    return Path(path).suffix.lower() in IMAGE_SUFFIXES


def local_path(base, value, roots=()):
    """Resolve a relative asset path; symlinks may only reach the project or an explicit source root."""
    if not isinstance(value, str) or not value or '://' in value or Path(value).is_absolute():
        raise VideoError('asset path must be a nonempty local relative path')
    base = Path(base).resolve()
    path = (base / value).resolve()
    if not any(path.is_relative_to(Path(x).resolve()) for x in (base, *roots)):
        raise VideoError(f'asset path escapes project directory: {value}; pass --source-root for external footage')
    if not path.is_file():
        raise VideoError(f'asset path does not exist: {value}')
    return path


def validate_manifest(data, base, roots=()):
    errors = []
    if not isinstance(data, dict): return ['manifest must be an object']
    if type(data.get('version')) is not int or data['version'] != 1: errors.append('version must be integer 1')
    if not isinstance(data.get('title'), str) or not data['title'].strip(): errors.append('title is required')
    if data.get('mode') not in {'brief', 'preview', 'production', 'repair'}: errors.append('invalid mode')
    if data.get('mode') == 'brief':
        if not isinstance(data.get('brief'), str) or not data['brief'].strip(): errors.append('brief text is required')
        return errors
    s = data.get('spec')
    if not isinstance(s, dict): return errors + ['spec must be an object']
    for key in ('width', 'height'):
        v = s.get(key)
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0 or v % 2: errors.append(f'{key} must be a positive even integer')
    rate = fps_value(s.get('fps'))
    if rate is None: errors.append('fps must be a positive number or N/D rate, at most 120')
    for key in ('min_duration', 'max_duration'):
        if not number(s.get(key), True): errors.append(f'{key} must be a finite positive duration')
    if all(number(s.get(k), True) for k in ('min_duration', 'max_duration')) and s['min_duration'] > s['max_duration']:
        errors.append('min_duration exceeds max_duration')
    if s.get('audio', 'optional') not in {'required', 'optional', 'none'}: errors.append('audio must be required, optional or none')
    assets = data.get('assets')
    listed = set()
    if not isinstance(assets, list): errors.append('assets must be a list'); assets = []
    for a in assets:
        if not isinstance(a, dict): errors.append('asset must be an object'); continue
        p = a.get('path')
        if isinstance(p, str):
            if p in listed: errors.append(f'duplicate asset path: {p}')
            listed.add(p)
        try: local_path(base, p, roots)
        except VideoError as e: errors.append(str(e))
        for key in ('provenance', 'rights'):
            if not isinstance(a.get(key), str) or not a[key].strip(): errors.append(f'asset {key} is required')
    scenes = data.get('scenes')
    if not isinstance(scenes, list) or not scenes: errors.append('scenes must be a nonempty list'); scenes = []
    ids, duration = set(), 0.0
    for scene in scenes:
        if not isinstance(scene, dict): errors.append('scene must be an object'); continue
        sid = scene.get('id')
        if not isinstance(sid, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', sid): errors.append('scene id must be a short lowercase identifier')
        elif sid in ids: errors.append(f'duplicate scene id: {sid}')
        else: ids.add(sid)
        if not number(scene.get('duration'), True): errors.append(f'scene {sid} duration must be finite and positive')
        else: duration += float(scene_frames(scene, rate) / rate) if rate else scene['duration']
        if not number(scene.get('trim_start', 0)): errors.append(f'scene {sid} trim_start must be nonnegative')
        if 'source_audio' in scene and not isinstance(scene['source_audio'], bool): errors.append('source_audio must be boolean')
        errors.extend(framing_errors(scene, sid))
        p = scene.get('asset')
        try: local_path(base, p, roots)
        except VideoError as e: errors.append(str(e))
        if isinstance(p, str) and p not in listed: errors.append(f'scene asset lacks provenance entry: {p}')
    if number(s.get('min_duration'), True) and number(s.get('max_duration'), True):
        tolerance = float(1 / rate) if rate else 0
        if not s['min_duration'] - tolerance <= duration <= s['max_duration'] + tolerance:
            errors.append(f'timeline duration {duration:g}s is outside spec')
    for key in ('narration', 'captions'):
        if data.get(key) is not None:
            try: local_path(base, data[key], roots)
            except VideoError as e: errors.append(f'{key}: {e}')
            if isinstance(data[key], str) and data[key] not in listed: errors.append(f'{key} lacks asset provenance')
    errors.extend(finishing_errors(data, base, listed, roots))
    if data.get('captions') and duration:
        try:
            _, es = parse_srt(local_path(base, data['captions'], roots).read_text(encoding='utf-8-sig'), duration)
            errors.extend(es)
        except (VideoError, UnicodeError, OSError) as e: errors.append(f'captions: {e}')
    return errors


def framing_errors(scene, sid):
    errors = []
    if scene.get('fit', 'contain') not in {'contain', 'cover'}: errors.append(f'scene {sid} fit must be contain or cover')
    for key in ('focus_x', 'focus_y'):
        if key in scene and not (number(scene[key]) and scene[key] <= 1): errors.append(f'scene {sid} {key} must be between 0 and 1')
    crop = scene.get('crop')
    if crop is not None:
        valid = isinstance(crop, dict) and all(number(crop.get(k)) for k in 'xywh') and crop['w'] > 0 and crop['h'] > 0
        if not valid or crop['x'] + crop['w'] > 1 or crop['y'] + crop['h'] > 1:
            errors.append(f'scene {sid} crop must be a rectangle with x, y, w, h inside 0-1')
    return errors


def finishing_errors(data, base, listed, roots):
    errors = []
    music = data.get('music')
    if music is not None:
        if not isinstance(music, dict): errors.append('music must be an object with a path')
        else:
            try: local_path(base, music.get('path'), roots)
            except VideoError as e: errors.append(f'music: {e}')
            if music.get('path') not in listed: errors.append('music lacks asset provenance')
            if 'gain_db' in music and (isinstance(music['gain_db'], bool) or not isinstance(music['gain_db'], (int, float))): errors.append('music gain_db must be a number')
    loudness = data.get('loudness')
    if loudness is not None:
        values = [loudness.get(k) for k in ('target', 'true_peak') if k in loudness] if isinstance(loudness, dict) else [None]
        if 'target' not in (loudness if isinstance(loudness, dict) else {}) or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and x < 0 for x in values):
            errors.append('loudness needs a negative target and optional negative true_peak')
    burn = data.get('burn_captions')
    if burn:
        if not data.get('captions'): errors.append('burn_captions needs a captions file')
        if isinstance(burn, dict) and burn.get('style', 'bold-center') not in CAPTION_STYLES: errors.append(f'burn_captions style must be one of {sorted(CAPTION_STYLES)}')
    return errors


def parse_srt(text, duration):
    cues, errors = [], []
    blocks = re.split(r'\n\s*\n', text.replace('\r\n', '\n').strip())
    previous = 0.0
    pattern = r'(\d{2,}):([0-5]\d):([0-5]\d),(\d{3}) --> (\d{2,}):([0-5]\d):([0-5]\d),(\d{3})'
    for index, block in enumerate(blocks, 1):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].isdigit(): errors.append(f'caption {index}: invalid block'); continue
        match = re.fullmatch(pattern, lines[1])
        if not match: errors.append(f'caption {index}: invalid timestamp'); continue
        v = [int(x) for x in match.groups()]
        start = v[0]*3600 + v[1]*60 + v[2] + v[3]/1000
        end = v[4]*3600 + v[5]*60 + v[6] + v[7]/1000
        if end <= start: errors.append(f'caption {index}: end must follow start')
        if start < previous - 0.001: errors.append(f'caption {index}: overlap with preceding cue')
        if end > duration + 0.05: errors.append(f'caption {index}: beyond video duration')
        body = '\n'.join(lines[2:]).strip()
        if not body: errors.append(f'caption {index}: empty text')
        cues.append({'start': start, 'end': end, 'text': body}); previous = end
    return cues, errors


def probe(path):
    return json.loads(run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-show_streams','-show_format','-of','json',path], 60).stdout)


def stream_duration(stream):
    """Use the picture's timeline, never a longer audio/container duration."""
    try:
        value=float(stream.get('duration','nan'))
        if number(value,True):return value
        if 'duration_ts' in stream and 'time_base' in stream:
            n,d=stream['time_base'].split('/');value=float(stream['duration_ts'])*float(n)/float(d)
            if number(value,True):return value
        tag=stream.get('tags',{}).get('DURATION')
        if tag:
            h,m,s=tag.split(':');value=int(h)*3600+int(m)*60+float(s)
            if number(value,True):return value
    except (ValueError,TypeError,ZeroDivisionError):pass
    return None


def display_size(stream):
    w, h = stream.get('width'), stream.get('height')
    rotation = next((x.get('rotation') for x in stream.get('side_data_list', []) if 'rotation' in x), 0)
    return (h, w) if rotation and abs(int(rotation)) % 180 == 90 else (w, h)


def picture_coverage(path):
    """Share of the frame holding picture, from sampled black-border detection."""
    log = subprocess.run(['ffmpeg','-nostdin','-hide_banner','-i',str(path),'-vf','fps=2,cropdetect=limit=24:round=2:reset=1:skip=0','-an','-f','null','-'],
                         capture_output=True, text=True, timeout=600).stderr
    info = next(x for x in probe(path)['streams'] if x.get('codec_type') == 'video')
    areas = sorted(int(w) * int(h) for w, h in re.findall(r'crop=(\d+):(\d+):', log))
    return round(areas[len(areas)//2] / (info['width'] * info['height']), 3) if areas else None


def lint_captions(cues, max_chars=42, max_cps=20, min_duration=.5):
    findings = []
    for i, c in enumerate(cues, 1):
        seconds, text = c['end'] - c['start'], c['text'].replace('\n', ' ')
        if max(len(x) for x in c['text'].split('\n')) > max_chars: findings.append({'severity': 'warn', 'check': 'caption_line_length', 'detail': f'cue {i} exceeds {max_chars} characters per line', 'start': c['start']})
        if seconds > 0 and len(text) / seconds > max_cps: findings.append({'severity': 'warn', 'check': 'caption_speed', 'detail': f'cue {i} runs at {len(text)/seconds:.0f} characters per second', 'start': c['start']})
        if seconds < min_duration: findings.append({'severity': 'warn', 'check': 'caption_duration', 'detail': f'cue {i} shows for {seconds:.2f}s', 'start': c['start']})
    return findings


def qc_media(path, spec, duration, has_audio, cues=None, loudness_target=None):
    """Flag suspicious intervals for a person or agent to interpret; intended fades and holds are legitimate."""
    args = ['ffmpeg','-nostdin','-hide_banner','-i',str(path),'-vf','blackdetect=d=0.5:pix_th=0.05,freezedetect=n=0.002:d=2']
    args += ['-af','silencedetect=n=-50dB:d=1.5,ebur128=peak=true'] if has_audio else ['-an']
    log = subprocess.run(args+['-f','null','-'],capture_output=True,text=True,timeout=max(120,duration*8)).stderr
    findings, measures = [], {'picture_coverage': picture_coverage(path)}
    def add(severity, check, detail, start=None):
        findings.append({'severity':severity,'check':check,'detail':detail,**({'start':start} if start is not None else {})})
    black = [(float(a),float(b)) for a,b in re.findall(r'black_start:([\d.]+) black_end:[\d.]+ black_duration:([\d.]+)',log)]
    measures['black_seconds'] = round(sum(x[1] for x in black),3)
    if measures['black_seconds'] >= duration*.9: add('fail','black',f'{measures["black_seconds"]}s of {duration:.2f}s is black')
    else:
        for start, seconds in black: add('warn','black_interval',f'{seconds:.2f}s of black',start)
    for start, seconds in re.findall(r'freeze_start: ([\d.]+)[\s\S]*?freeze_duration: ([\d.]+)',log): add('warn','frozen',f'{float(seconds):.2f}s without picture change',float(start))
    coverage = measures['picture_coverage']
    if coverage is not None and coverage < LOW_COVERAGE and measures['black_seconds'] < duration*.9: add('warn','coverage',f'picture fills about {coverage:.0%} of the frame')
    if has_audio:
        summary = log[log.rfind('Summary:'):]
        def level(pattern):
            m = re.search(pattern, summary)
            try: return float(m.group(1)) if m and number(abs(float(m.group(1)))) else None
            except ValueError: return None
        measures['lufs'], measures['lra'], measures['true_peak'] = level(r'I:\s+(-?[\d.]+|-?inf) LUFS'), level(r'LRA:\s+(-?[\d.]+) LU'), level(r'Peak:\s+(-?[\d.]+|-?inf) dBFS')
        silence = [(float(a),float(b)) for a,b in re.findall(r'silence_start: ([\d.]+)[\s\S]*?silence_duration: ([\d.]+)',log)]
        measures['silent_seconds'] = round(sum(x[1] for x in silence),3)
        if measures['lufs'] is None or measures['lufs'] <= -60 or measures['silent_seconds'] >= duration*.9:
            add('fail' if spec.get('audio') == 'required' else 'warn','silent','the audio track is effectively silent')
        else:
            for start, seconds in silence: add('warn','silence',f'{seconds:.2f}s of silence',start)
            if loudness_target is not None and abs(measures['lufs']-loudness_target) > 1.5: add('warn','loudness',f'{measures["lufs"]} LUFS against a {loudness_target} target')
            if measures['true_peak'] is not None and measures['true_peak'] > -.5: add('warn','true_peak',f'peak of {measures["true_peak"]} dB risks clipping after encoding')
    if cues: findings += lint_captions(cues)
    severities = {x['severity'] for x in findings}
    return {'status':'fail' if 'fail' in severities else 'warn' if severities else 'pass','findings':findings,'measures':measures}


def verify_media(path, spec=None, captions=None, decode=True, deep_qc=False, loudness_target=None):
    spec = spec or {}
    result = {'file': str(path), 'technical_pass': False, 'errors': [], 'checks': {},
              'review': {'visual': 'not_performed', 'listening': 'not_performed', 'user_approval': 'not_requested'}}
    try:
        p = Path(path)
        if not p.is_file() or not p.stat().st_size: raise VideoError('output file missing or empty')
        info = probe(p); streams = info.get('streams', [])
        videos = [x for x in streams if x.get('codec_type') == 'video']
        audios = [x for x in streams if x.get('codec_type') == 'audio']
        if not videos: raise VideoError('video stream missing')
        v = videos[0]
        duration = float(info.get('format', {}).get('duration', 'nan'))
        if not number(duration, True): raise VideoError('non-finite or missing media duration')
        fps_string = v.get('avg_frame_rate', '0/1'); n, d = fps_string.split('/')
        fps = float(n)/float(d) if float(d) else 0
        picture_duration=stream_duration(v)
        result.update({'duration': duration, 'video_duration':picture_duration, 'width': v.get('width'), 'height': v.get('height'),
                       'fps': fps, 'video_codec': v.get('codec_name'), 'pixel_format': v.get('pix_fmt'),
                       'audio_streams': len(audios), 'bytes': p.stat().st_size})
        errors = result['errors']
        for key in ('width','height'):
            if key in spec and result[key] != spec[key]: errors.append(f'{key} mismatch: {result[key]} vs {spec[key]}')
        if 'fps' in spec and abs(fps-float(fps_value(spec['fps']))) > 0.02: errors.append('fps mismatch')
        tolerance = max(0.08, 1 / max(fps, 1))
        if duration < spec.get('min_duration', 0)-tolerance or duration > spec.get('max_duration', math.inf)+tolerance:
            errors.append('duration outside requested range')
        if picture_duration is None:errors.append('video stream duration unavailable; container duration is insufficient')
        elif picture_duration < spec.get('min_duration',0)-tolerance or picture_duration > spec.get('max_duration',math.inf)+tolerance:
            errors.append('video stream duration outside requested range')
        elif abs(picture_duration-duration)>max(0.15,2/max(fps,1)):
            errors.append('video stream does not span the container timeline')
        if 'frames' in spec:
            counted = run(['ffprobe','-v','error','-select_streams','v:0','-count_packets','-show_entries','stream=nb_read_packets','-of','csv=p=0',p],120).stdout.strip().strip(',')
            result['frames'] = int(counted)
            if result['frames'] != spec['frames']: errors.append(f'frame count mismatch: {counted} vs {spec["frames"]}')
        if spec.get('audio') == 'required' and not audios: errors.append('required audio stream missing')
        if spec.get('audio') == 'none' and audios: errors.append('unexpected audio stream')
        result['checks']['metadata'] = 'pass' if not errors else 'fail'
        if decode:
            run(['ffmpeg','-v','error','-xerror','-protocol_whitelist','file,pipe','-i',p,'-map','0:v:0','-map','0:a?','-f','null','-'], max(120, duration*4))
            result['checks']['full_decode'] = 'pass'
        else: result['checks']['full_decode'] = 'not_performed'
        cues = None
        if captions:
            cues, es = parse_srt(Path(captions).read_text(encoding='utf-8-sig'), duration)
            errors.extend(es); result['checks']['caption_timing'] = 'pass' if not es else 'fail'
            result['caption_count'] = len(cues)
        else: result['checks']['caption_timing'] = 'not_requested'
        if deep_qc: result['qc'] = qc_media(p,spec,duration,bool(audios),cues,loudness_target)
        result['technical_pass'] = not errors and decode
    except (VideoError, OSError, ValueError, TypeError, KeyError, ZeroDivisionError) as e:
        result['errors'].append(str(e))
    return result


def file_digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def scene_key(scene, spec, base, tool_version, roots=()):
    payload = {'scene': scene, 'spec': spec, 'tool_version': tool_version,
               'input_sha256': file_digest(local_path(base, scene['asset'], roots)), 'pipeline': 3}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


def read_manifest(path, roots=()):
    p = Path(path).resolve()
    try: data = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e: raise VideoError(f'cannot load manifest: {e}') from e
    errors = validate_manifest(data, p.parent, roots)
    if errors: raise VideoError('; '.join(errors))
    return data, p.parent


def filter_names():
    listing = run(['ffmpeg','-v','error','-filters'],60).stdout
    return {x.split()[1] for x in listing.splitlines() if len(x.split()) > 1 and '->' in x}


def picture_filter(scene, s, stream, tone_map):
    """Per-scene picture chain. Timestamps reset before fps so the first frame of a cut survives."""
    w, h, parts = s['width'], s['height'], []
    if tone_map: parts.append(TONEMAP)
    crop = scene.get('crop')
    if crop: parts.append(f"crop=iw*{crop['w']}:ih*{crop['h']}:iw*{crop['x']}:ih*{crop['y']}")
    if scene.get('fit', 'contain') == 'cover':
        fx, fy = scene.get('focus_x', .5), scene.get('focus_y', .5)
        parts += [f'scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos:out_color_matrix=bt709',
                  f"crop={w}:{h}:'max(0,min(iw-{w},iw*{fx}-{w}/2))':'max(0,min(ih-{h},ih*{fy}-{h}/2))'"]
    else:
        parts += [f'scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos:out_color_matrix=bt709',
                  f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2']
    return ','.join(parts + ['setsar=1','setpts=PTS-STARTPTS',f'fps={s["fps"]}'])


def scene_coverage(scene, s, stream):
    w, h = display_size(stream)
    if not w or not h or scene.get('fit', 'contain') != 'contain': return 1.0
    crop = scene.get('crop') or {'w': 1, 'h': 1}
    source, target = w * crop['w'] / (h * crop['h']), s['width'] / s['height']
    return min(source / target, target / source)


def render_mix(data, base, roots, work, listing, total, warnings):
    """Render narration or scene audio plus ducked music to a WAV, then normalize it in two passes."""
    base_audio = ['-f','concat','-safe','1','-i',listing]
    if data.get('narration'):
        narration = local_path(base,data['narration'],roots); info = probe(narration)
        if not any(x.get('codec_type')=='audio' for x in info.get('streams',[])): raise VideoError('narration has no audio stream')
        if float(info.get('format',{}).get('duration','inf')) > total+0.05: raise VideoError('narration exceeds timeline; adjust scenes instead of truncating speech')
        base_audio = ['-protocol_whitelist','file,pipe','-i',narration]
    args = ['ffmpeg','-nostdin','-y','-v','error',*base_audio]
    graph = f'[0:a:0]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{total}[main]'
    music = data.get('music')
    if music:
        args += ['-stream_loop','-1','-i',local_path(base,music['path'],roots)]
        fade = min(1.5,total/4)
        graph += f';[1:a:0]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total},volume={music.get("gain_db",-18)}dB,afade=t=in:st=0:d={fade},afade=t=out:st={total-fade}:d={fade}[bed]'
        if music.get('duck',True):
            graph += ';[main]asplit=2[lead][key];[bed][key]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[ducked];[lead][ducked]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[out]'
        else: graph += ';[main][bed]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[out]'
    else: graph += ';[main]anull[out]'
    mix = work/'mix.wav'
    run(args+['-filter_complex',graph,'-map','[out]','-c:a','pcm_s24le',mix],max(120,total*4))
    loudness = data.get('loudness')
    if not loudness: return mix
    target, peak = loudness['target'], loudness.get('true_peak',-1)
    base_filter = f'loudnorm=I={target}:TP={peak}:LRA=11'
    log = run(['ffmpeg','-nostdin','-hide_banner','-i',mix,'-af',f'{base_filter}:print_format=json','-f','null','-'],max(120,total*4)).stderr
    measured = json.loads(log[log.rindex('{'):log.rindex('}')+1])
    if not number(abs(float(measured['input_i']))):
        warnings.append('loudness normalization skipped: the mix is silent'); return mix
    second = f"{base_filter}:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:linear=true"
    final = work/'final.wav'
    run(['ffmpeg','-nostdin','-y','-v','error','-i',mix,'-af',second+',aresample=48000','-c:a','pcm_s24le',final],max(120,total*4))
    return final


def cues_to_ass(cues, s, burn):
    """Word-safe ASS captions sized from the frame, so one style works at any resolution."""
    options = burn if isinstance(burn, dict) else {}
    style = CAPTION_STYLES[options.get('style','bold-center')]
    w, h = s['width'], s['height']; short = min(w,h)
    size, margin = round(short*style['size']), round(h*style['margin_v'][0 if h > w else 1])
    font = re.sub(r'[,\n]','',str(options.get('font','Arial')))
    def stamp(v):
        cs = round(v*100); return f'{cs//360000}:{cs%360000//6000:02}:{cs%6000//100:02}.{cs%100:02}'
    lines = ['[Script Info]','ScriptType: v4.00+',f'PlayResX: {w}',f'PlayResY: {h}','WrapStyle: 0','ScaledBorderAndShadow: yes','','[V4+ Styles]',
             'Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding',
             f"Style: Caption,{font},{size},&H00FFFFFF,&H000000FF,&H00101010,&H80000000,{style['bold']},0,0,0,100,100,0,0,{style['border']},{round(size*style['outline'],1)},0,2,{round(w*.08)},{round(w*.08)},{margin},1",
             '','[Events]','Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text']
    for c in cues:
        text = c['text'].upper() if style['upper'] else c['text']
        text = text.replace('\\','\\\\').replace('{','\\{').replace('}','\\}').replace('\n','\\N')
        lines.append(f"Dialogue: 0,{stamp(c['start'])},{stamp(c['end'])},Caption,,0,0,0,,{text}")
    return '\n'.join(lines)+'\n'


def caption_overflow(cues, s, burn, glyph_width=.62):
    """Numbers of cues likely to wrap past two lines at the burn size. The width is an average, so check frames for near misses."""
    options = burn if isinstance(burn, dict) else {}
    style = CAPTION_STYLES[options.get('style','bold-center')]
    size = round(min(s['width'],s['height'])*style['size']); usable = s['width']*.84
    return [i for i, c in enumerate(cues, 1) if sum(math.ceil(len(x)*glyph_width*size/usable) for x in c['text'].split('\n')) > 2]


def compose(manifest_path, output, cache=None, overwrite=False, source_roots=()):
    data, base = read_manifest(manifest_path, source_roots)
    if data['mode'] == 'brief': raise VideoError('brief mode does not render media')
    out = Path(output).resolve()
    if out.suffix.lower() != '.mp4': raise VideoError('compose output must be .mp4')
    if out.exists() and not overwrite: raise VideoError('output exists; use --overwrite explicitly')
    sources = {local_path(base, a['path'], source_roots) for a in data['assets']}
    if out in sources or out==Path(manifest_path).resolve(): raise VideoError('output cannot replace a source asset or manifest')
    cache = Path(cache).resolve() if cache else base / '.cache/video-production'
    cache.mkdir(parents=True, exist_ok=True); out.parent.mkdir(parents=True, exist_ok=True)
    s = data['spec']; version = run(['ffmpeg','-version'],60).stdout.splitlines()[0]; rate = fps_value(s['fps'])
    chunks, rendered, reused, warnings, snapped, tone_mapped = [], [], [], [], [], []
    # Source preflight precedes rendering, so a later bad scene cannot produce a partial final.
    infos = []
    for scene in data['scenes']:
        source = local_path(base, scene['asset'], source_roots); info = probe(source); still = is_still(source)
        vs=next((x for x in info.get('streams',[]) if x.get('codec_type')=='video'),{})
        frames = scene_frames(scene, rate); seconds = float(frames / rate)
        if abs(seconds - scene['duration']) > 1e-6: snapped.append({'id':scene['id'],'requested':scene['duration'],'actual':round(seconds,6),'frames':frames})
        if still and scene.get('source_audio'): raise VideoError(f'scene {scene["id"]}: a still image has no source audio')
        if still and scene.get('trim_start'): raise VideoError(f'scene {scene["id"]}: a still image cannot be trimmed')
        if not any(x.get('codec_type') == 'video' for x in info.get('streams',[])):
            raise VideoError(f'scene {scene["id"]}: source has no video')
        dur=stream_duration(vs)
        if not still and (not number(dur, True) or scene.get('trim_start',0)+seconds > dur+0.05):
            raise VideoError(f'scene {scene["id"]}: requested trim exceeds source duration')
        if scene.get('source_audio') and not any(x.get('codec_type')=='audio' for x in info.get('streams',[])):
            raise VideoError(f'scene {scene["id"]}: requested source audio is missing')
        tone_map = vs.get('color_transfer') in HDR_TRANSFERS
        if tone_map:
            if not {'zscale','tonemap'} <= filter_names(): raise VideoError(f'scene {scene["id"]}: HDR source needs FFmpeg zscale and tonemap filters')
            tone_mapped.append(scene['id'])
        coverage = scene_coverage(scene, s, vs)
        if coverage < LOW_COVERAGE: warnings.append(f'scene {scene["id"]}: picture coverage {coverage:.0%} with fit=contain; use fit=cover or crop to fill the frame')
        infos.append((scene, source, info, vs, frames, seconds, still, tone_map))
    for scene, source, info, vs, frames, seconds, still, tone_map in infos:
        key = scene_key(scene,s,base,version,source_roots); chunk = cache / f'{key}.mp4'
        expected = {**s, 'min_duration':seconds, 'max_duration':seconds, 'audio':'required', 'frames':frames}
        if chunk.exists() and verify_media(chunk,expected)['technical_pass']:
            reused.append(scene['id']); chunks.append(chunk); continue
        temporary = cache / f'{key}.{os.getpid()}.partial.mp4'
        has_audio = any(x.get('codec_type') == 'audio' for x in info.get('streams',[]))
        args = ['ffmpeg','-nostdin','-y','-v','error','-protocol_whitelist','file,pipe']
        args += ['-loop','1','-framerate',str(s['fps']),'-i',source] if still else ['-ss',str(scene.get('trim_start',0)),'-i',source]
        source_audio = scene.get('source_audio',False) and has_audio
        if not source_audio: args += ['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
        filt = picture_filter(scene,s,vs,tone_map)+f',tpad=stop_mode=clone:stop_duration={seconds},format=yuv420p,{BT709}'
        audio = 'aresample=48000:async=1:first_pts=0,apad'
        if source_audio:
            fade = min(.03, seconds/2)
            audio += f',afade=t=in:st=0:d={fade},afade=t=out:st={seconds-fade}:d={fade}'
        args += ['-t',str(seconds),'-map','0:v:0','-map','0:a:0' if source_audio else '1:a:0',
                 '-vf',filt,'-af',audio,'-c:v','libx264','-preset','fast','-crf','19',
                 '-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2','-movflags','+faststart',temporary]
        try:
            run(args, max(120,seconds*10))
            check = verify_media(temporary,expected)
            if not check['technical_pass']: raise VideoError(f'chunk verification failed: {check["errors"]}')
            temporary.replace(chunk)
        finally:
            temporary.unlink(missing_ok=True)
        chunks.append(chunk); rendered.append(scene['id'])
    total_frames = sum(x[4] for x in infos); total = float(total_frames / rate)
    with tempfile.TemporaryDirectory(prefix='video-compose-',dir=cache) as work:
        work = Path(work)
        # Copy/hardlink to simple generated names: concat never parses user file names.
        for i, chunk in enumerate(chunks):
            try: os.link(chunk,work/f'{i}.mp4')
            except OSError: shutil.copyfile(chunk,work/f'{i}.mp4')
        listing=work/'clips.txt'; listing.write_text(''.join(f"file '{i}.mp4'\n" for i in range(len(chunks))))
        temporary = out.parent / f'.{out.stem}.{os.getpid()}.partial.mp4'
        mixed = None
        if s.get('audio')!='none' and (data.get('narration') or data.get('music') or data.get('loudness')):
            mixed = render_mix(data,base,source_roots,work,listing,total,warnings)
        args = ['ffmpeg','-nostdin','-y','-v','error','-protocol_whitelist','file,pipe','-f','concat','-safe','1','-i',listing]
        args += ['-i',mixed,'-map','0:v:0','-map','1:a:0'] if mixed else ['-map','0:v:0','-map','0:a:0']
        if data.get('burn_captions'):
            if 'ass' not in filter_names(): raise VideoError('burning captions needs an FFmpeg build with the ass filter (libass)')
            cues,_ = parse_srt(local_path(base,data['captions'],source_roots).read_text(encoding='utf-8-sig'),total)
            (work/'captions.ass').write_text(cues_to_ass(cues,s,data['burn_captions']),encoding='utf-8')
            long_cues = caption_overflow(cues,s,data['burn_captions'])
            if long_cues: warnings.append(f'captions {long_cues} likely wrap past two lines at this style; lower --max-chars or use a smaller style, then check the frames')
            # Captions are burned last so no overlay or scale can cover or soften them.
            # Re-encoding concat input starts a frame late, so reset timestamps and count frames instead of using -t.
            args += ['-frames:v',str(total_frames),'-vf',f'setpts=PTS-STARTPTS,fps={s["fps"]},ass=captions.ass,format=yuv420p,{BT709}','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p']
            if s.get('audio')!='none': args += ['-af',f'atrim=0:{total}']
        else: args += ['-t',str(total),'-c:v','copy']
        args += ['-an'] if s.get('audio')=='none' else ['-c:a','aac','-b:a','192k','-ar','48000','-ac','2']
        args += ['-movflags','+faststart',temporary]
        try:
            run(args,max(120,total*(8 if data.get('burn_captions') else 4)),work)
            report=verify_media(temporary,{**s,'frames':total_frames},local_path(base,data['captions'],source_roots) if data.get('captions') else None)
            if not report['technical_pass']: raise VideoError(f'final verification failed: {report["errors"]}')
            temporary.replace(out)
        finally: temporary.unlink(missing_ok=True)
    return {'output':str(out),'rendered_scenes':rendered,'reused_scenes':reused,'snapped_scenes':snapped,
            'tone_mapped_scenes':tone_mapped,'warnings':warnings,'technical_pass':True,'visual_review':'not_performed','listening_review':'not_performed'}


def load_words(data):
    return data['words'] if isinstance(data, dict) else data


def pack_words(data, label='', gap=.5, low=.5):
    """Phrase-level transcript: the cheap primary reading view of footage. ?word? marks low confidence."""
    words, phrases = load_words(data), []
    for w in words:
        if phrases and w['s']-phrases[-1][-1]['e'] < gap: phrases[-1].append(w)
        else: phrases.append([w])
    lines = [f'## {label}'] if label else []
    for ph in phrases:
        text = ' '.join(f"?{w['w']}?" if w.get('p',1) < low else w['w'] for w in ph)
        lines.append(f"[{ph[0]['s']:06.2f}-{ph[-1]['e']:06.2f}] {text}")
    return '\n'.join(lines)


def ranges_to_scenes(asset, ranges, fps=30, pad_before=.05, pad_after=.08, shots=()):
    """Scenes for kept time ranges: padded so word edges survive, merged, and split at shot changes."""
    rate = fps_value(fps); merged = []
    for a, b in sorted(ranges):
        a, b = max(0, a-pad_before), b+pad_after
        if merged and a <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], b)
        else: merged.append([a, b])
    scenes = []
    for a, b in merged:
        points = [a]+[x for x in sorted(shots) if a < x < b]+[b]
        for x, y in zip(points, points[1:]):
            frames = round(Fraction(str(round(y-x,6)))*rate)
            if frames >= 2: scenes.append({'id':f'cut-{len(scenes)+1:03}','asset':asset,'trim_start':round(x,3),'duration':round(float(frames/rate),6),'source_audio':True})
    return scenes


def map_words(scenes, by_asset, fps=30):
    """Move source-time words onto the output timeline, dropping words the edit removed."""
    rate, offset, mapped = fps_value(fps), 0.0, []
    for scene in scenes:
        seconds, trim = float(scene_frames(scene, rate)/rate), scene.get('trim_start', 0)
        for w in by_asset.get(scene['asset'], []):
            if trim <= (w['s']+w['e'])/2 < trim+seconds:
                mapped.append({**w,'s':offset+max(0,w['s']-trim),'e':offset+min(seconds,w['e']-trim)})
        offset += seconds
    return mapped


def wrap_line(text, width=42):
    if len(text) <= width: return text
    words = text.split(); best = None
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        if best is None or max(len(a),len(b)) < max(len(x) for x in best): best = (a,b)
    return '\n'.join(best) if best else text


def words_to_cues(words, max_chars=32, max_gap=.6, min_duration=.7, low=.5):
    """Group timed words into caption cues, breaking at sentence ends, pauses and the length limit.

    A piece too short to read rejoins its unfinished sentence. Whole sentences stay apart, and the lint reports fast ones.
    """
    sentence_end = lambda x: re.search(r'[.!?]["\')]?$',x['w'])
    wording = lambda g: ' '.join(x['w'] for x in g)
    groups = []
    for w in words:
        current = groups[-1] if groups else None
        fits = current and len(wording(current))+1+len(w['w']) <= max_chars
        if fits and w['s']-current[-1]['e'] <= max_gap and not sentence_end(current[-1]): current.append(w)
        else: groups.append([w])
    joined = []
    for i, g in enumerate(groups):
        following = groups[i+1][0]['s'] if i+1 < len(groups) else g[-1]['e']+min_duration
        if (joined and not sentence_end(joined[-1][-1]) and g[0]['s']-joined[-1][-1]['e'] <= max_gap
                and following-g[0]['s'] < .5 and len(wording(joined[-1]+g)) <= max_chars*1.3): joined[-1] = joined[-1]+g
        else: joined.append(g)
    groups = joined
    cues = [{'start':round(g[0]['s'],3),'end':round(max(g[-1]['e'],g[0]['s']+min_duration),3),'text':wrap_line(' '.join(x['w'] for x in g)),
             'uncertain':[x['w'] for x in g if x.get('p',1) < low]} for g in groups]
    for a, b in zip(cues, cues[1:]): a['end'] = min(a['end'], b['start'])
    return cues


def cues_to_srt(cues):
    def stamp(v):
        ms = round(v*1000); return f'{ms//3600000:02}:{ms%3600000//60000:02}:{ms%60000//1000:02},{ms%1000:03}'
    return ''.join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n\n" for i, c in enumerate(cues, 1))


def speech_check(words, cues, min_similarity=.7, min_inside=.8):
    """Compare captions with a fresh transcript of the export: a warning signal, since ASR makes mistakes too."""
    norm = lambda text: re.sub(r"[^\w' ]", '', text.lower()).split()
    spoken = [x for w in words for x in norm(w['w'])]; shown = [x for c in cues for x in norm(c['text'])]
    similarity = difflib.SequenceMatcher(None, shown, spoken, autojunk=False).ratio()
    inside = sum(any(c['start']-.15 <= (w['s']+w['e'])/2 <= c['end']+.15 for c in cues) for w in words)/max(1,len(words))
    return {'text_similarity':round(similarity,3),'spoken_words_inside_cues':round(inside,3),'spoken_words':len(spoken),'caption_words':len(shown),
            'status':'pass' if similarity >= min_similarity and inside >= min_inside else 'warn'}


def detect_shots(media, threshold=10):
    out = run(['ffmpeg','-nostdin','-v','error','-i',media,'-an','-vf',f'scdet=t={threshold},metadata=print:key=lavfi.scd.time:file=-','-f','null','-'],900).stdout
    return sorted({float(x) for x in re.findall(r'lavfi\.scd\.time=([\d.]+)',out)})


def timeline(media, start, end, output, words=None, columns=6):
    """Filmstrip above a waveform for one time range: what an agent uses in place of watching and listening."""
    info = probe(media); streams = info.get('streams',[])
    v = next((x for x in streams if x.get('codec_type')=='video'),None)
    if not v: raise VideoError('timeline needs a video stream')
    seconds = end-start
    if seconds <= 0: raise VideoError('timeline end must follow start')
    dw, dh = display_size(v); thumb_h = 180 if dw >= dh else 320; thumb_w = 2*round(thumb_h*dw/dh/2)
    output = Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='video-timeline-') as work:
        strip = Path(work)/'strip.png'
        run(['ffmpeg','-nostdin','-y','-v','error','-ss',start,'-t',seconds,'-i',media,'-vf',f'fps={columns}/{seconds},scale={thumb_w}:{thumb_h},tile={columns}x1','-frames:v','1',strip],120)
        if any(x.get('codec_type')=='audio' for x in streams):
            wave = Path(work)/'wave.png'
            run(['ffmpeg','-nostdin','-y','-v','error','-ss',start,'-t',seconds,'-i',media,'-filter_complex',f'[0:a:0]aformat=channel_layouts=mono,showwavespic=s={thumb_w*columns}x120:colors=white','-frames:v','1',wave],120)
            run(['ffmpeg','-nostdin','-y','-v','error','-i',strip,'-i',wave,'-filter_complex','[0]format=rgb24[a];[1]format=rgba,colorchannelmixer=aa=1,format=rgb24[b];[a][b]vstack','-frames:v','1',output],60)
        else: shutil.copyfile(strip,output)
    said = []
    if words:
        said = [w for w in load_words(json.loads(Path(words).read_text())) if start <= w['s'] < end]
    return {'image':str(output),'start':start,'end':end,'columns':columns,'frame_times':[round(start+(i+.5)*seconds/columns,3) for i in range(columns)],'words':said}


def review(media, manifest_path, out_dir, max_views=12, window=1.0):
    """Timeline images at the opening, ending and each cut of an export, for review before anyone else sees it."""
    data = json.loads(Path(manifest_path).read_text(encoding='utf-8')); rate = fps_value(data['spec']['fps'])
    cuts, cursor = [], 0.0
    for scene in data['scenes'][:-1]:
        cursor += float(scene_frames(scene,rate)/rate); cuts.append(round(cursor,3))
    duration = float(probe(media)['format']['duration'])
    room = max(0,max_views-2)
    shown = cuts if len(cuts) <= room else [cuts[round(i*(len(cuts)-1)/max(1,room-1))] for i in range(room)] if room else []
    views = [('opening',0,min(2,duration)),('ending',max(0,duration-2),duration)]+[(f'cut:{c:.3f}',max(0,c-window),min(duration,c+window)) for c in shown]
    out = Path(out_dir); result = []
    for i,(label,start,end) in enumerate(views):
        image = out/f'view-{i:02}.png'
        timeline(media,start,end,image); result.append({'label':label,'start':round(start,3),'end':round(end,3),'image':str(image)})
    return {'views':result,'cuts':len(cuts),'cuts_not_shown':len(cuts)-len(shown)}


def doctor():
    tools = {x: shutil.which(x) for x in ('ffmpeg','ffprobe','python3','node','npx','uv','say','espeak-ng','espeak','piper','whisper-cli')}
    capabilities={};error=None;names=set()
    if tools['ffmpeg'] and tools['ffprobe']:
        try:
            encoders=run(['ffmpeg','-v','error','-encoders'],60).stdout
            names=filter_names()
            capabilities={name:bool(re.search(r'\b'+name+r'\b',encoders)) for name in ('libx264','aac')}
            capabilities.update({name:name in names for name in ('scale','pad','fps','aresample','apad','anullsrc')})
        except VideoError as e:error=str(e)
    ready=bool(capabilities) and all(capabilities.values()) and not error
    def route(*filters):
        missing=[x for x in filters if x not in names]
        return 'ready' if ready and not missing else 'missing: '+', '.join(missing or ['ffmpeg'])
    def script(module):
        if importlib.util.find_spec(module): return 'ready; model or dependency downloads may still be needed'
        return 'runs through uv run; first run downloads dependencies' if tools['uv'] else f'missing: install uv or the {module} Python package'
    routes={'clip_assembly':'ready' if ready else 'missing_dependency','captions_burn':route('ass'),'loudness':route('loudnorm','ebur128'),
            'qc':route('blackdetect','freezedetect','silencedetect','cropdetect','ebur128'),'hdr_tone_map':route('zscale','tonemap'),'shot_detection':route('scdet'),
            'timeline':route('showwavespic','tile','vstack'),'music_ducking':route('sidechaincompress','amix'),
            'transcription':script('faster_whisper'),'reframe':script('cv2'),
            'screen_capture':'requires_host_browser_automation; Playwright recipe in references/screen-workflows.md',
            'narration':'local engine found' if tools['piper'] or tools['espeak-ng'] or tools['espeak'] else 'no redistributable local engine found; check host TTS or use a human recording',
            'motion_graphics':'npx available for HyperFrames or Remotion; not installed by this check' if tools['npx'] else 'missing: Node.js for HyperFrames or Remotion'}
    return {'tools':tools,'capabilities':capabilities,'dependency_error':error,'local_composition':'ready' if ready else 'missing_dependency','routes':routes,
            'browser_capture':'requires_host_browser_automation','generated_video':'requires_authorized_provider_adapter',
            'note':'Availability is not a claim of output quality or provider integration.'}


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    c=sub.add_parser('check'); c.add_argument('manifest'); c.add_argument('--source-root',action='append',default=[])
    v=sub.add_parser('verify'); v.add_argument('media'); v.add_argument('--manifest'); v.add_argument('--captions'); v.add_argument('--report'); v.add_argument('--source-root',action='append',default=[]); v.add_argument('--qc',action='store_true'); v.add_argument('--loudness-target',type=float)
    c=sub.add_parser('compose'); c.add_argument('manifest'); c.add_argument('output'); c.add_argument('--cache'); c.add_argument('--overwrite',action='store_true'); c.add_argument('--source-root',action='append',default=[])
    x=sub.add_parser('pack',help='phrase-level transcript for reading'); x.add_argument('words',nargs='+')
    x=sub.add_parser('shots',help='detect hard shot changes'); x.add_argument('media'); x.add_argument('--threshold',type=float,default=10)
    x=sub.add_parser('cuts',help='turn kept ranges into manifest scenes'); x.add_argument('asset'); x.add_argument('--ranges',required=True,help='3.12-3.84,4.76-6.32'); x.add_argument('--fps',default='30'); x.add_argument('--pad-before',type=float,default=.05); x.add_argument('--pad-after',type=float,default=.08); x.add_argument('--media',help='also split at shot changes found in this file')
    x=sub.add_parser('captions',help='word timings to output-timeline SRT'); x.add_argument('manifest'); x.add_argument('--words',action='append',required=True,metavar='ASSET=WORDS.json'); x.add_argument('--out',required=True); x.add_argument('--max-chars',type=int,default=32); x.add_argument('--overwrite',action='store_true')
    x=sub.add_parser('timeline',help='filmstrip and waveform PNG for a time range'); x.add_argument('media'); x.add_argument('--start',type=float,required=True); x.add_argument('--end',type=float,required=True); x.add_argument('--out',required=True); x.add_argument('--words'); x.add_argument('--columns',type=int,default=6)
    x=sub.add_parser('review',help='timeline images at the opening, ending and cuts of an export'); x.add_argument('media'); x.add_argument('--manifest',required=True); x.add_argument('--out',required=True); x.add_argument('--max-views',type=int,default=12)
    x=sub.add_parser('speech-check',help='compare captions with a fresh transcript of the export'); x.add_argument('words'); x.add_argument('captions')
    a=p.parse_args()
    try:
        if a.command=='pack':
            print('\n\n'.join(pack_words(json.loads(Path(w).read_text()),json.loads(Path(w).read_text()).get('source',w) if isinstance(json.loads(Path(w).read_text()),dict) else w) for w in a.words))
            return 0
        if a.command=='doctor': result=doctor()
        elif a.command=='shots': result={'shots':detect_shots(a.media,a.threshold)}
        elif a.command=='cuts':
            ranges=[tuple(float(y) for y in x.split('-')) for x in a.ranges.split(',')]
            result={'scenes':ranges_to_scenes(a.asset,ranges,a.fps,a.pad_before,a.pad_after,detect_shots(a.media) if a.media else ())}
        elif a.command=='captions':
            data=json.loads(Path(a.manifest).read_text(encoding='utf-8'));out=Path(a.out)
            if out.exists() and not a.overwrite: raise VideoError('captions output exists; use --overwrite explicitly')
            by_asset={k:load_words(json.loads(Path(v).read_text())) for k,v in (x.split('=',1) for x in a.words)}
            mapped=map_words(data['scenes'],by_asset,data['spec']['fps']);cues=words_to_cues(mapped,a.max_chars)
            out.parent.mkdir(parents=True,exist_ok=True);out.write_text(cues_to_srt(cues),encoding='utf-8')
            result={'captions':str(out),'cues':len(cues),'words':len(mapped),'review_words':[{'at':c['start'],'words':c['uncertain'],'cue':c['text']} for c in cues if c['uncertain']],'lint':lint_captions(cues)}
        elif a.command=='timeline': result=timeline(a.media,a.start,a.end,a.out,a.words,a.columns)
        elif a.command=='review': result=review(a.media,a.manifest,a.out,a.max_views)
        elif a.command=='speech-check':
            cues,_=parse_srt(Path(a.captions).read_text(encoding='utf-8-sig'),math.inf)
            result=speech_check(load_words(json.loads(Path(a.words).read_text())),cues)
        elif a.command=='check':
            data,_=read_manifest(a.manifest,a.source_root); result={'valid':True,'mode':data['mode']}
        elif a.command=='verify':
            data,base=read_manifest(a.manifest,a.source_root) if a.manifest else ({},None)
            cap=a.captions or (str(local_path(base,data['captions'],a.source_root)) if data.get('captions') else None)
            result=verify_media(a.media,data.get('spec'),cap,deep_qc=a.qc,loudness_target=a.loudness_target)
            if a.report:
                dest=Path(a.report)
                protected={Path(a.media).resolve()}
                if a.manifest:
                    protected.add(Path(a.manifest).resolve())
                    protected.update(local_path(base,x['path'],a.source_root) for x in data.get('assets',[]))
                if cap: protected.add(Path(cap).resolve())
                if dest.resolve() in protected: raise VideoError('report cannot overwrite an input')
                dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(json.dumps(result,indent=2)+'\n')
        else: result=compose(a.manifest,a.output,a.cache,a.overwrite,a.source_root)
        print(json.dumps(result,indent=2,allow_nan=False))
        return 0 if result.get('technical_pass',True) and result.get('qc',{}).get('status')!='fail' else 1
    except (VideoError, OSError, ValueError) as e:
        print(json.dumps({'error':str(e)}),file=sys.stderr); return 1


if __name__=='__main__': sys.exit(main())
