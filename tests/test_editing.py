import array
import importlib.util
import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'skills/video-production/scripts/video_tools.py'
spec = importlib.util.spec_from_file_location('video_tools', MODULE)
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)

HAS_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', *map(str, args)], check=True)


def filter_available(name):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-filters'], capture_output=True, text=True).stdout
    return any(len(line.split()) > 1 and line.split()[1] == name for line in out.splitlines())


def tags(path):
    out = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                   'stream=color_primaries,color_transfer,color_space', '-of', 'json', str(path)])
    return json.loads(out)['streams'][0]


def frame_count(path):
    out = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets',
                                   '-show_entries', 'stream=nb_read_packets', '-of', 'csv=p=0', str(path)], text=True)
    return int(out.strip().strip(','))


def pcm(path):
    raw = subprocess.check_output(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'])
    a = array.array('f'); a.frombytes(raw)
    return a


def luma_box(path, t, crop=None):
    """Mean luma of one frame, optionally inside a w:h:x:y crop."""
    vf = (f'crop={crop},' if crop else '') + 'signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-'
    out = subprocess.check_output(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(t), '-i', str(path), '-frames:v', '1', '-vf', vf, '-f', 'null', '-'], text=True)
    return float(out.split('YAVG=')[1].split()[0])


class Project:
    """A real temporary project directory with a manifest and synthetic source media."""

    def __init__(self, root):
        self.root = Path(root)

    def tone(self, name='src.mp4', seconds=10, size='320x180', rate=30, freq=220):
        ffmpeg('-f', 'lavfi', '-i', f'testsrc2=size={size}:rate={rate}:duration={seconds}',
               '-f', 'lavfi', '-i', f'sine=frequency={freq}:sample_rate=48000:duration={seconds}',
               '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', self.root / name)
        return name

    def manifest(self, scenes, assets=None, **top):
        s = {'width': 320, 'height': 180, 'fps': 30, 'min_duration': 0.01, 'max_duration': 600, 'audio': 'required'}
        s.update(top.pop('spec', {}))
        listed = assets or sorted({x['asset'] for x in scenes})
        m = {'version': 1, 'title': 'Test', 'mode': 'production', 'spec': s, 'scenes': scenes,
             'assets': [{'path': a, 'provenance': 'Synthetic fixture', 'rights': 'Created for this test'} for a in listed], **top}
        p = self.root / 'project.json'; p.write_text(json.dumps(m))
        return p

    def compose(self, scenes, assets=None, **top):
        return video.compose(self.manifest(scenes, assets, **top), self.root / 'out.mp4', overwrite=True)


@unittest.skipUnless(HAS_FFMPEG, 'FFmpeg integration dependencies unavailable')
class EditCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Project(self.tmp.name)
        self.out = self.p.root / 'out.mp4'

    def tearDown(self):
        self.tmp.cleanup()


