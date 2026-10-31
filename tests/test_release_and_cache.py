import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


class ReleaseTests(unittest.TestCase):
    def test_skill_references_exist_and_description_stays_a_single_scalar(self):
        skill=ROOT/'skills/video-production/SKILL.md';text=skill.read_text()
        description=next(x for x in text.splitlines() if x.startswith('description:')).removeprefix('description:').strip()
        self.assertTrue(': ' not in description or description[0] in '\'"',description[:40])
        self.assertLessEqual(len(description),1024)
        for link in re.findall(r'\]\((references/[^)]+)\)',text):self.assertTrue((skill.parent/link).is_file(),link)

    def test_repeatable_cases_are_not_presented_as_results(self):
        cases=json.loads((ROOT/'evals/cases.json').read_text())
        self.assertEqual(cases['status'],'not_yet_run')
        self.assertTrue(all(c['prompt'] and c['pass_when'] for c in cases['cases']))

    def test_package_is_self_contained_and_excludes_private_artifacts(self):
        release=load('release',ROOT/'scripts/package_release.py')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in release.FILES:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('public content')
            (root/'scripts').mkdir(exist_ok=True)
            (root/'scripts/package_release.py').write_text('print("release")')
            skill=root/'skills/video-production'
            skill.mkdir(parents=True,exist_ok=True)
            (skill/'SKILL.md').write_text('---\nname: video-production\ndescription: Video workflow\n---\n')
            (skill/'scripts').mkdir()
            (skill/'scripts/video_tools.py').write_text('print("helper")')
            (skill/'references').mkdir()
            (skill/'references/creative-direction.md').write_text('Creative direction and capability discovery')
            (root/'artifacts').mkdir();(root/'artifacts/private.txt').write_text('private')
            (root/'.env').write_text('SECRET=private')
            result=release.build(root)
            self.assertEqual(Path(result['archive']).name,'video-production-0.3.0.zip')
            self.assertEqual(Path(result['skill_archive']).name,'video-production-skill-0.3.0.zip')
            with zipfile.ZipFile(result['archive']) as z:
                names=z.namelist()
                self.assertIn('video-production/scripts/package_release.py',names)
                self.assertFalse(any('artifacts/' in x or '.env' in x for x in names))
            with zipfile.ZipFile(result['skill_archive']) as z:
                self.assertIn('video-production/SKILL.md',z.namelist())
                self.assertIn('video-production/LICENSE',z.namelist())
                self.assertIn('video-production/scripts/video_tools.py',z.namelist())
                self.assertEqual(z.read('video-production/references/creative-direction.md'),b'Creative direction and capability discovery')
                self.assertFalse(any('/tests/' in x or '/examples/' in x for x in z.namelist()))


try:
    import PIL
except ImportError:
    PIL=None


@unittest.skipUnless(PIL,'Pillow example dependency unavailable')
class ShowcaseCacheTests(unittest.TestCase):
    def setUp(self):
        self.showcase=load('showcase',ROOT/'examples/showcase/render.py')

    def test_audio_cache_tracks_voice_rate_and_artifact_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            files=['narration.wav','mix.wav','captions.srt','script.md','music.wav']
            for name in files:(out/name).write_bytes(b'original artifact')
            key=self.showcase.narration_key('Voice A',148)
            state={'input_key':key,'artifacts':{name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in files}}
            (out/'timings.json').write_text(json.dumps(state))
            self.assertTrue(self.showcase.audio_cache_valid(out,'Voice A',148))
            self.assertFalse(self.showcase.audio_cache_valid(out,'Voice B',148))
            self.assertFalse(self.showcase.audio_cache_valid(out,'Voice A',180))
            (out/'mix.wav').write_bytes(b'truncated')
            self.assertFalse(self.showcase.audio_cache_valid(out,'Voice A',148))

    def test_corrupt_clip_not_reused_even_with_matching_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);clip=out/'clip.mp4';marker=out/'clip.sha256'
            clip.write_bytes(b'broken');marker.write_text('same-input')
            self.assertFalse(self.showcase.clip_cache_valid(clip,marker,'same-input',1))

    def test_malformed_audio_state_rebuilds_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            for state in [[],None,{'input_key':self.showcase.narration_key('Voice A',148),'artifacts':None}]:
                (out/'timings.json').write_text(json.dumps(state))
                self.assertFalse(self.showcase.audio_cache_valid(out,'Voice A',148))


    def test_narration_cues_wrap_to_readable_lines(self):
        speech=' '.join(s[3] for s in self.showcase.SCENES)
        for part in self.showcase.chunks(speech):
            wrapped=self.showcase.caption_lines(part)
            self.assertEqual(wrapped.replace('\n',' '),part)
            self.assertLessEqual(max(map(len,wrapped.split('\n'))),42,wrapped)
            self.assertLessEqual(wrapped.count('\n'),1,wrapped)

    def test_a_caption_change_invalidates_cached_narration(self):
        self.assertEqual(self.showcase.AUDIO_PIPELINE,5)


if __name__=='__main__':unittest.main()
