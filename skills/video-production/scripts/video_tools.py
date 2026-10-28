#!/usr/bin/env python3
"""Local-only production checks and resumable clip composition (Python 3.10+)."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


class VideoError(Exception):
    pass


def run(args, timeout=300):
    try:
        return subprocess.run([str(x) for x in args], capture_output=True, text=True,
                              check=True, timeout=timeout)
    except FileNotFoundError as e:
        raise VideoError(f'Missing executable: {args[0]}') from e
    except subprocess.TimeoutExpired as e:
        raise VideoError(f'{args[0]} exceeded {timeout}s; no successful result recorded') from e
    except subprocess.CalledProcessError as e:
        raise VideoError(f'{args[0]} failed: {(e.stderr or e.stdout or "")[-2000:]}') from e


def number(value, positive=False):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > 0 if positive else value >= 0))


def local_path(base, value):
    if not isinstance(value, str) or not value or '://' in value or Path(value).is_absolute():
        raise VideoError('asset path must be a nonempty local relative path')
    base = Path(base).resolve()
    path = (base / value).resolve()
    if not path.is_relative_to(base):
        raise VideoError('asset path escapes project directory')
    if not path.is_file():
        raise VideoError(f'asset path does not exist: {value}')
    return path


def validate_manifest(data, base):
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
    if not number(s.get('fps'), True) or s.get('fps', 0) > 120: errors.append('fps must be positive and at most 120')
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
        try: local_path(base, p)
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
        else: duration += scene['duration']
        if not number(scene.get('trim_start', 0)): errors.append(f'scene {sid} trim_start must be nonnegative')
        if 'source_audio' in scene and not isinstance(scene['source_audio'], bool): errors.append('source_audio must be boolean')
        p = scene.get('asset')
        try: local_path(base, p)
        except VideoError as e: errors.append(str(e))
        if isinstance(p, str) and p not in listed: errors.append(f'scene asset lacks provenance entry: {p}')
    if number(s.get('min_duration'), True) and number(s.get('max_duration'), True):
        tolerance = 1 / s['fps'] if number(s.get('fps'), True) else 0
        if not s['min_duration'] - tolerance <= duration <= s['max_duration'] + tolerance:
            errors.append(f'timeline duration {duration:g}s is outside spec')
    for key in ('narration', 'captions'):
        if data.get(key) is not None:
            try: local_path(base, data[key])
            except VideoError as e: errors.append(f'{key}: {e}')
            if isinstance(data[key], str) and data[key] not in listed: errors.append(f'{key} lacks asset provenance')
    if data.get('captions') and duration:
        try:
            _, es = parse_srt(local_path(base, data['captions']).read_text(encoding='utf-8-sig'), duration)
            errors.extend(es)
        except (VideoError, UnicodeError, OSError) as e: errors.append(f'captions: {e}')
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


def verify_media(path, spec=None, captions=None, decode=True):
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
        if 'fps' in spec and abs(fps-spec['fps']) > 0.02: errors.append('fps mismatch')
        tolerance = max(0.08, 1 / max(fps, 1))
        if duration < spec.get('min_duration', 0)-tolerance or duration > spec.get('max_duration', math.inf)+tolerance:
            errors.append('duration outside requested range')
        if picture_duration is None:errors.append('video stream duration unavailable; container duration is insufficient')
        elif picture_duration < spec.get('min_duration',0)-tolerance or picture_duration > spec.get('max_duration',math.inf)+tolerance:
            errors.append('video stream duration outside requested range')
        elif abs(picture_duration-duration)>max(0.15,2/max(fps,1)):
            errors.append('video stream does not span the container timeline')
        if spec.get('audio') == 'required' and not audios: errors.append('required audio stream missing')
        if spec.get('audio') == 'none' and audios: errors.append('unexpected audio stream')
        result['checks']['metadata'] = 'pass' if not errors else 'fail'
        if decode:
            run(['ffmpeg','-v','error','-xerror','-protocol_whitelist','file,pipe','-i',p,'-map','0:v:0','-map','0:a?','-f','null','-'], max(120, duration*4))
            result['checks']['full_decode'] = 'pass'
        else: result['checks']['full_decode'] = 'not_performed'
        if captions:
            cues, es = parse_srt(Path(captions).read_text(encoding='utf-8-sig'), duration)
            errors.extend(es); result['checks']['caption_timing'] = 'pass' if not es else 'fail'
            result['caption_count'] = len(cues)
        else: result['checks']['caption_timing'] = 'not_requested'
        result['technical_pass'] = not errors and decode
    except (VideoError, OSError, ValueError, TypeError, KeyError, ZeroDivisionError) as e:
        result['errors'].append(str(e))
    return result


def file_digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def scene_key(scene, spec, base, tool_version):
    payload = {'scene': scene, 'spec': spec, 'tool_version': tool_version,
               'input_sha256': file_digest(local_path(base, scene['asset'])), 'pipeline': 2}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


def read_manifest(path):
    p = Path(path).resolve()
    try: data = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e: raise VideoError(f'cannot load manifest: {e}') from e
    errors = validate_manifest(data, p.parent)
    if errors: raise VideoError('; '.join(errors))
    return data, p.parent


def compose(manifest_path, output, cache=None, overwrite=False):
    data, base = read_manifest(manifest_path)
    if data['mode'] == 'brief': raise VideoError('brief mode does not render media')
    out = Path(output).resolve()
    if out.suffix.lower() != '.mp4': raise VideoError('compose output must be .mp4')
    if out.exists() and not overwrite: raise VideoError('output exists; use --overwrite explicitly')
    sources = {local_path(base, a['path']) for a in data['assets']}
    if out in sources or out==Path(manifest_path).resolve(): raise VideoError('output cannot replace a source asset or manifest')
    cache = Path(cache).resolve() if cache else base / '.cache/video-production'
    cache.mkdir(parents=True, exist_ok=True); out.parent.mkdir(parents=True, exist_ok=True)
    s = data['spec']; version = run(['ffmpeg','-version'],60).stdout.splitlines()[0]
    chunks, rendered, reused = [], [], []
    # Source preflight precedes rendering, so a later bad scene cannot produce a partial final.
    infos = []
    for scene in data['scenes']:
        source = local_path(base, scene['asset']); info = probe(source)
        vs=next((x for x in info.get('streams',[]) if x.get('codec_type')=='video'),{})
        dur=stream_duration(vs)
        if not number(dur, True) or scene.get('trim_start',0)+scene['duration'] > dur+0.05:
            raise VideoError(f'scene {scene["id"]}: requested trim exceeds source duration')
        if not any(x.get('codec_type') == 'video' for x in info.get('streams',[])):
            raise VideoError(f'scene {scene["id"]}: source has no video')
        if scene.get('source_audio') and not any(x.get('codec_type')=='audio' for x in info.get('streams',[])):
            raise VideoError(f'scene {scene["id"]}: requested source audio is missing')
        frames = scene['duration'] * s['fps']
        if abs(frames-round(frames)) > 0.001: raise VideoError('scene durations must align to whole frames')
        infos.append((scene, source, info))
    for scene, source, info in infos:
        key = scene_key(scene,s,base,version); chunk = cache / f'{key}.mp4'
        expected = {**s, 'min_duration':scene['duration'], 'max_duration':scene['duration'], 'audio':'required'}
        if chunk.exists() and verify_media(chunk,expected)['technical_pass']:
            reused.append(scene['id']); chunks.append(chunk); continue
        temporary = cache / f'{key}.{os.getpid()}.partial.mp4'
        has_audio = any(x.get('codec_type') == 'audio' for x in info.get('streams',[]))
        args = ['ffmpeg','-y','-v','error','-protocol_whitelist','file,pipe','-ss',str(scene.get('trim_start',0)),'-i',source]
        source_audio = scene.get('source_audio',False) and has_audio
        if not source_audio: args += ['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
        filt = f'scale={s["width"]}:{s["height"]}:force_original_aspect_ratio=decrease,pad={s["width"]}:{s["height"]}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={s["fps"]}'
        args += ['-t',str(scene['duration']),'-map','0:v:0','-map','0:a:0' if source_audio else '1:a:0',
                 '-vf',filt,'-af','aresample=48000,apad','-c:v','libx264','-preset','fast','-crf','19',
                 '-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2','-movflags','+faststart',temporary]
        try:
            run(args, max(120,scene['duration']*10))
            check = verify_media(temporary,expected)
            if not check['technical_pass']: raise VideoError(f'chunk verification failed: {check["errors"]}')
            temporary.replace(chunk)
        finally:
            temporary.unlink(missing_ok=True)
        chunks.append(chunk); rendered.append(scene['id'])
    total = sum(x['duration'] for x in data['scenes'])
    with tempfile.TemporaryDirectory(prefix='video-compose-',dir=cache) as work:
        work = Path(work)
        # Copy/hardlink to simple generated names: concat never parses user file names.
        for i, chunk in enumerate(chunks):
            try: os.link(chunk,work/f'{i}.mp4')
            except OSError: shutil.copyfile(chunk,work/f'{i}.mp4')
        listing=work/'clips.txt'; listing.write_text(''.join(f"file '{i}.mp4'\n" for i in range(len(chunks))))
        temporary = out.parent / f'.{out.stem}.{os.getpid()}.partial.mp4'
        args = ['ffmpeg','-y','-v','error','-protocol_whitelist','file,pipe','-f','concat','-safe','1','-i',listing]
        if data.get('narration'):
            narration=local_path(base,data['narration'])
            ni=probe(narration)
            if not any(x.get('codec_type')=='audio' for x in ni.get('streams',[])): raise VideoError('narration has no audio stream')
            if float(ni.get('format',{}).get('duration','inf')) > total+0.05: raise VideoError('narration exceeds timeline; adjust scenes instead of truncating speech')
            args += ['-protocol_whitelist','file,pipe','-i',narration,'-map','0:v:0','-map','1:a:0','-af','apad']
        else: args += ['-map','0:v:0','-map','0:a:0']
        args += ['-t',str(total),'-c:v','copy']
        args += ['-an'] if s.get('audio')=='none' else ['-c:a','aac','-ar','48000','-ac','2']
        args += ['-movflags','+faststart',temporary]
        try:
            run(args,max(120,total*4))
            report=verify_media(temporary,s,local_path(base,data['captions']) if data.get('captions') else None)
            if not report['technical_pass']: raise VideoError(f'final verification failed: {report["errors"]}')
            temporary.replace(out)
        finally: temporary.unlink(missing_ok=True)
    return {'output':str(out),'rendered_scenes':rendered,'reused_scenes':reused,
            'technical_pass':True,'visual_review':'not_performed','listening_review':'not_performed'}


def doctor():
    tools = {x: shutil.which(x) for x in ('ffmpeg','ffprobe','python3','node','say','espeak-ng','espeak')}
    capabilities={};error=None
    if tools['ffmpeg'] and tools['ffprobe']:
        try:
            encoders=run(['ffmpeg','-v','error','-encoders'],60).stdout
            filters=run(['ffmpeg','-v','error','-filters'],60).stdout
            capabilities={name:bool(re.search(r'\b'+name+r'\b',encoders)) for name in ('libx264','aac')}
            capabilities.update({name:bool(re.search(r'\b'+name+r'\b',filters)) for name in ('scale','pad','fps','aresample','apad','anullsrc')})
        except VideoError as e:error=str(e)
    ready=bool(capabilities) and all(capabilities.values()) and not error
    return {'tools':tools,'capabilities':capabilities,'dependency_error':error,'local_composition':'ready' if ready else 'missing_dependency',
            'browser_capture':'requires_host_browser_automation','generated_video':'requires_authorized_provider_adapter',
            'note':'Availability is not a claim of output quality or provider integration.'}


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    c=sub.add_parser('check'); c.add_argument('manifest')
    v=sub.add_parser('verify'); v.add_argument('media'); v.add_argument('--manifest'); v.add_argument('--captions'); v.add_argument('--report')
    c=sub.add_parser('compose'); c.add_argument('manifest'); c.add_argument('output'); c.add_argument('--cache'); c.add_argument('--overwrite',action='store_true')
    a=p.parse_args()
    try:
        if a.command=='doctor': result=doctor()
        elif a.command=='check':
            data,_=read_manifest(a.manifest); result={'valid':True,'mode':data['mode']}
        elif a.command=='verify':
            data,base=read_manifest(a.manifest) if a.manifest else ({},None)
            cap=a.captions or (str(local_path(base,data['captions'])) if data.get('captions') else None)
            result=verify_media(a.media,data.get('spec'),cap)
            if a.report:
                dest=Path(a.report)
                protected={Path(a.media).resolve()}
                if a.manifest:
                    protected.add(Path(a.manifest).resolve())
                    protected.update(local_path(base,x['path']) for x in data.get('assets',[]))
                if cap: protected.add(Path(cap).resolve())
                if dest.resolve() in protected: raise VideoError('report cannot overwrite an input')
                dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(json.dumps(result,indent=2)+'\n')
        else: result=compose(a.manifest,a.output,a.cache,a.overwrite)
        print(json.dumps(result,indent=2,allow_nan=False))
        return 0 if result.get('technical_pass',True) else 1
    except (VideoError, OSError, ValueError) as e:
        print(json.dumps({'error':str(e)}),file=sys.stderr); return 1


if __name__=='__main__': sys.exit(main())