class CutTests(EditCase):
    def test_transcript_style_cuts_compose_with_exact_frames(self):
        self.p.tone()
        random.seed(7)
        scenes = [{'id': f's{i}', 'asset': 'src.mp4', 'duration': 1, 'trim_start': round(random.uniform(.2, 8), 2), 'source_audio': True} for i in range(6)]
        self.p.compose(scenes)
        self.assertEqual(frame_count(self.out), 180)

    def test_verify_rejects_a_chunk_one_frame_short(self):
        self.p.tone(seconds=2)
        short = self.p.root / 'short.mp4'
        ffmpeg('-i', self.p.root / 'src.mp4', '-frames:v', 59, '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'copy', short)
        report = video.verify_media(short, {'width': 320, 'height': 180, 'fps': 30, 'min_duration': 2, 'max_duration': 2, 'frames': 60})
        self.assertFalse(report['technical_pass'])

    def test_durations_snap_to_whole_frames_and_are_reported(self):
        self.p.tone()
        result = self.p.compose([{'id': 'a', 'asset': 'src.mp4', 'duration': 1.37, 'source_audio': True}])
        self.assertEqual(frame_count(self.out), 41)
        self.assertEqual(result['snapped_scenes'][0]['id'], 'a')

    def test_rational_fps_accepted(self):
        self.p.tone()
        self.p.compose([{'id': 'a', 'asset': 'src.mp4', 'duration': 5}], spec={'fps': '30000/1001', 'audio': 'optional'})
        report = video.verify_media(self.out)
        self.assertAlmostEqual(report['fps'], 30000 / 1001, places=2)

    def test_invalid_fps_string_rejected(self):
        self.p.tone()
        p = self.p.manifest([{'id': 'a', 'asset': 'src.mp4', 'duration': 1}], spec={'fps': 'fast'})
        self.assertTrue(any('fps' in x for x in video.validate_manifest(json.loads(p.read_text()), self.p.root)))

    def test_audio_is_faded_at_every_cut(self):
        self.p.tone()
        scenes = [{'id': f's{i}', 'asset': 'src.mp4', 'duration': 1, 'trim_start': round(i * 7 / 30, 6), 'source_audio': True} for i in range(6)]
        self.p.compose(scenes)
        a = pcm(self.out)
        steps = [abs(a[i + 1] - a[i]) for i in range(len(a) - 1)]
        baseline = max(steps[int(.3 * 48000):int(.7 * 48000)])
        for cut in range(1, 6):
            around = steps[cut * 48000 - 1800:cut * 48000 + 1800]
            self.assertLess(max(around), baseline * 2, f'cut {cut}')

    def test_outputs_are_tagged_bt709(self):
        self.p.tone()
        self.p.compose([{'id': 'a', 'asset': 'src.mp4', 'duration': 1}])
        t = tags(self.out)
        self.assertEqual((t.get('color_primaries'), t.get('color_transfer'), t.get('color_space')), ('bt709', 'bt709', 'bt709'))

    def test_hdr_source_is_tone_mapped_to_bt709(self):
        if not (filter_available('zscale') and filter_available('tonemap')):
            self.skipTest('zscale/tonemap unavailable')
        ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30:duration=2', '-vf', 'format=yuv420p,setparams=colorspace=bt2020nc:color_primaries=bt2020:color_trc=smpte2084',
               '-c:v', 'libx264', '-preset', 'ultrafast', self.p.root / 'hdr.mp4')
        result = self.p.compose([{'id': 'a', 'asset': 'hdr.mp4', 'duration': 1}], spec={'audio': 'optional'})
        t = tags(self.out)
        self.assertEqual((t.get('color_primaries'), t.get('color_transfer')), ('bt709', 'bt709'))
        self.assertEqual(result['tone_mapped_scenes'], ['a'])


class FramingTests(EditCase):
    def half_white(self, name='half.mp4'):
        """Left half white, right half black, so the crop position is measurable."""
        ffmpeg('-f', 'lavfi', '-i', 'color=white:size=640x180:rate=30:duration=2', '-f', 'lavfi', '-i', 'color=black:size=640x180:rate=30:duration=2',
               '-filter_complex', '[0][1]hstack,scale=640:180,format=yuv420p', '-c:v', 'libx264', '-preset', 'ultrafast', self.p.root / name)
        return name

    def test_cover_fills_vertical_frame(self):
        self.p.tone(size='640x180')
        self.p.compose([{'id': 'a', 'asset': 'src.mp4', 'duration': 1, 'fit': 'cover'}], spec={'width': 180, 'height': 320})
        report = video.verify_media(self.out, deep_qc=True)
        self.assertGreater(report['qc']['measures']['picture_coverage'], .95)

    def test_focus_x_moves_the_crop_toward_the_subject(self):
        self.half_white()
        self.p.compose([{'id': 'a', 'asset': 'half.mp4', 'duration': 1, 'fit': 'cover', 'focus_x': .1}], spec={'width': 180, 'height': 320, 'audio': 'optional'})
        left = luma_box(self.out, .5)
        self.p.compose([{'id': 'a', 'asset': 'half.mp4', 'duration': 1, 'fit': 'cover', 'focus_x': .9}], spec={'width': 180, 'height': 320, 'audio': 'optional'})
        right = luma_box(self.out, .5)
        self.assertGreater(left, 180); self.assertLess(right, 60)

    def test_crop_rectangle_selects_a_region(self):
        self.half_white()
        self.p.compose([{'id': 'a', 'asset': 'half.mp4', 'duration': 1, 'crop': {'x': .5, 'y': 0, 'w': .5, 'h': 1}}], spec={'audio': 'optional'})
        self.assertLess(luma_box(self.out, .5), 60)

    def test_contain_reports_low_picture_coverage(self):
        self.p.tone(size='640x180')
        result = self.p.compose([{'id': 'a', 'asset': 'src.mp4', 'duration': 1}], spec={'width': 180, 'height': 320})
        self.assertTrue(any('coverage' in w for w in result['warnings']), result)

    def test_invalid_framing_fields_rejected(self):
        self.p.tone()
        for scene in [{'fit': 'stretch'}, {'focus_x': 2}, {'crop': {'x': .9, 'y': 0, 'w': .5, 'h': 1}}, {'crop': 'center'}]:
            p = self.p.manifest([{'id': 'a', 'asset': 'src.mp4', 'duration': 1, **scene}])
            self.assertTrue(video.validate_manifest(json.loads(p.read_text()), self.p.root), scene)


