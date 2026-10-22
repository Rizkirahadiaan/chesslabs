"""Fetch official Android SDK components and Stockfish into this workspace."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'work/android-downloads'
SDK = ROOT / 'work/android-sdk'
CACHE.mkdir(parents=True, exist_ok=True)
SDK.mkdir(parents=True, exist_ok=True)

def fetch(url, name):
    dest = CACHE / name
    if dest.exists(): return dest
    print('Downloading:', url, flush=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'ChessLab-build/0.1', 'Accept': 'application/octet-stream'})
    with urllib.request.urlopen(request, timeout=45) as response, dest.with_suffix('.partial').open('wb') as out:
        shutil.copyfileobj(response, out)
    dest.with_suffix('.partial').replace(dest)
    print(name, dest.stat().st_size, flush=True)
    return dest

def unpack_zip(archive, target):
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not (target/name).resolve().is_relative_to(target.resolve()): raise ValueError('Unsafe archive path')
        z.extractall(target)

repo = ET.parse(fetch('https://dl.google.com/android/repository/repository2-1.xml', 'repository.xml')).getroot()
for package, target in [('platforms;android-36', SDK/'platforms'), ('build-tools;36.0.0', SDK/'build-tools'), ('platform-tools', SDK)]:
    node = next(n for n in repo if n.tag.endswith('remotePackage') and n.get('path') == package)
    arch = next(a for a in node.findall('./archives/archive') if a.findtext('host-os') in (None, 'windows'))
    url = arch.findtext('complete/url')
    archive = fetch('https://dl.google.com/android/repository/'+url, url.rsplit('/',1)[-1])
    expected = arch.findtext('complete/checksum')
    if hashlib.sha1(archive.read_bytes()).hexdigest() != expected: raise ValueError('SDK checksum mismatch')
    unpack_zip(archive, target)

engine_archive = fetch('https://api.github.com/repos/official-stockfish/Stockfish/releases/assets/545567324', 'stockfish-19-android.tar.gz')
if hashlib.sha256(engine_archive.read_bytes()).hexdigest() != 'ebb24051aa4a222b4daaf049b882ecf1163d370c128fe02316602643f4d5e426':
    raise ValueError('Stockfish checksum mismatch')
lib = ROOT/'android/app/src/main/jniLibs/arm64-v8a/libstockfish.so'
assets = ROOT/'android/app/src/main/assets'
lib.parent.mkdir(parents=True, exist_ok=True)
assets.mkdir(parents=True, exist_ok=True)
with tarfile.open(engine_archive) as t:
    binary = next(m for m in t.getmembers() if m.isfile() and m.name.endswith('/stockfish-android-arm64-universal'))
    lib.write_bytes(t.extractfile(binary).read())
    for m in t.getmembers():
        if m.isfile() and m.name.rsplit('/',1)[-1] in ('Copying.txt','AUTHORS'):
            (assets/m.name.rsplit('/',1)[-1]).write_bytes(t.extractfile(m).read())
source = fetch('https://codeload.github.com/official-stockfish/Stockfish/zip/refs/tags/sf_19', 'stockfish-19-source.zip')
shutil.copyfile(source, assets/'engine-source.zip')
lock = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (engine_archive, source)}
(ROOT/'android/dependencies.sha256.json').write_text(json.dumps(lock, indent=2))
print('Android SDK and Stockfish ready', flush=True)
