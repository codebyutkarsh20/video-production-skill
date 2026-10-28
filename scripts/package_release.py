#!/usr/bin/env python3
"""Build an allowlisted source package; local media/private artifacts stay outside."""
from pathlib import Path
import hashlib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILES=['README.md','INSTALL.md','AGENTS.md','llms.txt','LICENSE','skills/video-production/LICENSE','CONTRIBUTING.md','ASSET-CREDITS.md','CHANGELOG.md','requirements-examples.txt','requirements-tts.txt','docs/assets/preview.jpg',
       'docs/release-evidence.md','docs/evaluations.md']
TREES=['skills','tests','examples','scripts','.github']
SUFFIXES={'.md','.py','.yaml','.yml','.html','.cjs','.txt','.json'}


def build(root=ROOT):
    root=Path(root).resolve();out=root/'dist';out.mkdir(exist_ok=True)
    dest=out/'video-production-0.1.0.zip';entries=[]
    for name in FILES:
        p=root/name
        if not p.is_file(): raise ValueError(f'Missing release input: {name}')
        entries.append(p)
    for tree in TREES:
        for p in sorted((root/tree).rglob('*')):
            if p.is_file() and p.suffix in SUFFIXES and not any((x.startswith('.') and x!='.github') or x=='__pycache__' for x in p.relative_to(root).parts):entries.append(p)
    for p in entries:
        if p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Release inputs must not escape via symlinks')
        body=p.read_bytes()
        if any(('/'+part+'/').encode() in body for part in ('Users','home')):
            raise ValueError(f'Private machine path in release input: {p.relative_to(root)}')
    def write_archive(target,items):
        temp=target.with_suffix('.partial')
        try:
            with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as archive:
                for p,name in items:archive.write(p,name)
            temp.replace(target)
        finally:temp.unlink(missing_ok=True)
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n')
        return digest
    digest=write_archive(dest,[(p,'video-production/'+str(p.relative_to(root))) for p in entries])
    skill_root=root/'skills/video-production'
    if not (skill_root/'SKILL.md').is_file():raise ValueError('Missing installable SKILL.md')
    skill_entries=[(p,'video-production/'+str(p.relative_to(skill_root))) for p in entries if p.is_relative_to(skill_root)]
    skill_dest=out/'video-production-skill-0.1.0.zip'
    skill_digest=write_archive(skill_dest,skill_entries)
    return {'archive':str(dest),'files':len(entries),'sha256':digest,
            'skill_archive':str(skill_dest),'skill_files':len(skill_entries),'skill_sha256':skill_digest}


if __name__=='__main__':
    import json
    print(json.dumps(build(),indent=2))