class StillTests(EditCase):
    def test_still_image_scene_renders_for_its_duration(self):
        ffmpeg('-f', 'lavfi', '-i', 'color=red:size=640x360', '-frames:v', 1, self.p.root / 'title.png')
        self.p.compose([{'id': 'a', 'asset': 'title.png', 'duration': 2}])
        self.assertEqual(frame_count(self.out), 60)

    def test_still_cannot_request_source_audio(self):
        ffmpeg('-f', 'lavfi', '-i', 'color=red:size=640x360', '-frames:v', 1, self.p.root / 'title.png')
        with self.assertRaisesRegex(video.VideoError, 'still'):
            self.p.compose([{'id': 'a', 'asset': 'title.png', 'duration': 2, 'source_audio': True}])


class SourceRootTests(EditCase):
    def setUp(self):
        super().setUp()
        self.proj = self.p.root / 'proj'; self.proj.mkdir()
        self.footage = self.p.root / 'footage'; self.footage.mkdir()
        Project(self.footage).tone('clip.mp4', seconds=2)
        (self.proj / 'clip.mp4').symlink_to(self.footage / 'clip.mp4')
        self.q = Project(self.proj)

    def test_external_footage_refused_without_a_root(self):
        p = self.q.manifest([{'id': 'a', 'asset': 'clip.mp4', 'duration': 1}])
        with self.assertRaises(video.VideoError):
            video.compose(p, self.proj / 'o.mp4')

    def test_external_footage_allowed_inside_an_explicit_root(self):
        p = self.q.manifest([{'id': 'a', 'asset': 'clip.mp4', 'duration': 1}])
        result = video.compose(p, self.proj / 'o.mp4', source_roots=[self.footage])
        self.assertTrue(result['technical_pass'])

    def test_absolute_paths_stay_refused_with_a_root(self):
        with self.assertRaises(video.VideoError):
            video.local_path(self.proj, str(self.footage / 'clip.mp4'), [self.footage])

    def test_root_does_not_allow_other_locations(self):
        other = self.p.root / 'other'; other.mkdir()
        Project(other).tone('secret.mp4', seconds=2)
        (self.proj / 'secret.mp4').symlink_to(other / 'secret.mp4')
        with self.assertRaises(video.VideoError):
            video.local_path(self.proj, 'secret.mp4', [self.footage])


SRT_OK = '1\n00:00:00,100 --> 00:00:01,000\nHello there.\n'
WORDS = [dict(w='Hello', s=1.0, e=1.3, p=.99), dict(w='there.', s=1.35, e=1.7, p=.95), dict(w='Second', s=3.0, e=3.4, p=.3),
         dict(w='part', s=3.45, e=3.8, p=.98), dict(w='here', s=3.85, e=4.1, p=.97), dict(w='now.', s=4.15, e=4.5, p=.99)]


