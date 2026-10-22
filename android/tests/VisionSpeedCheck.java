import id.chesslab.coach.*;
import android.graphics.*;
import java.io.*;
import java.util.*;

public class VisionSpeedCheck {
    private static double median(double[] values){Arrays.sort(values);return values[values.length/2];}
    public static void main(String[] args)throws Exception {
        String dir=args[0];Rect area=new Rect(0,464,738,1202);
        Bitmap start=Bitmap.load(dir+"/coords-False-start.png"),move=Bitmap.load(dir+"/coords-False-0.png"),latest=Bitmap.load(dir+"/coords-False-5.png");
        Vision.Theme theme=Vision.Theme.train(start,area,true);Vision.Reader reader=new Vision.Reader();
        if(reader.read(start,area,theme,true).placement==null || reader.classifiedTiles!=64)throw new AssertionError("Cold read");
        for(int i=0;i<6;i++)reader.read(start,area,theme,true);
        double[] unchanged=new double[31],changed=new double[21],full=new double[11];
        for(int i=0;i<unchanged.length;i++){
            long before=System.nanoTime();reader.read(start,area,theme,true);unchanged[i]=(System.nanoTime()-before)/1e6;
            if(reader.classifiedTiles!=0)throw new AssertionError("Unchanged board was reclassified");
        }
        for(int i=0;i<changed.length;i++){
            Bitmap frame=i%2==0?move:start;long before=System.nanoTime();Vision.Observation result=reader.read(frame,area,theme,true);changed[i]=(System.nanoTime()-before)/1e6;
            if(reader.classifiedTiles!=2 || result.placement==null)throw new AssertionError("Sparse move should classify only two tiles: "+reader.classifiedTiles);
        }
        for(int i=0;i<full.length;i++){long before=System.nanoTime();Vision.read(start,area,theme,true);full[i]=(System.nanoTime()-before)/1e6;}
        String expected="rnbqkb1r/ppp2ppp/3p1n2/4p3/3PP3/2N5/PPP2PPP/R1BQKBNR";
        if(!expected.equals(reader.read(latest,area,theme,true).placement))throw new AssertionError("User position with b1 empty");
        Vision.Observation flipped=reader.read(latest,area,theme,false);
        if(reader.classifiedTiles!=0 || !AutoTracker.flip(expected).equals(flipped.placement))throw new AssertionError("Orientation mapping should reuse pixel cache");
        Vision.Theme other=Vision.Theme.train(start,area,true);reader.read(start,area,other,true);
        if(reader.classifiedTiles!=64)throw new AssertionError("Theme change must invalidate cache");
        reader.read(start,new Rect(0,465,738,1203),other,true);
        if(reader.classifiedTiles!=64)throw new AssertionError("Area change must invalidate cache");
        File legacy=new File(dir,"legacy-theme.bin");
        if(legacy.exists() && !expected.equals(Vision.read(latest,area,Vision.Theme.load(legacy),true).placement))throw new AssertionError("Legacy theme migration");
        double stableMs=median(unchanged),changedMs=median(changed),fullMs=median(full);
        System.out.printf(Locale.US,"Vision median: full %.2f ms, unchanged %.2f ms, two tiles %.2f ms%n",fullMs,stableMs,changedMs);
        try(PrintWriter report=new PrintWriter(new File(dir,"performance.json"))){
            report.printf(Locale.US,"{\"full_ms\":%.4f,\"unchanged_ms\":%.4f,\"two_tiles_ms\":%.4f,\"unchanged_classified_tiles\":0,\"changed_classified_tiles\":2,\"legacy_theme_checked\":%s}%n",fullMs,stableMs,changedMs,legacy.exists());
        }
    }
}
