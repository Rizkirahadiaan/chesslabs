package id.chesslab.coach;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.media.projection.*;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;

public final class MainActivity extends Activity {
    private Spinner level,colour,orientation,response,startupTurn;private EditText fen;private TextView status;
    private android.content.SharedPreferences prefs;
    private static final int CAPTURE=30;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);prefs=getSharedPreferences("coach",MODE_PRIVATE);
        ScrollView scroll=new ScrollView(this);LinearLayout body=new LinearLayout(this);body.setOrientation(1);body.setPadding(24,24,24,32);scroll.addView(body);setContentView(scroll);
        scroll.setOnApplyWindowInsetsListener((v,insets)->{android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars());v.setPadding(bars.left,bars.top,bars.right,bars.bottom);return insets;});
        title(body,"ChessLab Coach",28);title(body,"ANDROID · PAPAN DINAMIS",12);
        title(body,"Baca papan, pilih langkah",21);
        text(body,"Coach mengenali papan 2D dari layar, menjalankan Stockfish di HP, dan memberi rekomendasi. Gunakan pada latihan atau permainan yang mengizinkan bantuan.");
        level=spinner(body,"Kecerdasan",Engine.LEVELS,prefs.getString("level","Human"));
        text(body,"Human memilih variasi langkah kuat dengan toleransi hingga 0,35 pion. Estimasi kekuatan dapat berkurang.");
        response=spinner(body,"Respons",new String[]{"Cepat","Seimbang","Mendalam"},prefs.getString("response","Cepat"));
        colour=spinner(body,"Anda bermain",new String[]{"Otomatis saat mulai","Putih","Hitam"},prefs.getString("colour","Otomatis saat mulai"));
        orientation=spinner(body,"Sisi bawah",new String[]{"Otomatis","Putih","Hitam"},prefs.getString("orientationMode","Otomatis"));
        text(body,"Tema tersimpan dipakai otomatis. Untuk tema baru, tampilkan POSISI AWAL lengkap lalu tekan Pelajari sekali. Membalik tampilan tidak mengubah warna pemain Anda.");
        startupTurn=spinner(body,"Giliran awal saat menyambung posisi",new String[]{"Auto","Putih","Hitam"},prefs.getString("startupTurn","Auto"));
        text(body,"Auto menunggu satu langkah untuk memastikan giliran. Hak rokade dan en passant sebelum sesi tidak ditebak; gunakan FEN lengkap jika diperlukan.");
        title(body,"Sambung posisi",18);fen=new EditText(this);fen.setSingleLine(false);fen.setText(prefs.getString("fen",Board.START));fen.setHint("FEN lengkap");body.addView(fen);
        button(body,"Gunakan posisi awal",()->fen.setText(Board.START));
        button(body,"Simpan pengaturan / sinkronkan FEN",()->{if(save()){command("settings");toast("Pengaturan tersimpan. Papan akan dicocokkan dengan FEN ini.");}});
        button(body,"Simpan pengaturan / baca posisi sekarang",()->{if(save()){command("join");toast("Pengaturan tersimpan. Buka papan untuk menyambung posisi.");}});
        title(body,"Mulai sesi",18);
        button(body,"1. Izinkan tampil di atas aplikasi",()->startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,Uri.parse("package:"+getPackageName()))));
        button(body,"2. Mulai pembacaan layar",this::startCapture);
        button(body,"Hentikan sesi",()->{stopService(new Intent(this,CaptureService.class));toast("Sesi dihentikan");});
        text(body,"Setelah berbagi layar, buka papan tujuan. Pencarian, pembacaan, orientasi dan partai baru ditangani otomatis. Baca kini menyambung posisi berjalan; tombol Cepat mengganti kecepatan. Cari dan Area tetap tersedia. Geser panel agar tidak menutupi papan.");
        text(body,"Tema tersimpan otomatis dan dicoba kembali saat tampilan berubah. Papan 3D/animasi berat tidak didukung. Jika layar dilindungi atau overlay diblokir aplikasi, pembacaan tidak tersedia.");
        status=text(body,"");
        button(body,"Lisensi & sumber Stockfish",()->new AlertDialog.Builder(this).setTitle("Stockfish 19 · GPLv3").setMessage("Stockfish 19 dibangun untuk ARM64 NEON. Sumber lengkap, jaringan evaluasi, dan lisensi disertakan dalam APK (assets/engine-source.zip dan Copying.txt).\n\nhttps://stockfishchess.org\nhttps://github.com/official-stockfish/Stockfish/tree/sf_19\n\nPemrosesan berlangsung lokal. APK tidak meminta izin internet dan tidak menyimpan tangkapan layar.").setPositiveButton("Tutup",null).show());
    }
    @Override public void onResume(){super.onResume();if(status!=null)status.setText((CaptureService.running?"Sesi aktif. ":"Sesi belum berjalan. ")+prefs.getString("status",""));}
    private boolean save(){try{new Board(fen.getText().toString());}catch(Exception e){toast("FEN: "+e.getMessage());return false;}
        prefs.edit().putString("level",level.getSelectedItem().toString()).putString("response",response.getSelectedItem().toString()).putString("colour",colour.getSelectedItem().toString()).putString("orientationMode",orientation.getSelectedItem().toString()).putString("startupTurn",startupTurn.getSelectedItem().toString()).putString("fen",fen.getText().toString().trim()).apply();return true;}
    private void startCapture(){
        if(CaptureService.running){toast("Sesi sudah aktif. Gunakan panel Coach atau hentikan dahulu.");return;}
        if(!Settings.canDrawOverlays(this)){toast("Aktifkan izin tampil di atas aplikasi terlebih dahulu.");return;}
        if(!save())return;
        if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},31);return;}
        requestCapture();
    }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] grants){super.onRequestPermissionsResult(request,permissions,grants);if(request==31)requestCapture();}
    private void requestCapture(){MediaProjectionManager m=getSystemService(MediaProjectionManager.class);Intent intent=Build.VERSION.SDK_INT>=34?m.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay()):m.createScreenCaptureIntent();startActivityForResult(intent,CAPTURE);}
    @Override public void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==CAPTURE && result==RESULT_OK && data!=null){Intent i=new Intent(this,CaptureService.class).setAction("start").putExtra("result",result).putExtra("data",data);startForegroundService(i);toast("Buka aplikasi papan. Panel Coach akan muncul.");}}
    private void command(String action){if(CaptureService.running)startService(new Intent(this,CaptureService.class).setAction(action));}
    private void toast(String message){Toast.makeText(this,message,Toast.LENGTH_LONG).show();}
    private TextView text(LinearLayout parent,String value){TextView v=new TextView(this);v.setText(value);v.setTextSize(15);v.setTextColor(Color.rgb(58,73,83));v.setPadding(0,10,0,12);parent.addView(v);return v;}
    private void title(LinearLayout parent,String value,int size){TextView v=text(parent,value);v.setTextSize(size);v.setTypeface(null,1);v.setTextColor(Color.rgb(18,61,71));}
    private Spinner spinner(LinearLayout parent,String label,String[] items,String selected){title(parent,label,16);Spinner s=new Spinner(this);ArrayAdapter<String> adapter=new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,items);s.setAdapter(adapter);for(int i=0;i<items.length;i++)if(items[i].equals(selected))s.setSelection(i);parent.addView(s);return s;}
    private void button(LinearLayout parent,String text,Runnable action){Button b=new Button(this);b.setText(text);b.setAllCaps(false);b.setOnClickListener(v->action.run());parent.addView(b,new LinearLayout.LayoutParams(-1,-2));}
}
