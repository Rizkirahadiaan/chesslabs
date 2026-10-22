import id.chesslab.coach.*;
import android.graphics.*;
import java.io.*;
public class VisionCheck {
    private static int checked,failures;
    private static void checkCases(String dir,String filename,Rect box,Vision.Theme theme)throws Exception {
        try(BufferedReader r=new BufferedReader(new FileReader(dir+"/"+filename))){String line;
            while((line=r.readLine())!=null){String[] parts=line.split(" ");Vision.Observation o=Vision.read(Bitmap.load(dir+"/"+parts[0]),box,theme,parts[1].equals("white"));
                if(!parts[2].equals(o.placement)){System.out.println("FAIL "+parts[0]+" "+o.placement+" confidence="+o.confidence+" "+o.guidance());failures++;}checked++;
            }
        }
    }
    public static void main(String[] args)throws Exception {
        Rect box=new Rect(40,260,680,900);
        Bitmap start=Bitmap.load(args[0]+"/start.png");
        Vision.Theme theme=Vision.Theme.train(start,box,true);
        File saved=new File(args[0],"theme.bin");theme.save(saved);theme=Vision.Theme.load(saved);
        checkCases(args[0],"cases.txt",box,theme);
        try(BufferedReader r=new BufferedReader(new FileReader(args[0]+"/suites.txt"))){String line;
            while((line=r.readLine())!=null){String[] parts=line.split(" ");String[] coords=parts[2].split(",");Rect area=new Rect(Integer.parseInt(coords[0]),Integer.parseInt(coords[1]),Integer.parseInt(coords[2]),Integer.parseInt(coords[3]));
                Bitmap initial=Bitmap.load(args[0]+"/"+parts[0]+"-start.png");
                Vision.Theme mobile=Vision.Theme.train(initial,area,parts[1].equals("white"));
                checkCases(args[0],parts[0]+".txt",area,mobile);
                Rect mobileDetected=Vision.detect(initial);
                System.out.println(parts[0]+" detected="+mobileDetected+" expected="+area);
                if(mobileDetected==null || !new Board(Board.START).placement().equals(Vision.read(initial,mobileDetected,mobile,parts[1].equals("white")).placement)){
                    System.out.println("FAIL detected initial "+parts[0]);failures++;
                }
                checked++;
                if(mobileDetected!=null){
                    if(Math.abs(mobileDetected.left-area.left)>2 || Math.abs(mobileDetected.top-area.top)>2 || Math.abs(mobileDetected.right-area.right)>2 || Math.abs(mobileDetected.bottom-area.bottom)>2)
                        throw new AssertionError("Incorrect board bounds: "+mobileDetected+" expected="+area);
                    Vision.Theme autoTheme=Vision.Theme.train(initial,mobileDetected,parts[1].equals("white"));
                    checkCases(args[0],parts[0]+".txt",mobileDetected,autoTheme);
                }
                Bitmap moved=Bitmap.load(args[0]+"/"+parts[0]+"-1.png");
                Rect movedDetected=Vision.detect(moved);
                System.out.println(parts[0]+" moved detected="+movedDetected);
                if(movedDetected==null || !"rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR".equals(Vision.read(moved,movedDetected,mobile,parts[1].equals("white")).placement)){
                    System.out.println("FAIL detected e4 e6 "+parts[0]);failures++;
                }
                checked++;
                try{Vision.Theme.train(moved,area,parts[1].equals("white"));throw new AssertionError("Midgame theme accepted: "+parts[0]);}catch(IllegalArgumentException expected){}
                if(parts[0].equals("mobile-738-False")){
                    Vision.Observation bad=Vision.read(Bitmap.load(args[0]+"/obscured-e6.png"),area,mobile,true);
                    if(bad.placement!=null || !"e6".equals(bad.uncertainSquare) || bad.uncertainSquares!=1 || !bad.guidance().contains("e6"))
                        throw new AssertionError("Missing per-square diagnostic: "+bad.guidance());
                }
            }
        }
        for(boolean flipped:new boolean[]{false,true}){
            String prefix="coords-"+(flipped?"True":"False");Rect area=new Rect(0,464,738,1202);
            Bitmap initial=Bitmap.load(args[0]+"/"+prefix+"-start.png");
            Boolean bottom=Vision.initialWhiteBottom(initial,area);
            if(bottom==null || bottom==flipped)throw new AssertionError("Initial colour detection failed: "+prefix);
            checkCases(args[0],prefix+".txt",area,Vision.Theme.train(initial,area,!flipped));
        }
        Rect detected=Vision.detect(start);
        if(detected==null)throw new AssertionError("Board not detected");
        System.out.println("Detected board "+detected);
        Vision.Observation o=Vision.read(start,detected,theme,true);
        if(!new Board(Board.START).placement().equals(o.placement))throw new AssertionError("Detected area cannot be recognized");
        Bitmap blank=Bitmap.load(args[0]+"/blank.png");
        if(Vision.detect(blank)!=null)throw new AssertionError("Blank screen detected as board");
        try{Vision.Theme.train(blank,box,true);throw new AssertionError("Blank theme accepted");}catch(IllegalArgumentException expected){}
        System.out.println((checked-failures)+"/"+checked+" recognition checks passed");
        if(failures>0)throw new AssertionError(failures+" recognition regressions");
        try(PrintWriter report=new PrintWriter(new File(args[0],"checks.json"))){report.println("{\"recognition_checks\":"+checked+",\"failures\":"+failures+"}");}
    }
}
