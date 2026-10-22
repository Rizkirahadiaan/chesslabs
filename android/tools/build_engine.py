"""Cross-compile the local Stockfish distribution for Android ARM64 + 16K pages."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
config=json.loads((ROOT/'config.json').read_text())
original=Path(config['stockfish_path']).parent
work=ROOT/'work/android-stockfish'
work.mkdir(parents=True,exist_ok=True)
src=work/'src'
shutil.copytree(original/'src',src,dirs_exist_ok=True)
ndk=ROOT/'work/android-sdk/android-ndk-r27d/toolchains/llvm/prebuilt/windows-x86_64'
clang=ndk/'bin/clang.exe'
net=re.search(r'#define EvalFileDefaultName "([^"]+)"',(src/'evaluate.h').read_text()).group(1)
if not (src/net).exists():
    subprocess.run([config['stockfish_path']],input=f'export_net {src/net}\nquit\n',text=True,cwd=src,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
if not (src/net).exists():raise RuntimeError('NNUE export failed')
if not hashlib.sha256((src/net).read_bytes()).hexdigest().startswith(net[3:15]):raise RuntimeError('NNUE checksum mismatch')
if '--prepare-only' in sys.argv:
    print('Stockfish source and verified NNUE ready',flush=True)
    raise SystemExit(0)
make=(src/'Makefile').read_text()
sources=re.search(r'SRCS = (.*?)\n\n',make,re.S).group(1).replace('\\\n',' ').split()
flags=['--driver-mode=g++','--target=aarch64-linux-android34','--sysroot='+str(ndk/'sysroot'),'-std=c++17','-O3','-DNDEBUG','-DIS_64BIT','-DUSE_NEON','-DUSE_POPCNT','-fno-exceptions','-fPIE','-pthread']
def compile_one(name):
    obj=work/(name.replace('/','_')+'.o')
    print('Compile',name,flush=True)
    subprocess.run([str(clang)]+flags+['-c',name,'-o',str(obj)],cwd=src,check=True)
    return obj
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:objects=list(pool.map(compile_one,sources))
target=ROOT/'android/app/src/main/jniLibs/arm64-v8a/libstockfish.so'
target.parent.mkdir(parents=True,exist_ok=True)
subprocess.run([str(clang)]+flags+['-static-libstdc++','-pie','-Wl,-z,max-page-size=16384']+[str(o) for o in objects]+['-o',str(target)],cwd=src,check=True)
subprocess.run([str(ndk/'bin/llvm-strip.exe'),str(target)],check=True)
assets=ROOT/'android/app/src/main/assets';assets.mkdir(parents=True,exist_ok=True)
for name in ('Copying.txt','AUTHORS'):shutil.copyfile(original/name,assets/name)
with zipfile.ZipFile(assets/'engine-source.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in src.rglob('*'):
        if p.is_file():z.write(p,'stockfish/src/'+p.relative_to(src).as_posix())
    for name in ('Copying.txt','AUTHORS'):z.write(original/name,'stockfish/'+name)
    z.write(Path(__file__),'build_engine.py')
(ROOT/'android/engine-build.json').write_text(json.dumps({'source':'local Stockfish distribution','architecture':'ARM64 NEON','ndk':'r27d','api':34,'page_alignment':16384,'binary_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'network':net},indent=2))
print('Android Stockfish built:',target,flush=True)
