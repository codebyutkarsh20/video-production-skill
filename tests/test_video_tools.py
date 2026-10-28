import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'skills/video-production/scripts/video_tools.py'
spec = importlib.util.spec_from_file_location('video_tools', MODULE)
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


def manifest():
    return {'version': 1, 'title': 'Fictional preview', 'mode': 'preview',
            'spec': {'width': 320, 'height': 180, 'fps': 24, 'min_duration': 0.5,
                     'max_duration': 3, 'audio': 'required'},
            'scenes': [{'id': 'opening', 'asset': 'clip.mp4', 'duration': 1}],
            'assets': [{'path': 'clip.mp4', 'provenance': 'Original synthetic fixture',
                        'rights': 'Created for this test'}]}


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'clip.mp4').write_bytes(b'placeholder')

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_manifest(self):
        self.assertEqual(video.validate_manifest(manifest(), self.root), [])

    def test_unknown_mode_is_error(self):
        m = manifest(); m['mode'] = 'magic'
        self.assertTrue(any('mode' in x for x in video.validate_manifest(m, self.root)))

    def test_boolean_version_is_not_schema_version(self):
        m = manifest(); m['version'] = True
        self.assertTrue(any('version' in x for x in video.validate_manifest(m, self.root)))

    def test_duplicate_scene_id(self):
        m = manifest(); m['scenes'].append(copy.deepcopy(m['scenes'][0]))
        self.assertTrue(any('duplicate' in x for x in video.validate_manifest(m, self.root)))

    def test_nonfinite_duration(self):
        m = manifest(); m['scenes'][0]['duration'] = float('nan')
        self.assertTrue(any('duration' in x for x in video.validate_manifest(m, self.root)))

    def test_wrong_type_does_not_crash(self):
        for m in [None, [], {'spec': [], 'scenes': [None], 'assets': [None]},
                  {**manifest(), 'scenes': 'wrong'}, {**manifest(), 'assets': None}]:
            self.assertTrue(video.validate_manifest(m, self.root))

    def test_odd_dimensions_rejected(self):
        m = manifest(); m['spec']['width'] = 319
        self.assertTrue(any('even' in x for x in video.validate_manifest(m, self.root)))

    def test_path_escape_and_remote_refused(self):
        for path in ['../outside.mp4', '/tmp/outside.mp4', 'https://example.com/clip.mp4']:
            m = manifest(); m['scenes'][0]['asset'] = path
            self.assertTrue(any('path' in x for x in video.validate_manifest(m, self.root)))

    def test_symlink_escape_refused(self):
        with tempfile.TemporaryDirectory() as other:
            p = Path(other) / 'secret.mp4'; p.write_bytes(b'secret')
            (self.root / 'linked.mp4').symlink_to(p)
            m = manifest(); m['scenes'][0]['asset'] = 'linked.mp4'
            self.assertTrue(any('path' in x for x in video.validate_manifest(m, self.root)))

    def test_missing_provenance_rejected(self):
        m = manifest(); m['assets'][0]['rights'] = ''
        self.assertTrue(any('rights' in x for x in video.validate_manifest(m, self.root)))

    def test_unlisted_scene_asset_rejected(self):
        m = manifest(); m['assets'] = []
        self.assertTrue(any('asset' in x for x in video.validate_manifest(m, self.root)))

    def test_timeline_outside_spec(self):
        m = manifest(); m['spec']['min_duration'] = 2
        self.assertTrue(any('timeline' in x for x in video.validate_manifest(m, self.root)))

    def test_brief_needs_no_media(self):
        m = {'version': 1, 'mode': 'brief', 'title': 'Brief', 'brief': 'A concise request.'}
        self.assertEqual(video.validate_manifest(m, self.root), [])

    def test_cache_fingerprint_uses_content(self):
        m = manifest(); a = video.scene_key(m['scenes'][0], m['spec'], self.root, 'ffmpeg-test')
        (self.root / 'clip.mp4').write_bytes(b'replaced input')
        self.assertNotEqual(a, video.scene_key(m['scenes'][0], m['spec'], self.root, 'ffmpeg-test'))

    def test_cache_key_changes_for_duration_and_spec(self):
        m = manifest(); a = video.scene_key(m['scenes'][0], m['spec'], self.root, 'ffmpeg-test')
        m['scenes'][0]['duration'] = 2
        self.assertNotEqual(a, video.scene_key(m['scenes'][0], m['spec'], self.root, 'ffmpeg-test'))
        m['scenes'][0]['duration'] = 1; m['spec']['fps'] = 30
        self.assertNotEqual(a, video.scene_key(m['scenes'][0], m['spec'], self.root, 'ffmpeg-test'))


