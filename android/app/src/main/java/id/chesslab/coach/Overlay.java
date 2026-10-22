package id.chesslab.coach;

import android.content.Context;
import android.graphics.*;
import android.view.*;
import android.widget.*;
import java.util.function.Consumer;

final class Overlay {
    private static final long AUTO_HIDE_MS=5000;
    private final Context context;private final WindowManager wm;private final Consumer<String> action;
    private final android.os.Handler handler=new android.os.Handler(android.os.Looper.getMainLooper());
    private final android.content.SharedPreferences prefs;
    private final LinearLayout panel,content,controls;private final TextView status,metrics,logo;private final Markers markers;
    private Button profileButton,autoHideButton;
    private final WindowManager.LayoutParams panelParams;private Selection selection;private boolean closed,minimized,autoHide;
    private final Runnable hideTask=()->setMinimized(true);
    Overlay(Context context,Consumer<String> action){
        this.context=context;this.action=action;wm=context.getSystemService(WindowManager.class);
        prefs=context.getSharedPreferences("coach",Context.MODE_PRIVATE);autoHide=prefs.getBoolean("overlayAutoHide",true);
        markers=new Markers(context);wm.addView(markers,params(-1,-1,true));
        panel=new LinearLayout(context){
            @Override public boolean dispatchTouchEvent(MotionEvent event){
                if(event.getActionMasked()==MotionEvent.ACTION_DOWN)handler.removeCallbacks(hideTask);
                boolean handled=super.dispatchTouchEvent(event);
                if(event.getActionMasked()==MotionEvent.ACTION_UP || event.getActionMasked()==MotionEvent.ACTION_CANCEL)scheduleHide();
                return handled;
            }
        };
        panel.setOrientation(1);panel.setClickable(true);
        content=new LinearLayout(context);content.setOrientation(1);content.setPadding(dp(6),dp(4),dp(6),dp(4));content.setBackgroundColor(Color.rgb(233,242,244));panel.addView(content);
        TextView header=new TextView(context);header.setText("\u265f Coach \u00b7 geser di sini \u00b7 ketuk untuk minimalkan");header.setTextSize(12);header.setTextColor(Color.rgb(13,72,83));header.setPadding(0,dp(6),0,dp(6));content.addView(header);
        status=new TextView(context);status.setTextSize(12);status.setMaxLines(3);status.setTextColor(Color.BLACK);content.addView(status);
        controls=new LinearLayout(context);controls.setOrientation(1);content.addView(controls);
        String[][] rows={{"Jeda/Lanjut","Cari","Area","Baca kini"},{"Pelajari","Balik","Cepat","Stop"}};
        String[][] commands={{"pause","detect","area","join"},{"learn","flip","profile","stop"}};
        for(int r=0;r<rows.length;r++){LinearLayout row=new LinearLayout(context);controls.addView(row);for(int c=0;c<rows[r].length;c++){Button b=new Button(context);b.setText(rows[r][c]);b.setTextSize(10);b.setAllCaps(false);b.setPadding(0,0,0,0);String cmd=commands[r][c];if(cmd.equals("profile"))profileButton=b;b.setOnClickListener(v->action.accept(cmd));row.addView(b,new LinearLayout.LayoutParams(0,dp(38),1));}}
        LinearLayout visibilityRow=new LinearLayout(context);controls.addView(visibilityRow);
        autoHideButton=new Button(context);autoHideButton.setTextSize(10);autoHideButton.setAllCaps(false);autoHideButton.setPadding(0,0,0,0);updateAutoHideLabel();
        autoHideButton.setOnClickListener(v->{autoHide=!autoHide;prefs.edit().putBoolean("overlayAutoHide",autoHide).apply();updateAutoHideLabel();scheduleHide();});
        visibilityRow.addView(autoHideButton,new LinearLayout.LayoutParams(0,dp(40),2));
        Button minimize=new Button(context);minimize.setText("Minimalkan");minimize.setTextSize(10);minimize.setAllCaps(false);minimize.setPadding(0,0,0,0);minimize.setOnClickListener(v->setMinimized(true));visibilityRow.addView(minimize,new LinearLayout.LayoutParams(0,dp(40),1));
        metrics=new TextView(context);metrics.setTextSize(10);metrics.setTextColor(Color.rgb(58,73,83));metrics.setMaxLines(1);controls.addView(metrics);
        logo=new TextView(context);logo.setText("\u265f");logo.setTextSize(30);logo.setGravity(Gravity.CENTER);logo.setTextColor(Color.WHITE);
        android.graphics.drawable.GradientDrawable background=new android.graphics.drawable.GradientDrawable();background.setShape(android.graphics.drawable.GradientDrawable.OVAL);background.setColor(Color.rgb(13,72,83));logo.setBackground(background);
        logo.setContentDescription("Buka menu ChessLab Coach. Geser untuk memindahkan.");logo.setVisibility(View.GONE);panel.addView(logo,new LinearLayout.LayoutParams(dp(48),dp(48)));
        panelParams=params(expandedWidth(),-2,false);panelParams.x=dp(8);panelParams.y=dp(50);wm.addView(panel,panelParams);
        panel.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->{
            if(closed)return;
            int x=panelParams.x,y=panelParams.y;clampPosition();
            if(x!=panelParams.x || y!=panelParams.y)wm.updateViewLayout(panel,panelParams);
        });
        header.setOnClickListener(v->setMinimized(true));logo.setOnClickListener(v->setMinimized(false));
        installDrag(header);installDrag(logo);scheduleHide();
    }
    private int expandedWidth(){return Math.min(dp(320),context.getResources().getDisplayMetrics().widthPixels-dp(16));}
    private void updateAutoHideLabel(){autoHideButton.setText("Sembunyi otomatis: "+(autoHide?"ON":"OFF"));autoHideButton.setContentDescription("Sembunyi otomatis "+(autoHide?"aktif":"nonaktif")+". Ketuk untuk mengubah.");}
    private void scheduleHide(){handler.removeCallbacks(hideTask);if(!closed && autoHide && !minimized && selection==null)handler.postDelayed(hideTask,AUTO_HIDE_MS);}
    private void setMinimized(boolean value){
        if(closed || selection!=null)return;
        minimized=value;content.setVisibility(value?View.GONE:View.VISIBLE);logo.setVisibility(value?View.VISIBLE:View.GONE);
        panelParams.width=value?dp(48):expandedWidth();panelParams.height=value?dp(48):WindowManager.LayoutParams.WRAP_CONTENT;
        panelParams.alpha=value?.65f:1f;clampPosition();wm.updateViewLayout(panel,panelParams);
        scheduleHide();
    }
    private void clampPosition(){
        int width=panelParams.width,height=minimized?dp(48):panel.getHeight();
        panelParams.x=Math.max(0,Math.min(context.getResources().getDisplayMetrics().widthPixels-width,panelParams.x));
        panelParams.y=Math.max(0,Math.min(context.getResources().getDisplayMetrics().heightPixels-height,panelParams.y));
    }
    private void installDrag(View view){
        view.setOnTouchListener(new View.OnTouchListener(){float x,y;int px,py;boolean moved;
            public boolean onTouch(View v,MotionEvent e){
                switch(e.getActionMasked()){
                    case MotionEvent.ACTION_DOWN:x=e.getRawX();y=e.getRawY();px=panelParams.x;py=panelParams.y;moved=false;return true;
                    case MotionEvent.ACTION_MOVE:
                        float dx=e.getRawX()-x,dy=e.getRawY()-y;moved|=Math.hypot(dx,dy)>ViewConfiguration.get(context).getScaledTouchSlop();
                        if(moved){panelParams.x=px+(int)dx;panelParams.y=py+(int)dy;clampPosition();wm.updateViewLayout(panel,panelParams);}return true;
                    case MotionEvent.ACTION_UP:if(!moved)v.performClick();return true;
                    case MotionEvent.ACTION_CANCEL:return true;
                }return false;
            }
        });
    }
    private int dp(int n){return (int)(n*context.getResources().getDisplayMetrics().density);}
    private WindowManager.LayoutParams params(int width,int height,boolean passive){WindowManager.LayoutParams p=new WindowManager.LayoutParams(width,height,WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE|WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN|(passive?WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE:0),PixelFormat.TRANSLUCENT);p.gravity=Gravity.TOP|Gravity.LEFT;p.layoutInDisplayCutoutMode=WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS;if(passive)p.alpha=.75f;return p;}
    void message(String s){if(!closed)status.setText(s);}
    void profile(String s){if(!closed && profileButton!=null)profileButton.setText(s);}
    void metrics(String s){if(!closed)metrics.setText(s);}
    void hideMove(){markers.move=null;markers.invalidate();}
    void move(Rect box,String move,boolean whiteBottom){markers.box=new Rect(box);markers.move=move;markers.whiteBottom=whiteBottom;markers.invalidate();}
    Rect panelBounds(){if(closed || panel.getVisibility()!=View.VISIBLE)return new Rect();int[] xy=new int[2];panel.getLocationOnScreen(xy);return new Rect(xy[0],xy[1],xy[0]+panel.getWidth(),xy[1]+panel.getHeight());}
    void select(Consumer<Rect> result){
        if(selection!=null || closed)return;handler.removeCallbacks(hideTask);hideMove();panel.setVisibility(View.GONE);
        selection=new Selection(context,box->{wm.removeView(selection);selection=null;panel.setVisibility(View.VISIBLE);scheduleHide();result.accept(box);});
        wm.addView(selection,params(-1,-1,false));
    }
    void close(){closed=true;handler.removeCallbacks(hideTask);if(selection!=null)wm.removeView(selection);wm.removeView(panel);wm.removeView(markers);}
    static final class Markers extends View {
        final Paint paint=new Paint(3);Rect box;String move;boolean whiteBottom;
        Markers(Context c){super(c);}
        protected void onDraw(Canvas canvas){if(move==null || box==null)return;int[] origin=new int[2];getLocationOnScreen(origin);paint.setColor(Color.rgb(15,160,175));paint.setStrokeWidth(3);
            for(int i=0;i<2;i++){int square=Board.square(move.substring(i*2,i*2+2)),r=whiteBottom?7-square/8:square/8,c=whiteBottom?square%8:7-square%8;float x=box.left+(c+.87f)*box.width()/8-origin[0],y=box.top+(r+.13f)*box.height()/8-origin[1];paint.setStyle(i==0?Paint.Style.STROKE:Paint.Style.FILL);canvas.drawCircle(x,y,Math.max(5,box.width()/120f),paint);}
        }
    }
    static final class Selection extends View {
        final Paint paint=new Paint(3);final Consumer<Rect> done;float x,y,ex,ey;boolean started;
        Selection(Context c,Consumer<Rect> done){super(c);this.done=done;}
        public boolean onTouchEvent(MotionEvent e){if(e.getAction()==0){x=ex=e.getRawX();y=ey=e.getRawY();started=true;}else if(e.getAction()==2){ex=e.getRawX();ey=e.getRawY();}else if(e.getAction()==1){ex=e.getRawX();ey=e.getRawY();Rect r=new Rect((int)Math.min(x,ex),(int)Math.min(y,ey),(int)Math.max(x,ex),(int)Math.max(y,ey));done.accept(r.width()>=160 && r.height()>=160 && Math.abs(r.width()-r.height())<r.width()*.1?r:null);}invalidate();return true;}
        protected void onDraw(Canvas canvas){canvas.drawColor(0x66334455);paint.setColor(Color.WHITE);paint.setTextSize(18*getResources().getDisplayMetrics().scaledDensity);paint.setStyle(Paint.Style.FILL);canvas.drawText("Tarik dari sudut papan ke sudut seberangnya",20,80,paint);if(started){int[] o=new int[2];getLocationOnScreen(o);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(4);canvas.drawRect(Math.min(x,ex)-o[0],Math.min(y,ey)-o[1],Math.max(x,ex)-o[0],Math.max(y,ey)-o[1],paint);}}
    }
}
