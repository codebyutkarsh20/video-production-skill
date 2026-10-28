#!/usr/bin/env python3
"""Build an allowlisted source package; local media/private artifacts stay outside."""
from pathlib import Path
import hashlib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILES=['README.md','LICENSE','skills/video-production/LICENSE','CONTRIBUTING.md','ASSET-CREDITS.md','CHANGELOG.md','requirements-examples.txt','requirements-tts.txt',
       'docs/release-evidence.md','docs/evaluations.md']
TREES=['skills','tests','examples','scripts']
SUFFIXES={'.md','.py','.yaml','.html','.cjs','.txt','.json'}


def build(root=ROOT):
    root=Path(root).resolve();out=root/'dist';out.mkdir(exist_ok=True)
    dest=out/'video-production-0.1.0.zip';entries=[]
    for name in FILES:
        p=root/name
        if not p.is_file(): raise ValueError(f'Missing release input: {name}')
        entries.append(p)
    for tree in TREES:
        for p in sorted((root/tree).rglob('*')):
            if p.is_file() and p.suffix in SUFFIXES and not any(x.startswith('.') or x=='__pycache__' for x in p.relative_to(root).parts):entries.append(p)
    for p in entries:
        if p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Release inputs must not escape via symlinks')
        body=p.read_bytes()
        if any(('/'+part+'/').encode() in body for part in ('Users','home')):
            raise ValueError(f'Private machine path in release input: {p.relative_to(root)}')
    temp=dest.with_suffix('.partial')
    try:
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as archive:
            for p in entries:archive.write(p,'video-production/'+str(p.relative_to(root)))
        temp.replace(dest)
    finally:temp.unlink(missing_ok=True)
    digest=hashlib.sha256(dest.read_bytes()).hexdigest()
    dest.with_suffix('.zip.sha256').write_text(f'{digest}  {dest.name}\n')
    return {'archive':str(dest),'files':len(entries),'sha256':digest}


if __name__=='__main__':
    import json
    print(json.dumps(build(),indent=2))