class QcTests(EditCase):
    def garbage(self):
        ffmpeg('-f', 'lavfi', '-i', 'color=black:size=320x180:rate=30:duration=3', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo:d=3',
               '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', self.p.root / 'g.mp4')
        return self.p.root / 'g.mp4'

    def checks(self, report, severity=None):
        return {x['check'] for x in report['qc']['findings'] if severity in (None, x['severity'])}

    def test_black_silent_video_fails_qc_while_technical_pass_stays_separate(self):
        report = video.verify_media(self.garbage(), {'audio': 'required'}, deep_qc=True)
        self.assertTrue(report['technical_pass'])
        self.assertEqual(report['qc']['status'], 'fail')
        self.assertTrue({'black', 'silent'} <= self.checks(report, 'fail'), report['qc'])

    def test_normal_media_passes_qc_with_measures(self):
        self.p.tone(seconds=3)
        report = video.verify_media(self.p.root / 'src.mp4', {'audio': 'required'}, deep_qc=True)
        self.assertNotIn('fail', {x['severity'] for x in report['qc']['findings']}, report['qc'])
        self.assertLess(report['qc']['measures']['lufs'], 0)
        self.assertIn('true_peak', report['qc']['measures'])

    def test_trailing_silence_is_flagged(self):
        ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30:duration=6', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2',
               '-af', 'apad', '-t', 6, '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', self.p.root / 's.mp4')
        report = video.verify_media(self.p.root / 's.mp4', {'audio': 'required'}, deep_qc=True)
        self.assertIn('silence', self.checks(report, 'warn'), report['qc'])

    def test_letterboxed_picture_is_flagged(self):
        self.p.tone(size='640x180')
        self.p.compose([{'id': 'a', 'asset': 'src.mp4', 'duration': 1}], spec={'width': 180, 'height': 320})
        report = video.verify_media(self.out, deep_qc=True)
        self.assertIn('coverage', self.checks(report, 'warn'), report['qc'])

    def test_loudness_target_is_checked(self):
        self.p.tone(seconds=3)
        report = video.verify_media(self.p.root / 'src.mp4', {'audio': 'required'}, deep_qc=True, loudness_target=-40)
        self.assertIn('loudness', self.checks(report, 'warn'), report['qc'])

    def test_caption_limits_are_flagged(self):
        findings = video.lint_captions([{'start': 0, 'end': .1, 'text': 'x' * 88}, {'start': 1, 'end': 3, 'text': 'A readable cue.'}])
        self.assertEqual({x['check'] for x in findings}, {'caption_line_length', 'caption_speed', 'caption_duration'})

    def test_readable_captions_have_no_findings(self):
        self.assertEqual(video.lint_captions([{'start': 0, 'end': 2, 'text': 'A readable cue.'}]), [])

    def test_cli_exit_code_fails_on_qc_failure(self):
        r = subprocess.run([sys.executable, str(MODULE), 'verify', str(self.garbage()), '--qc'], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertEqual(json.loads(r.stdout)['qc']['status'], 'fail')


class TranscriptToolTests(unittest.TestCase):
    def test_pack_groups_phrases_on_silence_and_marks_low_confidence(self):
        text = video.pack_words({'words': WORDS}, 'take.mp4')
        lines = [x for x in text.splitlines() if x.startswith('[')]
        self.assertEqual(len(lines), 2)
        self.assertIn('Hello there.', lines[0]); self.assertIn('?Second?', lines[1]); self.assertTrue(lines[1].startswith('[003.00-004.50]'))

    def test_ranges_pad_and_merge(self):
        scenes = video.ranges_to_scenes('a.mp4', [(1.0, 1.7), (1.72, 2.0), (3.0, 4.5)], fps=30, pad_before=.05, pad_after=.08)
        self.assertEqual(len(scenes), 2)
        self.assertEqual((scenes[0]['trim_start'], scenes[0]['asset'], scenes[0]['source_audio']), (.95, 'a.mp4', True))
        self.assertAlmostEqual(scenes[0]['duration'], 1.13, places=2)

    def test_ranges_never_start_before_zero(self):
        self.assertEqual(video.ranges_to_scenes('a.mp4', [(.01, 1)], fps=30)[0]['trim_start'], 0)

    def test_ranges_split_at_shot_changes(self):
        scenes = video.ranges_to_scenes('a.mp4', [(1, 5)], fps=30, pad_before=0, pad_after=0, shots=[3.0])
        self.assertEqual([x['trim_start'] for x in scenes], [1, 3.0])

    def test_words_map_to_the_output_timeline(self):
        scenes = [{'id': 'b', 'asset': 'a.mp4', 'trim_start': 3, 'duration': 2}, {'id': 'a', 'asset': 'a.mp4', 'trim_start': 1, 'duration': 1}]
        mapped = video.map_words(scenes, {'a.mp4': WORDS}, fps=30)
        self.assertEqual([x['w'] for x in mapped], ['Second', 'part', 'here', 'now.', 'Hello', 'there.'])
        self.assertAlmostEqual(mapped[0]['s'], 0); self.assertAlmostEqual(mapped[4]['s'], 2)

    def test_words_cut_out_of_the_timeline_are_dropped(self):
        scenes = [{'id': 'a', 'asset': 'a.mp4', 'trim_start': 1, 'duration': 1}]
        self.assertEqual([x['w'] for x in video.map_words(scenes, {'a.mp4': WORDS}, fps=30)], ['Hello', 'there.'])

    def test_caption_cues_respect_limits_and_stay_ordered(self):
        words = [dict(w=f'word{i}', s=i * .3, e=i * .3 + .25, p=.9) for i in range(12)]
        cues = video.words_to_cues(words, max_chars=16)
        self.assertTrue(all(len(c['text']) <= 16 for c in cues), cues)
        self.assertTrue(all(a['end'] <= b['start'] for a, b in zip(cues, cues[1:])), cues)

    def test_caption_cues_break_at_sentence_ends(self):
        cues = video.words_to_cues([dict(w='Stop.', s=0, e=.4, p=.9), dict(w='Go', s=.5, e=.8, p=.9)], max_chars=30)
        self.assertEqual([c['text'] for c in cues], ['Stop.', 'Go'])

    def test_srt_writer_round_trips(self):
        cues = [{'start': 0.25, 'end': 1.5, 'text': 'Hello'}, {'start': 61.0, 'end': 62.25, 'text': 'There'}]
        parsed, errors = video.parse_srt(video.cues_to_srt(cues), 70)
        self.assertEqual(errors, []); self.assertEqual(parsed, cues)

    def test_speech_check_separates_right_from_wrong_captions(self):
        spoken = [dict(w=w, s=i * .4, e=i * .4 + .3, p=.9) for i, w in enumerate('we should have about ten minutes left'.split())]
        right = [{'start': 0, 'end': 2.8, 'text': 'We should have about ten minutes left'}]
        wrong = [{'start': 5, 'end': 6, 'text': 'These words were never spoken at all'}]
        good, bad = video.speech_check(spoken, right), video.speech_check(spoken, wrong)
        self.assertGreater(good['text_similarity'], .9); self.assertEqual(good['status'], 'pass')
        self.assertLess(bad['text_similarity'], .4); self.assertEqual(bad['status'], 'warn')
        self.assertLess(bad['spoken_words_inside_cues'], 1)


class ReadingToolTests(EditCase):
    def test_shots_finds_a_hard_cut(self):
        ffmpeg('-f', 'lavfi', '-i', 'color=red:size=320x180:rate=30:duration=2', '-f', 'lavfi', '-i', 'color=blue:size=320x180:rate=30:duration=2',
               '-filter_complex', '[0][1]concat=n=2:v=1:a=0,format=yuv420p', '-c:v', 'libx264', '-preset', 'ultrafast', self.p.root / 'c.mp4')
        shots = video.detect_shots(self.p.root / 'c.mp4')
        self.assertEqual(len(shots), 1); self.assertAlmostEqual(shots[0], 2, delta=.1)

    def test_timeline_renders_a_png_with_words_and_frame_times(self):
        self.p.tone(seconds=6)
        words = self.p.root / 'w.json'; words.write_text(json.dumps({'words': WORDS}))
        png = self.p.root / 't.png'
        result = video.timeline(self.p.root / 'src.mp4', 1, 4, png, words)
        self.assertGreater(png.stat().st_size, 1000)
        self.assertEqual(result['words'][0]['w'], 'Hello'); self.assertEqual(len(result['frame_times']), result['columns'])

    def test_timeline_handles_video_without_audio(self):
        ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30:duration=2', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', self.p.root / 'n.mp4')
        png = self.p.root / 't.png'
        video.timeline(self.p.root / 'n.mp4', 0, 2, png)
        self.assertTrue(png.is_file())

    def test_review_covers_every_cut_plus_opening_and_ending(self):
        self.p.tone()
        p = self.p.manifest([{'id': f's{i}', 'asset': 'src.mp4', 'duration': 2, 'trim_start': i} for i in range(3)])
        video.compose(p, self.out)
        result = video.review(self.out, p, self.p.root / 'r')
        self.assertEqual(sorted(x['label'] for x in result['views']), ['cut:2.000', 'cut:4.000', 'ending', 'opening'])
        self.assertTrue(all(Path(x['image']).is_file() for x in result['views']))

    def test_review_caps_the_number_of_views_and_says_so(self):
        self.p.tone()
        p = self.p.manifest([{'id': f's{i}', 'asset': 'src.mp4', 'duration': 1, 'trim_start': i} for i in range(9)])
        video.compose(p, self.out)
        result = video.review(self.out, p, self.p.root / 'r', max_views=4)
        self.assertEqual(len(result['views']), 4); self.assertGreater(result['cuts_not_shown'], 0)


