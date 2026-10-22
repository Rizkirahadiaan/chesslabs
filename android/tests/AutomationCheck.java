import id.chesslab.coach.*;

public class AutomationCheck {
    private static int checks;
    private static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);checks++;}
    private static AutoTracker.Result frames(AutoTracker tracker,String placement,int count){AutoTracker.Result r=null;for(int i=0;i<count;i++)r=tracker.observe(placement);return r;}
    private static Board moves(String... moves){Board b=new Board(Board.START);for(String m:moves){check(b.legalMoves().contains(m),"Fixture move "+m);b=b.play(m);}return b;}
    private static AutoTracker automatic(){return new AutoTracker(new Board(Board.START),true,true,"Auto",true);}
    public static void main(String[] args){
        AutoTracker tracker=automatic();String start=new Board(Board.START).placement();
        check(!tracker.observe(start).ready(),"One frame must not show advice");
        check(tracker.observe(start).ready(),"Initial position should sync");
        Board e4e6=moves("e2e4","e7e6");
        check(frames(tracker,e4e6.placement(),2).board.fen().equals(e4e6.fen()),"Follow two plies including metadata");
        check(frames(tracker,AutoTracker.flip(e4e6.placement()),2).ready() && !tracker.whiteBottom,"Auto flip");
        check(tracker.board.fen().equals(e4e6.fen()),"Flipping must preserve rights and turn");
        // The reader maps pixels using the tracker's current bottom side.
        tracker.unstable();check(!tracker.observe(AutoTracker.flip(e4e6.placement())).ready(),"Recovery needs stable frames");
        check(tracker.observe(AutoTracker.flip(e4e6.placement())).ready() && tracker.whiteBottom,"Return orientation");

        Board mid=moves("d2d4","d7d6","e2e4","g8f6","b1c3","e7e5");
        AutoTracker middle=automatic();
        check(!frames(middle,mid.placement(),3).ready(),"Unknown turn must wait");
        check(!frames(middle,mid.placement(),5).ready(),"Repeated image cannot invent turn");
        Board next=mid.play("g1f3");
        AutoTracker.Result joined=frames(middle,next.placement(),3);
        check(joined.ready() && joined.joined && !joined.board.white,"One observed move proves turn");
        check(joined.board.rights.isEmpty() && joined.board.ep==-1 && middle.partialHistory,"No invented castling or en passant");
        check(!frames(middle,start,2).ready(),"New game needs three frames");
        check(middle.observe(start).newGame && !middle.partialHistory,"Automatic new-game reset");
        check(middle.board.fen().equals(Board.START),"New-game metadata");

        AutoTracker explicit=new AutoTracker(new Board(Board.START),true,true,"Putih",false);
        check(frames(explicit,mid.placement(),3).ready() && explicit.board.white,"Explicit startup turn");
        AutoTracker exact=new AutoTracker(mid,true,false,"Auto",true);
        check(frames(exact,mid.placement(),2).board.fen().equals(mid.fen()),"Exact FEN preserves known rights and ep");
        Board unrelated=moves("e2e4","e7e6","d2d4","d7d5","b1c3","g8f6");
        check(!frames(exact,unrelated.placement(),3).ready(),"Synced tracker must not silently join an unrelated game");
        AutoTracker.Result opening=frames(exact,new Board(Board.START).play("e2e4").placement(),3);
        check(opening.ready() && opening.newGame && !opening.board.white,"New game after a white opening");

        AutoTracker reversible=automatic();frames(reversible,start,2);
        Board knights=moves("g1f3","g8f6");frames(reversible,knights.placement(),2);
        Board returned=knights.play("f3g1").play("f6g8");
        AutoTracker.Result continued=frames(reversible,returned.placement(),2);
        check(continued.ready() && !continued.newGame && continued.board.full==3,"Legal return to start is not a new game");

        String ending="8/8/8/3k4/8/8/8/4K2R";
        check(!frames(automatic(),ending,3).ready(),"Ambiguous endgame orientation must wait");
        AutoTracker manual=new AutoTracker(new Board(Board.START),true,true,"Putih",false);
        check(frames(manual,ending,3).ready(),"Explicit endgame orientation and turn");
        AutoTracker rotated=automatic();check(!frames(rotated,AutoTracker.flip(mid.placement()),3).ready(),"Rotated midgame also waits for turn");
        check(frames(rotated,AutoTracker.flip(next.placement()),3).ready() && !rotated.whiteBottom,"Join rotated midgame");

        AutoTracker.RecoveryGate gate=new AutoTracker.RecoveryGate();
        check(!gate.shouldScan(0,false,-3000) && !gate.shouldScan(900,false,-3000),"Wait out animations");
        check(gate.shouldScan(1000,false,-3000),"Persistent failure triggers scan");
        check(!gate.shouldScan(2000,false,1000) && gate.shouldScan(4000,false,1000),"Rate limit recovery scans");
        check(!gate.shouldScan(4100,true,4000) && !gate.shouldScan(5000,false,4000),"Valid frame resets recovery delay");
        for(String name:new String[]{"Cepat","Seimbang","Mendalam"}){
            Timing t=Timing.forName(name);check(t.pollMillis==(name.equals("Cepat")?80:name.equals("Seimbang")?120:180),"PC polling profile");
            check(t.thinkMillis==(name.equals("Cepat")?180:name.equals("Seimbang")?450:1200),"PC engine profile");
        }
        System.out.println(checks+" automation assertions passed");
    }
}
