package id.chesslab.coach;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.graphics.*;
import android.hardware.display.*;
import android.media.*;
import android.media.projection.*;
import android.os.*;
import android.view.*;
import java.io.*;
import java.nio.ByteBuffer;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class CaptureService extends Service {
    public static volatile boolean running;
    private final Handler main=new Handler(Looper.getMainLooper());
    private HandlerThread thread;private Handler worker;
    private final ExecutorService engines=Executors.newSingleThreadExecutor(),scans=Executors.newSingleThreadExecutor();
    private volatile Engine engine;private final AtomicBoolean engineBusy=new AtomicBoolean(),scanBusy=new AtomicBoolean();
    private final AtomicInteger generation=new AtomicInteger();private volatile boolean destroyed;
    private MediaProjection projection;private VirtualDisplay display;private ImageReader imageReader;private Overlay overlay;
    private SharedPreferences prefs;private int width,height,density,layoutEpoch;
    private Rect box,pendingBox;private volatile Rect panelBounds=new Rect();
    private Bitmap captureBuffer;private ByteBuffer paddedBuffer;
    private boolean paused,calibrating,scanRequested=true,forceArea,pendingForced,persistBox,positionReady;
    private boolean training,trainingBottom,followLatched,playerWhite=true;
    private long learnAt,lastScan=-3000,lastPanelCheck,lastMetrics,engineRetryAt;
    private String level="Human",colour="Otomatis saat mulai",orientationMode="Otomatis",startupTurn="Auto",lastAnalysed,lastStatus="";
    private Timing timing=Timing.forName("Cepat");
    private AutoTracker tracker;private final AutoTracker.RecoveryGate recovery=new AutoTracker.RecoveryGate();
    private Vision.Reader recognizer=new Vision.Reader(),trainingReader;
    private final List<Vision.Theme> themes=new ArrayList<>();private Vision.Theme activeTheme,trainingTheme,pendingTheme;
    private String terminalFen;private boolean terminal;
    private final Map<String,Engine.Advice> adviceCache=new LinkedHashMap<String,Engine.Advice>(16,.75f,true){
        protected boolean removeEldestEntry(Map.Entry<String,Engine.Advice> entry){return size()>16;}
    };
    private double readMillis;private int changedTiles;private long engineMillis;
    private final Runnable captureLoop=new Runnable(){
        public void run(){
            if(destroyed)return;
            long started=SystemClock.elapsedRealtime();frame(imageReader);
            if(!destroyed)worker.postDelayed(this,Math.max(8,timing.pollMillis-(SystemClock.elapsedRealtime()-started)));
        }
    };

    @Override public void onCreate(){super.onCreate();prefs=getSharedPreferences("coach",MODE_PRIVATE);thread=new HandlerThread("screen-reader");thread.start();worker=new Handler(thread.getLooper());}
    @Override public IBinder onBind(Intent i){return null;}
    @Override public int onStartCommand(Intent intent,int flags,int id){
        if(intent==null){stopSelf();return START_NOT_STICKY;}
        String action=intent.getAction();
        if("stop".equals(action)){stopSelf();return START_NOT_STICKY;}
        if("settings".equals(action) || "join".equals(action)){
            worker.post(()->{loadSettings("settings".equals(action));notReady();paused=false;status("join".equals(action)?"Membaca posisi sekarang…":"Mencocokkan FEN yang disimpan…");});
            return START_NOT_STICKY;
        }
        if(projection!=null)return START_NOT_STICKY;
        try {
            NotificationManager nm=getSystemService(NotificationManager.class);
            nm.createNotificationChannel(new NotificationChannel("capture","Pembacaan papan aktif",NotificationManager.IMPORTANCE_LOW));
            PendingIntent stop=PendingIntent.getService(this,0,new Intent(this,CaptureService.class).setAction("stop"),PendingIntent.FLAG_IMMUTABLE);
            PendingIntent open=PendingIntent.getActivity(this,1,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
            Notification note=new Notification.Builder(this,"capture").setSmallIcon(R.drawable.ic_coach).setContentTitle("ChessLab membaca layar")
                .setContentText("Pemrosesan lokal · ketuk untuk pengaturan").setContentIntent(open).setOngoing(true)
                .addAction(new Notification.Action.Builder(null,"Hentikan",stop).build()).build();
            startForeground(1,note,ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
            Intent data=intent.getParcelableExtra("data",Intent.class);if(data==null)throw new IllegalArgumentException("Izin layar tidak tersedia");
            projection=getSystemService(MediaProjectionManager.class).getMediaProjection(intent.getIntExtra("result",0),data);
            if(projection==null)throw new IllegalStateException("Izin layar ditolak");
            Rect screen=getSystemService(WindowManager.class).getMaximumWindowMetrics().getBounds();
            width=screen.width();height=screen.height();density=getResources().getDisplayMetrics().densityDpi;
            overlay=new Overlay(this,this::command);
            projection.registerCallback(new MediaProjection.Callback(){
                @Override public void onStop(){main.post(()->{status("Berbagi layar berakhir. Mulai sesi baru dari Coach.");stopSelf();});}
                @Override public void onCapturedContentResize(int w,int h){if(w>0 && h>0 && (w!=width || h!=height))resize(w,h);}
            },worker);
            worker.post(()->{
                if(destroyed)return;
                try{
                    loadSettings(false);loadThemes();loadBox();createReader();
                    display=projection.createVirtualDisplay("ChessLab capture",width,height,density,DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,imageReader.getSurface(),null,worker);
                    worker.post(captureLoop);
                    main.post(()->{if(!destroyed)running=true;});status("Buka papan. Pencarian dan pembacaan berjalan otomatis.");
                    engines.submit(()->{try{prepareEngine();}catch(Exception ignored){/* Retry when advice is requested. */}});
                }catch(Exception e){fail(e);}
            });
        }catch(Exception e){fail(e);}
        return START_NOT_STICKY;
    }
    private void loadSettings(boolean exactFen){
        level=prefs.getString("level","Human");colour=prefs.getString("colour","Otomatis saat mulai");
        timing=Timing.forName(prefs.getString("response","Cepat"));orientationMode=prefs.getString("orientationMode","Otomatis");
        startupTurn=prefs.getString("startupTurn","Auto");
        boolean bottom=orientationMode.equals("Otomatis")?prefs.getString("orientation","Putih").equals("Putih"):orientationMode.equals("Putih");
        tracker=new AutoTracker(new Board(prefs.getString("fen",Board.START)),bottom,!exactFen,startupTurn,orientationMode.equals("Otomatis"));
        followLatched=false;recognizer.clear();recovery.reset();
        main.post(()->{if(!destroyed)overlay.profile(timing.name);});
    }
    private File themeDir(){File d=new File(getFilesDir(),"themes");d.mkdirs();return d;}
    private void loadThemes(){
        themes.clear();File[] files=themeDir().listFiles((d,n)->n.endsWith(".bin"));
        if(files!=null){Arrays.sort(files,Comparator.comparing(File::getName).reversed());for(File f:files){try{themes.add(Vision.Theme.load(f));}catch(IOException ignored){}}}
        if(!themes.isEmpty())activeTheme=themes.get(0);
    }
    private void loadBox(){
        if(prefs.getInt("screenWidth",0)==width && prefs.getInt("screenHeight",0)==height){
            Rect r=new Rect(prefs.getInt("left",0),prefs.getInt("top",0),prefs.getInt("right",0),prefs.getInt("bottom",0));if(validBox(r))box=r;
        }
        scanRequested=box==null;
    }
    private boolean validBox(Rect r){return r!=null && r.left>=0 && r.top>=0 && r.right<=width && r.bottom<=height && r.width()>=160 && r.height()>=160;}
    private void saveBox(){prefs.edit().putInt("screenWidth",width).putInt("screenHeight",height).putInt("left",box.left).putInt("top",box.top).putInt("right",box.right).putInt("bottom",box.bottom).apply();persistBox=false;}
    private void createReader(){imageReader=ImageReader.newInstance(width,height,PixelFormat.RGBA_8888,2);}
    private void clearCapture(){if(captureBuffer!=null){captureBuffer.recycle();captureBuffer=null;}paddedBuffer=null;}
    private void resize(int w,int h){
        layoutEpoch++;pendingBox=box=null;scanRequested=true;forceArea=false;notReady();if(tracker!=null)tracker.unstable();recognizer.clear();clearCapture();width=w;height=h;
        if(display!=null){display.setSurface(null);if(imageReader!=null)imageReader.close();createReader();display.resize(width,height,density);display.setSurface(imageReader.getSurface());}
        status("Ukuran layar berubah. Mencari ulang papan otomatis…");
    }
    private void command(String command){
        if(command.equals("stop")){stopSelf();return;}
        if(command.equals("area")){
            worker.post(()->{calibrating=true;layoutEpoch++;pendingBox=null;notReady();clearCapture();});
            overlay.select(rect->worker.post(()->{
                calibrating=false;if(validBox(rect)){box=rect;saveBox();recognizer.clear();tracker.unstable();paused=false;status("Area tersimpan. Membaca otomatis…");}
                else status("Area tidak valid. Pilih seluruh papan persegi 8×8.");
            }));return;
        }
        worker.post(()->{
            if(tracker==null)return;
            switch(command){
                case "pause":paused=!paused;notReady();clearCapture();tracker.unstable();status(paused?"Dijeda. Ketuk Jeda/Lanjut untuk melanjutkan.":"Membaca papan otomatis…");break;
                case "detect":layoutEpoch++;pendingBox=null;scanRequested=true;forceArea=true;paused=false;notReady();status("Mencari papan… Geser panel keluar dari papan.");break;
                case "learn":layoutEpoch++;pendingBox=null;training=true;trainingTheme=null;trainingReader=new Vision.Reader();learnAt=SystemClock.elapsedRealtime()+400;paused=false;notReady();status("Belajar: tampilkan POSISI AWAL lengkap dan diam.");break;
                case "flip":tracker.whiteBottom=!tracker.whiteBottom;tracker.unstable();prefs.edit().putString("orientation",tracker.whiteBottom?"Putih":"Hitam").apply();notReady();status("Sisi bawah: "+(tracker.whiteBottom?"Putih":"Hitam"));break;
                case "join":tracker=new AutoTracker(new Board(Board.START),tracker.whiteBottom,true,startupTurn,orientationMode.equals("Otomatis"));paused=false;notReady();status("Membaca posisi sekarang…");break;
                case "profile":timing=timing.next();prefs.edit().putString("response",timing.name).apply();invalidateAnalysis();main.post(()->{if(!destroyed)overlay.profile(timing.name);});status("Respons "+timing.name);requestAdvice();break;
            }
        });
    }
    private void invalidateAnalysis(){generation.incrementAndGet();lastAnalysed=null;main.post(()->{if(!destroyed && overlay!=null)overlay.hideMove();});}
    private void notReady(){if(positionReady || lastAnalysed!=null)invalidateAnalysis();positionReady=false;}
    private void status(String text){
        if(text.equals(lastStatus))return;lastStatus=text;prefs.edit().putString("status",text).apply();
        main.post(()->{if(!destroyed && overlay!=null)overlay.message(text);});
    }
    private void metrics(){
        long now=SystemClock.elapsedRealtime();if(now-lastMetrics<250)return;lastMetrics=now;
        String text=String.format(Locale.US,"Baca %.1f ms · %d/64 petak · Mesin %d ms",readMillis,changedTiles,engineMillis);
        main.post(()->{if(!destroyed)overlay.metrics(text);});
    }
    private void fail(Exception e){status("Coach berhenti: "+e.getMessage());main.post(this::stopSelf);}
    private void frame(ImageReader source){
        if(destroyed || source==null || source!=imageReader)return;
        try(Image image=source.acquireLatestImage()){
            if(calibrating || paused)return;
            long now=SystemClock.elapsedRealtime();
            // A static screen may not produce another image. Keep polling and use
            // its last pixels, rather than dropping the final frame of a move.
            if(image==null){if(captureBuffer!=null)process(captureBuffer,now);return;}
            Image.Plane plane=image.getPlanes()[0];int stride=plane.getRowStride();
            if(plane.getPixelStride()!=4)throw new IOException("Format layar tidak didukung");
            int paddedWidth=stride/4;
            if(captureBuffer==null || captureBuffer.getWidth()!=paddedWidth || captureBuffer.getHeight()!=image.getHeight()){
                clearCapture();captureBuffer=Bitmap.createBitmap(paddedWidth,image.getHeight(),Bitmap.Config.ARGB_8888);
            }
            ByteBuffer buffer=plane.getBuffer();int bytes=stride*image.getHeight();
            if(buffer.remaining()<bytes){
                if(paddedBuffer==null || paddedBuffer.capacity()!=bytes)paddedBuffer=ByteBuffer.allocateDirect(bytes);
                paddedBuffer.clear();paddedBuffer.put(buffer);paddedBuffer.rewind();buffer=paddedBuffer;
            }
            captureBuffer.copyPixelsFromBuffer(buffer);process(captureBuffer,now);
        }catch(Exception e){notReady();if(tracker!=null)tracker.unstable();status("Pembacaan: "+e.getMessage()+". Mencoba lagi…");}
    }
    private void queueScan(Bitmap bitmap,long now){
        if(!scanBusy.compareAndSet(false,true))return;
        scanRequested=false;lastScan=now;final int epoch=layoutEpoch;final boolean forced=forceArea;forceArea=false;
        final Bitmap snapshot;
        try{Bitmap crop=Bitmap.createBitmap(bitmap,0,0,width,height);snapshot=crop==bitmap?bitmap.copy(Bitmap.Config.ARGB_8888,false):crop;}
        catch(RuntimeException e){scanBusy.set(false);throw e;}
        final Rect previous=box==null?null:new Rect(box);final boolean bottom=tracker.whiteBottom;
        final List<Vision.Theme> savedThemes=new ArrayList<>(themes);
        scans.submit(()->{
            Rect found=null;Vision.Theme match=null;
            try{
                // Theme fallback and board search both run away from the capture loop.
                if(!forced && previous!=null)for(Vision.Theme theme:savedThemes){
                    if(Vision.read(snapshot,previous,theme,bottom).placement!=null){found=previous;match=theme;break;}
                }
                if(found==null){
                    found=Vision.detect(snapshot);
                    if(found!=null)for(Vision.Theme theme:savedThemes){
                        if(Vision.read(snapshot,found,theme,bottom).placement!=null){match=theme;break;}
                    }
                }
            }catch(Exception ignored){}finally{snapshot.recycle();}
            final Rect detected=found;final Vision.Theme detectedTheme=match;
            worker.post(()->{
                scanBusy.set(false);if(destroyed || epoch!=layoutEpoch)return;
                if(validBox(detected)){pendingBox=detected;pendingTheme=detectedTheme;pendingForced=forced;}
                else if(box==null)status("Papan belum ditemukan. Pencarian otomatis berlanjut; Area tetap tersedia.");
            });
        });
    }
    private void usePending(Bitmap bitmap){
        Rect candidate=pendingBox;pendingBox=null;Vision.Theme suggested=pendingTheme;pendingTheme=null;
        if(!validBox(candidate) || Rect.intersects(panelBounds,candidate))return;
        Vision.Reader nextReader=new Vision.Reader();Vision.Theme matched=null;
        if(suggested!=null && nextReader.read(bitmap,candidate,suggested,tracker.whiteBottom).placement!=null)matched=suggested;
        if(suggested==null && activeTheme!=null && nextReader.read(bitmap,candidate,activeTheme,tracker.whiteBottom).placement!=null)matched=activeTheme;
        if(box!=null && !pendingForced && matched==null)return;
        box=candidate;persistBox=true;recognizer=nextReader;if(matched!=null)activeTheme=matched;
        tracker.unstable();notReady();recovery.reset();
    }
    private void learn(Bitmap bitmap,long now)throws Exception{
        if(now<learnAt)return;
        try{
            if(trainingTheme==null){
                Boolean bottom=orientationMode.equals("Otomatis")?Vision.initialWhiteBottom(bitmap,box):Boolean.valueOf(tracker.whiteBottom);
                if(bottom==null){training=false;status("Warna belum jelas. Pilih sisi bawah di pengaturan lalu Pelajari.");return;}
                trainingBottom=bottom;trainingTheme=Vision.Theme.train(bitmap,box,trainingBottom);
            }
            Vision.Observation observation=trainingReader.read(bitmap,box,trainingTheme,trainingBottom);
            if(!new Board(Board.START).placement().equals(observation.placement))throw new IllegalArgumentException("Kembalikan semua bidak ke posisi awal lalu ketuk Pelajari.");
            if(trainingReader.classifiedTiles!=0)return;
            trainingTheme.save(new File(themeDir(),"theme-"+System.currentTimeMillis()+".bin"));
            themes.add(0,trainingTheme);activeTheme=trainingTheme;recognizer=trainingReader;training=false;
            tracker=new AutoTracker(new Board(Board.START),trainingBottom,true,startupTurn,orientationMode.equals("Otomatis"));
            prefs.edit().putString("orientation",trainingBottom?"Putih":"Hitam").putString("fen",Board.START).apply();
            followLatched=false;saveBox();status("Tema tersimpan. Langkah dan partai berikutnya dibaca otomatis.");
        }catch(IllegalArgumentException e){training=false;trainingTheme=null;status(e.getMessage());}
    }
    private void process(Bitmap bitmap,long now)throws Exception{
        if(now-lastPanelCheck>=150){lastPanelCheck=now;main.post(()->{if(!destroyed)panelBounds=overlay.panelBounds();});}
        if(scanRequested || box==null && now-lastScan>=3000)queueScan(bitmap,now);
        if(pendingBox!=null)usePending(bitmap);
        if(!validBox(box))return;
        if(Rect.intersects(panelBounds,box)){notReady();tracker.unstable();status("Geser panel Coach keluar dari area papan.");return;}
        if(training){learn(bitmap,now);return;}
        if(activeTheme==null){status("Papan ditemukan. Tampilkan posisi awal dan ketuk Pelajari sekali untuk tema baru.");return;}
        long started=System.nanoTime();Vision.Observation observation=recognizer.read(bitmap,box,activeTheme,tracker.whiteBottom);
        readMillis=(System.nanoTime()-started)/1e6;changedTiles=recognizer.classifiedTiles;
        if(observation.placement==null){
            notReady();tracker.unstable();status(observation.guidance());metrics();
            if(recovery.shouldScan(now,false,lastScan))queueScan(bitmap,now);return;
        }
        recovery.shouldScan(now,true,lastScan);
        String oldFen=tracker.board.fen();boolean oldBottom=tracker.whiteBottom;
        AutoTracker.Result result=tracker.observe(observation.placement);
        if(!result.ready()){notReady();status(result.message);metrics();return;}
        if(!oldFen.equals(result.board.fen()) || oldBottom!=tracker.whiteBottom || result.newGame)invalidateAnalysis();
        positionReady=true;
        if(result.newGame){adviceCache.clear();followLatched=false;}
        if(!followLatched){playerWhite=tracker.whiteBottom;followLatched=true;}
        if(colour.equals("Putih"))playerWhite=true;else if(colour.equals("Hitam"))playerWhite=false;
        if(persistBox)saveBox();
        if(oldBottom!=tracker.whiteBottom)prefs.edit().putString("orientation",tracker.whiteBottom?"Putih":"Hitam").apply();
        Board board=result.board;
        if(!board.fen().equals(terminalFen)){terminalFen=board.fen();terminal=board.legalMoves().isEmpty();}
        if(terminal){status(board.inCheck(board.white)?"Skakmat. Menunggu partai baru otomatis.":"Pat. Menunggu partai baru otomatis.");metrics();return;}
        if(board.white!=playerWhite){status("Menunggu lawan · "+level);metrics();return;}
        requestAdvice();metrics();
    }
    private Engine prepareEngine()throws Exception{
        if(destroyed)return null;
        if(engine==null)engine=new Engine(new File(getApplicationInfo().nativeLibraryDir,"libstockfish.so").getAbsolutePath());
        if(destroyed){engine.close();engine=null;return null;}return engine;
    }
    private String adviceKey(){return tracker.board.fen()+"|"+level+"|"+timing.thinkMillis;}
    private void requestAdvice(){
        if(destroyed || paused || training || terminal || !positionReady || tracker.board.white!=playerWhite || SystemClock.elapsedRealtime()<engineRetryAt)return;
        String key=adviceKey();if(key.equals(lastAnalysed))return;
        Engine.Advice cached=adviceCache.get(key);
        if(cached!=null){lastAnalysed=key;showAdvice(cached,generation.get());return;}
        if(!engineBusy.compareAndSet(false,true))return;
        final Board position=tracker.board.copy();final int token=generation.get(),budget=timing.thinkMillis;final String chosenLevel=level;
        lastAnalysed=key;status("Menganalisis · "+level+" · "+timing.name);
        engines.submit(()->{
            try{
                Engine active=prepareEngine();if(active==null)return;
                Engine.Advice advice=active.analyse(position,chosenLevel,budget,()->destroyed || token!=generation.get());
                worker.post(()->{
                    if(destroyed || token!=generation.get() || !positionReady)return;
                    if(advice!=null){adviceCache.put(key,advice);showAdvice(advice,token);}else lastAnalysed=null;
                });
            }catch(Exception e){
                if(engine!=null){engine.close();engine=null;}
                worker.post(()->{if(!destroyed && token==generation.get()){lastAnalysed=null;engineRetryAt=SystemClock.elapsedRealtime()+1000;status("Mesin: "+e.getMessage()+". Mencoba lagi…");}});
            }finally{
                engineBusy.set(false);
                // Start the latest position without waiting for another screenshot.
                worker.post(this::requestAdvice);
            }
        });
    }
    private void showAdvice(Engine.Advice advice,int token){
        if(token!=generation.get() || !positionReady)return;
        engineMillis=advice.milliseconds;final Rect area=new Rect(box);final boolean bottom=tracker.whiteBottom;
        String message=advice.move+"  "+advice.score+" · "+level+"\n"+advice.line;
        status(message);metrics();
        main.post(()->{if(!destroyed && token==generation.get())overlay.move(area,advice.move,bottom);});
    }
    @Override public void onDestroy(){
        destroyed=true;running=false;generation.incrementAndGet();
        worker.removeCallbacks(captureLoop);
        if(overlay!=null)overlay.close();
        worker.post(()->{if(display!=null)display.release();if(imageReader!=null)imageReader.close();if(projection!=null)projection.stop();clearCapture();thread.quitSafely();});
        if(engine!=null)engine.close();engines.shutdownNow();scans.shutdownNow();stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy();
    }
}
