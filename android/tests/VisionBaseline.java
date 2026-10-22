import id.chesslab.coach.*;
import android.graphics.*;
import java.io.*;
import java.util.*;
/** Run against the saved 0.1.1 recognizer, in a separate JVM/classpath. */
public class VisionBaseline {
    public static void main(String[] args)throws Exception{
        Rect area=new Rect(0,464,738,1202);Bitmap start=Bitmap.load(args[0]+"/coords-False-start.png");
        Vision.Theme theme=Vision.Theme.train(start,area,true);theme.save(new File(args[0],"legacy-theme.bin"));
        for(int i=0;i<4;i++)Vision.read(start,area,theme,true);
        double[] times=new double[15];for(int i=0;i<times.length;i++){long t=System.nanoTime();Vision.read(start,area,theme,true);times[i]=(System.nanoTime()-t)/1e6;}
        Arrays.sort(times);Vision.Observation latest=Vision.read(Bitmap.load(args[0]+"/coords-False-5.png"),area,theme,true);
        System.out.printf(Locale.US,"0.1.1 full read median %.2f ms; current-position recognition: %s%n",times[times.length/2],latest.placement!=null);
        try(PrintWriter report=new PrintWriter(new File(args[0],"baseline.json"))){report.printf(Locale.US,"{\"full_ms\":%.4f,\"current_position_recognized\":%s}%n",times[times.length/2],latest.placement!=null);}
    }
}
