"""Build and sign the dependency-free Java Android app using local SDK tools."""
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT/'work/android-sdk'
WORK = ROOT/'work/android-build'
APP = ROOT/'android/app/src/main'
OUTPUT = ROOT/'outputs/android'
for d in (WORK/'classes',WORK/'generated',WORK/'dex',OUTPUT):d.mkdir(parents=True,exist_ok=True)
jar = next((SDK/'platforms').rglob('android.jar'))
tools = next((SDK/'build-tools').rglob('aapt2.exe')).parent
def run(*cmd):
    subprocess.run([str(v) for v in cmd],cwd=ROOT,check=True)
run(tools/'aapt2.exe','compile','--dir',APP/'res','-o',WORK/'resources.zip')
manifest=WORK/'AndroidManifest.xml'
manifest.write_text((APP/'AndroidManifest.xml').read_text().replace('<manifest ', '<manifest package="id.chesslab.coach" ', 1),encoding='utf-8')
run(tools/'aapt2.exe','link','-I',jar,'--manifest',manifest,
    '--java',WORK/'generated','--min-sdk-version','34','--target-sdk-version','36',
    '--version-code','4','--version-name','0.2.1','-o',WORK/'unsigned.apk',WORK/'resources.zip')
sources=list((APP/'java').rglob('*.java'))+list((WORK/'generated').rglob('*.java'))
argfile=WORK/'javac.args'
argfile.write_text('\n'.join('"'+str(p).replace('\\','/')+'"' for p in sources))
run('javac','-encoding','UTF-8','-source','17','-target','17','-classpath',jar,'-d',WORK/'classes','@'+str(argfile))
with zipfile.ZipFile(WORK/'classes.jar','w',zipfile.ZIP_DEFLATED) as z:
    for p in (WORK/'classes').rglob('*.class'):z.write(p,p.relative_to(WORK/'classes').as_posix())
run('java','-cp',tools/'lib/d8.jar','com.android.tools.r8.D8','--lib',jar,'--min-api','34','--output',WORK/'dex',WORK/'classes.jar')
engine=APP/'jniLibs/arm64-v8a/libstockfish.so'
if not engine.exists():raise SystemExit('Mesin ARM64 belum tersedia. Jalankan android/tools/prepare.py.')
with zipfile.ZipFile(WORK/'unsigned.apk','a',zipfile.ZIP_DEFLATED) as z:
    for p in (WORK/'dex').glob('*.dex'):z.write(p,p.name)
    z.write(engine,'lib/arm64-v8a/libstockfish.so')
    for p in (APP/'assets').rglob('*'):
        if p.is_file():z.write(p,'assets/'+p.relative_to(APP/'assets').as_posix())
run(tools/'zipalign.exe','-f','4',WORK/'unsigned.apk',WORK/'aligned.apk')
key=WORK/'development.jks'
if not key.exists():
    keytool=shutil.which('keytool') or str(Path('C:/Program Files/Java/jdk-17/bin/keytool.exe'))
    run(keytool,'-genkeypair','-keystore',key,'-storepass','android','-keypass','android','-alias','chesslab-dev',
        '-dname','CN=ChessLab Development','-keyalg','RSA','-keysize','2048','-validity','10000')
apk=OUTPUT/'ChessLab-Coach-Android.apk'
run('java','-jar',tools/'lib/apksigner.jar','sign','--ks',key,'--ks-key-alias','chesslab-dev','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,WORK/'aligned.apk')
run('java','-jar',tools/'lib/apksigner.jar','verify','--verbose',apk)
run(tools/'aapt2.exe','dump','badging',apk)
print('APK:',apk)
