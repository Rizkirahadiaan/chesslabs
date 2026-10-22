"""Exercise PC-style automation, incremental vision, and UCI cancellation on the JVM."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

root=Path(__file__).resolve().parents[2]
fixtures=root/'work/android-vision-tests'
out=root/'work/android-automation-tests';out.mkdir(parents=True,exist_ok=True)
stubs=list((root/'android/tests/stubs').rglob('*.java'))
java=root/'android/app/src/main/java/id/chesslab/coach'
tests=[root/f'android/tests/{name}.java' for name in ['AutomationCheck','VisionSpeedCheck','EngineCheck']]
sources=stubs+[java/f'{name}.java' for name in ['Board','Vision','AutoTracker','Timing','Engine']]+tests
subprocess.run(['javac','-encoding','UTF-8','-d',str(out)]+[str(p) for p in sources],check=True)

baseline=root/'work/android-speed-backup/android__app__src__main__java__id__chesslab__coach__Vision.java'
if baseline.exists():
    old=out/'baseline';old.mkdir(exist_ok=True)
    shutil.copyfile(baseline,old/'Vision.java')
    subprocess.run(['javac','-encoding','UTF-8','-d',str(old)]+[str(p) for p in stubs+[java/'Board.java',old/'Vision.java',root/'android/tests/VisionBaseline.java']],check=True)
    subprocess.run(['java','-cp',str(old),'VisionBaseline',str(fixtures)],check=True)

automation=subprocess.check_output(['java','-cp',str(out),'AutomationCheck'],text=True)
print(automation,end='')
subprocess.run(['java','-cp',str(out),'VisionSpeedCheck',str(fixtures)],check=True)
config=json.loads((root/'config.json').read_text())
engine=subprocess.check_output(['java','-cp',str(out),'EngineCheck',config['stockfish_path']],text=True)
print(engine,end='')
report={
    'automation_assertions':int(re.search(r'(\d+) automation assertions',automation).group(1)),
    'recognition':json.loads((fixtures/'performance.json').read_text()),
    'engine_levels_tested':5,
    'engine_cancellation_tested':True,
    'human_uses_requested_budget':True,
    'runtime':'Windows JVM / Windows Stockfish; not an Android device benchmark',
    'source_sha256':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sources+[Path(__file__).resolve()]},
}
if baseline.exists():report['baseline_0_1_1']=json.loads((fixtures/'baseline.json').read_text())
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
speed=report['recognition']
baseline_ms=report.get('baseline_0_1_1',{}).get('full_ms')
baseline_text=f'{baseline_ms:.2f} ms' if baseline_ms is not None else 'Tidak diukur'
(out/'performance.md').write_text(f'''# Respons Android 0.2.0

Pengukuran JVM di komputer pengembangan, memakai gambar papan buatan 738 piksel.
Adapter gambar memakai piksel ARGB seperti buffer capture Android. Ini bukan
benchmark Samsung A34, bukan pengukuran aplikasi PC Python, dan tidak termasuk
waktu tangkap layar, penantian stabil, atau gambar overlay.

| Pembacaan | Median |
|---|---:|
| Versi Android 0.1.1, baca penuh | {baseline_text} |
| Versi Android 0.2.0, baca penuh | {speed['full_ms']:.2f} ms |
| Papan tidak berubah | {speed['unchanged_ms']:.2f} ms |
| Dua petak berubah | {speed['two_tiles_ms']:.2f} ms |

Cache diuji: 0 dari 64 petak dihitung ulang untuk gambar yang tidak berubah;
hanya 2 petak dihitung ulang setelah satu langkah. Pergantian tema atau area
mengosongkan cache. Tema versi sebelumnya juga diuji.

Profil mengikuti PC: interval target 80 / 120 / 180 ms dan anggaran Stockfish
180 / 450 / 1.200 ms. Human memakai anggaran yang sama tanpa pengali 3.
Hasil aktual bergantung pada perangkat dan kompleksitas posisi.

{report['automation_assertions']} pemeriksaan logika otomatis lulus, termasuk orientasi, partai baru,
menyusul dua ply, sambung tengah permainan, dan pembatasan pencarian ulang.
Kelima level UCI, mat, pembatalan analisis lama, serta analisis berikutnya diuji
menggunakan Stockfish Windows. Runtime Android belum diuji langsung.
''',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