class FinishingTests(EditCase):
    def narration(self, seconds=2):
        ffmpeg('-f', 'lavfi', '-i', f'sine=frequency=300:sample_rate=48000:duration={seconds}', self.p.root / 'voice.wav')

    def test_loudness_target_is_met(self):
        self.p.tone(seconds=8)
        self.p.compose([{'id': 'a', 'asset': 'src.mp4', 'duration': 6, 'source_audio': True}], loudness={'target': -16, 'true_peak': -1.5})
        report = video.verify_media(self.out, {'audio': 'required'}, deep_qc=True, loudness_target=-16)
        self.assertAlmostEqual(report['qc']['measures']['lufs'], -16, delta=1.5)

    def test_music_ducks_under_speech(self):
        self.p.tone(seconds=8)
        ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=1000:sample_rate=48000:duration=8', self.p.root / 'music.wav')
        ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=300:sample_rate=48000:duration=3', '-af', 'volume=6dB', self.p.root / 'voice.wav')
        self.p.compose([{'id': 'a', 'asset': 'src.mp4', 'duration': 6}], assets=['src.mp4', 'voice.wav', 'music.wav'], narration='voice.wav',
                       music={'path': 'music.wav', 'gain_db': -6})
        def band(start):
            out = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-ss', str(start), '-t', '1', '-i', str(self.out), '-af', 'bandpass=f=1000:w=100,volumedetect', '-f', 'null', '-'], capture_output=True, text=True).stderr
            return float(out.split('mean_volume:')[1].split()[0])
        self.assertLess(band(1), band(4.5) - 3)

    def test_music_must_have_provenance(self):
        self.p.tone()
        ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=1000:sample_rate=48000:duration=8', self.p.root / 'music.wav')
        p = self.p.manifest([{'id': 'a', 'asset': 'src.mp4', 'duration': 1}], music={'path': 'music.wav'})
        self.assertTrue(any('music' in x for x in video.validate_manifest(json.loads(p.read_text()), self.p.root)))

    def test_captions_are_burned_into_the_picture(self):
        if not filter_available('ass'):
            self.skipTest('ass filter unavailable')
        ffmpeg('-f', 'lavfi', '-i', 'color=black:size=640x360:rate=30:duration=3', '-f', 'lavfi', '-i', 'sine=frequency=300:sample_rate=48000:duration=3',
               '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', self.p.root / 'dark.mp4')
        (self.p.root / 'cap.srt').write_text('1\n00:00:01,000 --> 00:00:02,000\nBURNED TEXT\n')
        scene = [{'id': 'a', 'asset': 'dark.mp4', 'duration': 3, 'source_audio': True}]
        self.p.compose(scene, assets=['dark.mp4', 'cap.srt'], captions='cap.srt', burn_captions={'style': 'bold-center'}, spec={'width': 640, 'height': 360})
        self.assertGreater(luma_box(self.out, 1.5), luma_box(self.out, .5) + 1)
        self.assertEqual(frame_count(self.out), 90)
        first = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'frame=pts_time', '-read_intervals', '%+#1', '-of', 'csv=p=0', str(self.out)], text=True)
        self.assertAlmostEqual(float(first.strip().strip(',')), 0, places=3)

    def test_compose_warns_when_burned_captions_run_long(self):
        if not filter_available('ass'):
            self.skipTest('ass filter unavailable')
        self.p.tone(seconds=3)
        (self.p.root / 'cap.srt').write_text("1\n00:00:00,000 --> 00:00:02,000\nAre you ready? Of course you're ready. You're a rock star.\n")
        result = self.p.compose([{'id': 'a', 'asset': 'src.mp4', 'duration': 2, 'source_audio': True}], assets=['src.mp4', 'cap.srt'], captions='cap.srt', burn_captions={'style': 'bold-center'}, spec={'width': 540, 'height': 960})
        self.assertTrue(any('past two lines' in x for x in result['warnings']), result['warnings'])

    def test_burning_needs_a_caption_file_and_a_known_style(self):
        self.p.tone()
        p = self.p.manifest([{'id': 'a', 'asset': 'src.mp4', 'duration': 1}], burn_captions={'style': 'bold-center'})
        self.assertTrue(any('captions' in x for x in video.validate_manifest(json.loads(p.read_text()), self.p.root)))
        (self.p.root / 'cap.srt').write_text(SRT_OK)
        p = self.p.manifest([{'id': 'a', 'asset': 'src.mp4', 'duration': 1}], assets=['src.mp4', 'cap.srt'], captions='cap.srt', burn_captions={'style': 'comic'})
        self.assertTrue(any('style' in x for x in video.validate_manifest(json.loads(p.read_text()), self.p.root)))


