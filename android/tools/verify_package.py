"""Static packaging checks; deliberately does not claim a device runtime test."""
from pathlib import Path
import hashlib
import io
import json
import shutil
import subprocess
import zipfile

root=Path(__file__).resolve().parents[2]
apk=root/'outputs/android/ChessLab-Coach-Android.apk'
sdk=root/'work/android-sdk'
tools=next((sdk/'build-tools').rglob('aapt2.exe')).parent
signing=subprocess.check_output(['java','-jar',str(tools/'lib/apksigner.jar'),'verify','--verbose',str(apk)],text=True)
badging=subprocess.check_output([str(tools/'aapt2.exe'),'dump','badging',str(apk)],text=True)
assert 'Verifies' in signing
assert "minSdkVersion:'34'" in badging and "targetSdkVersion:'36'" in badging
assert "native-code: 'arm64-v8a'" in badging
assert "versionCode='4'" in badging and "versionName='0.2.1'" in badging
assert 'android.permission.INTERNET' not in badging
vision_path=root/'work/android-vision-tests/report.json'
vision=json.loads(vision_path.read_text())
assert vision['failures']==0
for name,digest in vision['source_sha256'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, f'Rerun vision tests after changing {name}'
automation_path=root/'work/android-automation-tests/report.json'
automation=json.loads(automation_path.read_text())
for name,digest in automation['source_sha256'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, f'Rerun automation tests after changing {name}'
with zipfile.ZipFile(apk) as z:
    assert z.testzip() is None
    native=z.read('lib/arm64-v8a/libstockfish.so')
    assert native[:4]==b'\x7fELF'
    expected=json.loads((root/'android/engine-build.json').read_text())['binary_sha256']
    assert hashlib.sha256(native).hexdigest()==expected
    with zipfile.ZipFile(io.BytesIO(z.read('assets/engine-source.zip'))) as source:
        assert source.testzip() is None
        assert 'stockfish/src/main.cpp' in source.namelist()
        net=source.read('stockfish/src/nn-1a298aa575a0.nnue')
        assert hashlib.sha256(net).hexdigest().startswith('1a298aa575a0')
    assert b'GNU GENERAL PUBLIC LICENSE' in z.read('assets/Copying.txt')
shutil.copyfile(root/'android/README.md',root/'outputs/android/PANDUAN-ANDROID.md')
shutil.copyfile(vision_path,root/'outputs/android/vision-verification.json')
shutil.copyfile(automation_path,root/'outputs/android/automation-verification.json')
shutil.copyfile(automation_path.parent/'performance.md',root/'outputs/android/HASIL-RESPONS-ANDROID.md')
report={'apk':apk.name,'bytes':apk.stat().st_size,'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),
        'version_name':'0.2.1','version_code':4,
        'signature_verified':True,'min_sdk':34,'target_sdk':36,'abi':'arm64-v8a','network_permission':False,
        'stockfish_source_and_nnue_bundled':True,'rules_perft_depth_4':197281,'legal_positions_compared':224,
        'recognition_fixture_positions':vision['fixture_positions'],'recognition_checks':vision['recognition_checks'],
        'mobile_autodetection_checks':vision['mobile_autodetection_checks'],
        'midgame_training_rejections':vision['midgame_training_rejections'],
        'per_square_diagnostic_tested':vision['per_square_diagnostic_tested'],
        'automation_assertions':automation['automation_assertions'],
        'engine_cancellation_tested':automation['engine_cancellation_tested'],
        'windows_uci_levels_tested':automation['engine_levels_tested'],
        'android_device_runtime_tested':False,'samsung_a34_tested':False}
(root/'outputs/android/verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
