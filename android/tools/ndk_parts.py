"""Download only ARM64 compiler/sysroot ZIP entries from Google's official NDK."""
import io, json, socket, struct, urllib.request, zipfile, zlib, http.client, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CACHE=ROOT/'work/android-downloads'
DEST=ROOT/'work/android-sdk'
URL='https://dl.google.com/android/repository/android-ndk-r27d-windows.zip'
SIZE=781506724
original=socket.getaddrinfo
def ipv4(host,port,family=0,type=0,proto=0,flags=0):return original(os.environ.get('CHESSLAB_GOOGLE_IP',host) if host=='dl.google.com' else host,port,socket.AF_INET,type,proto,flags)
socket.getaddrinfo=ipv4
connection=None
def read_range(start,count):
    global connection
    for attempt in range(5):
        try:
            if connection is None:connection=http.client.HTTPSConnection('dl.google.com',timeout=12)
            connection.request('GET','/android/repository/android-ndk-r27d-windows.zip',headers={'Range':f'bytes={start}-{start+count-1}'})
            r=connection.getresponse()
            if r.status!=206 or not r.headers.get('Content-Range','').startswith(f'bytes {start}-'):raise RuntimeError('Range unsupported')
            data=r.read()
            if len(data)!=count:raise RuntimeError('Incomplete download')
            return data
        except (OSError,http.client.HTTPException) as e:
            print('Retry download:',type(e).__name__,flush=True)
            if connection:connection.close()
            connection=None
            if attempt==4:raise
class Remote(io.RawIOBase):
    def __init__(self):self.pos=0
    def seekable(self):return True
    def seek(self,n,whence=0):self.pos=n if whence==0 else self.pos+n if whence==1 else SIZE+n;return self.pos
    def tell(self):return self.pos
    def read(self,n=-1):
        if n<0:n=SIZE-self.pos
        path=CACHE/f'ndk-range-{self.pos}-{n}.bin'
        data=path.read_bytes() if path.exists() else read_range(self.pos,n)
        if not path.exists():path.write_bytes(data)
        self.pos+=len(data);return data
with zipfile.ZipFile(Remote()) as z:
    entries=z.infolist()
    (CACHE/'ndk-files.json').write_text(json.dumps([{'name':f.filename,'size':f.file_size,'compressed':f.compress_size} for f in entries],indent=2))
    chosen=[]
    for f in entries:
        name=f.filename
        if f.is_dir():continue
        if '/toolchains/llvm/prebuilt/windows-x86_64/' not in name:continue
        local=name.split('/windows-x86_64/',1)[1]
        arm_lib=local.removeprefix('sysroot/usr/lib/aarch64-linux-android/')
        keep=(local.startswith('sysroot/usr/include/') or local.startswith('sysroot/usr/lib/aarch64-linux-android/') and ('/' not in arm_lib or arm_lib.startswith('34/'))
              or local.startswith('lib/clang/18/include/') or local.startswith('lib/clang/18/lib/linux/') and 'aarch64' in local
              or local in ['bin/clang.exe','bin/ld.lld.exe','bin/llvm-strip.exe','bin/llvm-readelf.exe']
              or local.startswith('bin/') and local.endswith('.dll'))
        if keep:chosen.append(f)
    print('Selected',len(chosen),'files, compressed MB',sum(f.compress_size for f in chosen)//1000000,flush=True)
    # Cache consecutive byte ranges to avoid thousands of tiny HTTP requests.
    groups=[]
    for f in sorted(chosen,key=lambda f:f.header_offset):
        start=f.header_offset;end=start+30+len(f.filename.encode())+f.compress_size+256
        if groups and start-groups[-1][1]<128*1024 and end-groups[-1][0]<16*1024*1024:
            groups[-1][1]=end;groups[-1][2].append(f)
        else:groups.append([start,end,[f]])
    for start,end,files in groups:
        if all((DEST/f.filename).exists() for f in files):continue
        path=CACHE/f'ndk-part-{start}-{end}.bin'
        if not path.exists():
            print('Fetching',round((end-start)/1000000,1),'MB',files[0].filename.rsplit('/',1)[-1],flush=True)
            path.write_bytes(read_range(start,end-start))
        data=path.read_bytes()
        for f in files:
            offset=f.header_offset-start
            header=struct.unpack_from('<4s5H3I2H',data,offset)
            begin=offset+30+header[-2]+header[-1]
            compressed=data[begin:begin+f.compress_size]
            content=zlib.decompress(compressed,-15) if f.compress_type==8 else compressed
            if len(content)!=f.file_size or zlib.crc32(content)!=f.CRC:raise RuntimeError('NDK CRC mismatch')
            target=DEST/f.filename
            if not target.resolve().is_relative_to(DEST.resolve()):raise ValueError('Unsafe path')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
print('ARM64 NDK components ready',flush=True)