def load_script(name):
    path = ROOT / 'skills/video-production/scripts' / f'{name}.py'
    module_spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module, path


class NumericScalar(float):
    """Behaves like a NumPy scalar: arithmetic and comparisons do not return plain Python numbers."""
    def __round__(self, digits=None): return self
    def __add__(self, other): return NumericScalar(float(self) + other)
    def __truediv__(self, other): return NumericScalar(float(self) / other)
    def __lt__(self, other): return NumericBool(float(self) < other)


class NumericBool:
    def __init__(self, value): self.value = value
    def __bool__(self): return self.value
    def __radd__(self, other): return NumericScalar(other + int(self.value))


def timed(text, start, end):
    words = text.split(); step = (end-start)/len(words)
    return [dict(w=w, s=round(start+i*step, 3), e=round(start+(i+1)*step, 3), p=.9) for i, w in enumerate(words)]


class CaptionPacingTests(unittest.TestCase):
    def test_an_orphan_word_too_short_to_read_rejoins_its_sentence(self):
        cues = video.words_to_cues(timed('We should have about ten', 0, 1.25)+timed('minutes.', 1.25, 1.6)+timed('Well perfect.', 1.6, 2.6))
        self.assertEqual([c['text'] for c in cues], ['We should have about ten minutes.', 'Well perfect.'])

    def test_fast_sentences_stay_apart_and_the_lint_reports_them(self):
        cues = video.words_to_cues(timed("Of course you're ready.", 0, .7)+timed("You're a rock star.", .7, 1.4))
        self.assertEqual(len(cues), 2)
        self.assertTrue([x for x in video.lint_captions(cues) if x['check'] == 'caption_speed'])

    def test_a_long_pause_keeps_an_orphan_apart(self):
        cues = video.words_to_cues(timed('We should have about ten', 0, 1.25)+timed('minutes.', 2.5, 2.8))
        self.assertEqual(len(cues), 2)

    def test_joining_stays_near_the_length_limit(self):
        cues = video.words_to_cues(timed('Every one reads so fast and then more words', 0, 1), max_chars=24)
        self.assertEqual(len(cues), 2)

    def test_comfortable_sentences_stay_separate(self):
        cues = video.words_to_cues(timed('Stop right there.', 0, 1.2)+timed('Go on now.', 1.3, 2.5))
        self.assertEqual(len(cues), 2)

    def test_burned_captions_past_two_lines_are_reported(self):
        spec = {'width': 1080, 'height': 1920}; style = {'style': 'bold-center'}
        long = {'start': 0, 'end': 2, 'text': "Are you ready? Of course you're ready. You're a rock star."}
        short = {'start': 2, 'end': 3, 'text': 'Are you ready?'}
        self.assertEqual(video.caption_overflow([short, long], spec, style), [2])
        self.assertEqual(video.caption_overflow([long], {'width': 1920, 'height': 1080}, {'style': 'minimal'}), [])