class CaptionTests(unittest.TestCase):
    def test_valid_captions(self):
        cues, errors = video.parse_srt('1\n00:00:00,000 --> 00:00:00,800\nHello.\n', 1)
        self.assertEqual(errors, []); self.assertEqual(len(cues), 1)

    def test_out_of_bounds_and_overlap(self):
        text = '1\n00:00:00,000 --> 00:00:00,800\nOne\n\n2\n00:00:00,700 --> 00:00:02,000\nTwo\n'
        _, errors = video.parse_srt(text, 1)
        self.assertTrue(any('overlap' in x for x in errors))
        self.assertTrue(any('beyond' in x for x in errors))

    def test_invalid_time_and_empty_text(self):
        for text in ['1\n00:99:00,000 --> 00:99:01,000\nHello',
                     '1\n00:00:01,000 --> 00:00:00,000\nHello',
                     '1\n00:00:00,000 --> 00:00:01,000\n', 'garbage']:
            self.assertTrue(video.parse_srt(text, 2)[1])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg integration dependencies unavailable')
class MediaIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.clip = self.root / 'clip.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',
                        'testsrc2=size=320x180:rate=24','-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
                        '-t','1.2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(self.clip)],check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_actual_media_full_decode(self):
        report = video.verify_media(self.clip, manifest()['spec'])
        self.assertTrue(report['technical_pass'], report)
        self.assertEqual(report['review']['visual'], 'not_performed')
        self.assertEqual(report['review']['listening'], 'not_performed')

    def test_mismatch_dimensions_fails(self):
        s = manifest()['spec']; s['width'] = 640
        self.assertFalse(video.verify_media(self.clip, s)['technical_pass'])

    def test_corrupt_file_fails(self):
        self.clip.write_bytes(b'not a video')
        self.assertFalse(video.verify_media(self.clip, manifest()['spec'])['technical_pass'])

    def test_missing_audio_fails_when_required(self):
        silent = self.root / 'silent.mp4'
        subprocess.run(['ffmpeg','-v','error','-i',str(self.clip),'-an','-c:v','copy',str(silent)],check=True)
        self.assertFalse(video.verify_media(silent, manifest()['spec'])['technical_pass'])

    def test_compose_and_content_cache_resume(self):
        m = manifest(); p = self.root / 'project.json'; p.write_text(json.dumps(m))
        out = self.root / 'output.mp4'
        first = video.compose(p, out)
        self.assertEqual(first['rendered_scenes'], ['opening'])
        self.assertTrue(video.verify_media(out, m['spec'])['technical_pass'])
        with self.assertRaises(video.VideoError): video.compose(p, out)
        second = video.compose(p, out, overwrite=True)
        self.assertEqual(second['reused_scenes'], ['opening'])

    def test_trim_beyond_source_refused(self):
        m = manifest(); m['scenes'][0]['trim_start'] = 2
        p = self.root / 'project.json'; p.write_text(json.dumps(m))
        with self.assertRaises(video.VideoError): video.compose(p, self.root / 'bad.mp4')
        self.assertFalse((self.root / 'bad.mp4').exists())

    def test_explicit_source_audio_missing_is_error(self):
        silent = self.root / 'silent.mp4'
        subprocess.run(['ffmpeg','-v','error','-i',str(self.clip),'-an','-c:v','copy',str(silent)],check=True)
        m=manifest();m['scenes'][0].update({'asset':'silent.mp4','source_audio':True})
        m['assets'][0]['path']='silent.mp4'
        p=self.root/'project.json';p.write_text(json.dumps(m))
        with self.assertRaises(video.VideoError):video.compose(p,self.root/'bad.mp4')

    def test_report_cannot_overwrite_a_manifest_source(self):
        output=self.root/'output.mp4';shutil.copyfile(self.clip,output)
        p=self.root/'project.json';p.write_text(json.dumps(manifest()))
        original=self.clip.read_bytes()
        result=subprocess.run([sys.executable,str(MODULE),'verify',str(output),'--manifest',str(p),
                               '--report',str(self.clip)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.clip.read_bytes(),original)

    def test_audio_tail_does_not_count_as_video(self):
        short=self.root/'short-picture.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=24:duration=0.5',
                        '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=3',
                        '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(short)],check=True)
        self.assertFalse(video.verify_media(short,{**manifest()['spec'],'min_duration':2.9,'max_duration':3.1})['technical_pass'])
        m=manifest();m['scenes'][0].update({'asset':'short-picture.mp4','duration':3})
        m['assets'][0]['path']='short-picture.mp4';p=self.root/'project.json';p.write_text(json.dumps(m))
        with self.assertRaises(video.VideoError):video.compose(p,self.root/'bad.mp4')


if __name__ == '__main__':
    unittest.main()