@unittest.skipUnless(shutil.which('node'), 'Node.js is not installed')
class ScreenCaptureTests(unittest.TestCase):
    helper = ROOT/'skills/video-production/scripts/screen_capture.cjs'

    def node(self, script, cwd):
        return subprocess.run(['node', '-e', script, str(self.helper)], capture_output=True, text=True, cwd=cwd, timeout=120)

    def test_frame_list_keeps_real_timing_and_decodes(self):
        script = """
const fs=require('fs'),{recordFrames}=require(process.argv[1]);
const page={screenshot:async o=>{fs.copyFileSync('seed.jpg',o.path);await new Promise(r=>setTimeout(r,30))},context:()=>({})};
recordFrames(page,'frames',()=>new Promise(r=>setTimeout(r,300))).then(x=>console.log(JSON.stringify(x)));
"""
        with tempfile.TemporaryDirectory() as d:
            ffmpeg('-f', 'lavfi', '-i', 'color=c=white:s=64x64', '-frames:v', 1, Path(d)/'seed.jpg')
            done = self.node(script, d); self.assertEqual(done.returncode, 0, done.stderr)
            result = json.loads(done.stdout)
            lines = (Path(d)/'frames/frames.ffconcat').read_text().splitlines()
            self.assertEqual(lines[0], 'ffconcat version 1.0')
            self.assertEqual(lines[-1], lines[-3], 'the last frame repeats so its duration counts')
            self.assertGreater(result['frames'], 2)
            ffmpeg('-f', 'concat', '-safe', 0, '-i', Path(d)/'frames/frames.ffconcat', '-vf', 'fps=30,format=yuv420p', Path(d)/'out.mp4')
            self.assertAlmostEqual(frame_count(Path(d)/'out.mp4')/30, result['seconds'], delta=.2)

    def test_cursor_follows_the_mouse_on_set_content_and_navigated_pages(self):
        script = """
const fs=require('fs'),{installCursor,recordFrames}=require(process.argv[1]);
let chromium;
try{({chromium}=require('playwright'))}catch(e){console.log('SKIP');process.exit(0)}
(async()=>{
  let browser;
  try{browser=await chromium.launch({headless:true})}catch(e){console.log('SKIP');process.exit(0)}
  const context=await browser.newContext({viewport:{width:640,height:360}});await installCursor(context);
  const page=await context.newPage();const seen=[];
  const left=()=>page.evaluate(()=>document.getElementById('__capture_cursor').style.left);
  await page.setContent('<h1>Inline</h1>');
  await recordFrames(page,'a',async()=>{await page.mouse.move(300,200);await page.waitForTimeout(150);seen.push(await left())});
  fs.writeFileSync('p.html','<h1>File</h1>');await page.goto('file://'+process.cwd()+'/p.html');
  await recordFrames(page,'b',async()=>{await page.mouse.move(120,90);await page.waitForTimeout(150);seen.push(await left())});
  console.log(JSON.stringify(seen));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
"""
        with tempfile.TemporaryDirectory() as d:
            done = self.node(script, d); self.assertEqual(done.returncode, 0, done.stderr)
            if done.stdout.strip() == 'SKIP': self.skipTest('Playwright with Chromium is not available')
            self.assertEqual(json.loads(done.stdout), ['300px', '120px'])


class TranscribeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.transcribe, self.path = load_script('transcribe')
        self.media = self.root / 'take.mp4'; self.media.write_bytes(b'take one')
        self.out = self.root / 'words.json'

    def tearDown(self):
        self.tmp.cleanup()

    def test_loading_the_script_needs_no_heavy_dependency(self):
        self.assertTrue(callable(self.transcribe.cached_transcript))

    def test_matching_cached_transcript_is_reused(self):
        self.out.write_text(json.dumps({'sha256': self.transcribe.digest(self.media), 'model': 'base.en', 'glossary': [], 'words': [{'w': 'hi', 's': 0, 'e': 1, 'p': 1}]}))
        self.assertEqual(self.transcribe.cached_transcript(self.media, self.out, 'base.en', [])['words'][0]['w'], 'hi')

    def test_changed_media_model_or_glossary_invalidates_the_cache(self):
        self.out.write_text(json.dumps({'sha256': self.transcribe.digest(self.media), 'model': 'base.en', 'glossary': [], 'words': []}))
        self.assertIsNone(self.transcribe.cached_transcript(self.media, self.out, 'small.en', []))
        self.assertIsNone(self.transcribe.cached_transcript(self.media, self.out, 'base.en', ['Bali']))
        self.media.write_bytes(b'take two')
        self.assertIsNone(self.transcribe.cached_transcript(self.media, self.out, 'base.en', []))

    def test_malformed_cache_is_ignored(self):
        self.out.write_text('not json')
        self.assertIsNone(self.transcribe.cached_transcript(self.media, self.out, 'base.en', []))

    def test_word_records_hold_plain_numbers_for_json(self):
        class Word:
            word, start, end, probability = ' hi ', NumericScalar(1), NumericScalar(2), NumericScalar(.25)
        record = self.transcribe.word_record(Word)
        self.assertEqual(record['w'], 'hi')
        self.assertTrue(all(type(record[k]) is float for k in 'sep'))
        json.dumps({'low': sum(record['p'] < .5 for _ in [0])})

    def test_script_declares_pinned_dependencies_for_uv(self):
        text = self.path.read_text()
        self.assertIn('# /// script', text); self.assertIn('faster-whisper==', text)


class ReframeTests(unittest.TestCase):
    def setUp(self):
        self.reframe, self.path = load_script('reframe')

    def test_focus_is_the_median_face_position(self):
        self.assertAlmostEqual(self.reframe.choose_focus([.2, .3, .9], .5), .3)

    def test_scene_without_faces_keeps_the_previous_focus(self):
        self.assertEqual(self.reframe.choose_focus([], .7), .7)

    def test_faces_kept_counts_those_inside_the_crop_window(self):
        self.assertEqual(self.reframe.faces_inside([.1, .5, .9], .5, .4), 1)

    def test_window_at_the_frame_edge_is_clamped_like_the_renderer(self):
        self.assertEqual(self.reframe.faces_inside([.05], 0, .4), 1)

    def test_face_centers_are_plain_numbers_for_json(self):
        center = self.reframe.face_center(NumericScalar(10), NumericScalar(20), 100)
        self.assertIs(type(center), float); self.assertAlmostEqual(center, .2)

    def test_script_declares_a_pinned_opencv_below_5(self):
        self.assertIn('opencv-python-headless<5', self.path.read_text())


class DoctorTests(EditCase):
    def test_doctor_reports_each_route_separately(self):
        routes = video.doctor()['routes']
        self.assertTrue({'clip_assembly', 'captions_burn', 'loudness', 'qc', 'hdr_tone_map', 'transcription', 'reframe', 'screen_capture'} <= set(routes))
        self.assertTrue(all(isinstance(x, str) for x in routes.values()))

    def test_filter_names_are_parsed_exactly(self):
        names = video.filter_names()
        self.assertIn('scale', names); self.assertNotIn('->', names); self.assertNotIn('Filters:', names)


if __name__ == '__main__':
    unittest.main()
