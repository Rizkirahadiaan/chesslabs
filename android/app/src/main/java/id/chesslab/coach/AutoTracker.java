package id.chesslab.coach;

import java.util.*;

/** Android-independent counterparts of PC adaptive.py and midgame.py. */
public final class AutoTracker {
    public Board board;
    public boolean whiteBottom,synced,partialHistory;
    private final boolean allowJoin,autoOrientation;
    private final String startupTurn;
    private String lastPlacement;
    private int stable;
    private Result waiting;
    private List<Board> bootstrap=new ArrayList<>();
    private String bootstrapPlacement;
    public static final class Result {
        public final Board board;public final boolean newGame,joined;public final String message;
        Result(Board b,boolean reset,boolean join,String message){board=b;newGame=reset;joined=join;this.message=message;}
        public boolean ready(){return board!=null;}
    }
    public AutoTracker(Board seed,boolean bottom,boolean allowJoin,String turn,boolean autoOrientation){
        board=seed;whiteBottom=bottom;this.allowJoin=allowJoin;startupTurn=turn;this.autoOrientation=autoOrientation;
    }
    public void unstable(){lastPlacement=null;stable=0;waiting=null;}
    public Result observe(String placement){
        if(placement==null){unstable();return waitFor("Menunggu papan terbaca.");}
        if(!placement.equals(lastPlacement))waiting=null;
        stable=placement.equals(lastPlacement)?stable+1:1;lastPlacement=placement;
        if(stable>3 && waiting!=null)return waiting;
        if(stable<2)return waitFor("Menunggu posisi stabil…");
        String opposite=flip(placement),normal=placement;boolean bottom=whiteBottom;
        Board candidate=Board.reconcile(board,placement);boolean reset=false,joined=false;
        if(candidate==null){candidate=Board.reconcile(board,opposite);if(candidate!=null){normal=opposite;bottom=!bottom;}}
        if(candidate==null){
            candidate=opening(placement);
            if(candidate==null){candidate=opening(opposite);if(candidate!=null){normal=opposite;bottom=!bottom;}}
            reset=candidate!=null;
        }
        if(reset && stable<3)return waitFor("Memastikan partai baru…");
        if(candidate==null && !synced && allowJoin){
            if(stable<3)return waitFor("Membaca posisi sekarang…");
            if(autoOrientation){
                boolean a=!possible(placement,"Auto").isEmpty(),b=!possible(opposite,"Auto").isEmpty();
                int evidence=evidence(placement)-evidence(opposite);
                if(!a && !b)return waitFor("Susunan belum legal. Periksa Area atau tema.");
                if(a && b && Math.abs(evidence)<3)return waitFor("Orientasi belum pasti. Pilih sisi bawah di pengaturan.");
                if(!a || b && evidence<0){normal=opposite;bottom=!bottom;}
            }
            candidate=join(normal);joined=candidate!=null;
            if(candidate==null)return waitFor("Posisi terbaca. Tunggu satu langkah untuk mengetahui giliran, atau pilih Giliran awal.");
        }
        if(candidate==null)return waitFor("Posisi belum sinkron. Ketuk Baca kini atau masukkan FEN lengkap.");
        board=candidate;whiteBottom=bottom;synced=true;waiting=null;
        lastPlacement=normal;
        if(reset)partialHistory=false;
        if(joined)partialHistory=true;
        return new Result(board,reset,joined,reset?"Partai baru terdeteksi.":joined?"Posisi tersambung; hak rokade lama tidak diketahui.":"Posisi tersinkron.");
    }
    private Result waitFor(String message){Result result=new Result(null,false,false,message);if(stable>=3)waiting=result;return result;}
    private Board join(String placement){
        if("Auto".equals(startupTurn) && !placement.equals(bootstrapPlacement)){
            Map<String,Board> matches=new HashMap<>();
            for(Board previous:bootstrap)for(String move:previous.legalMoves()){
                Board trial=previous.play(move);if(trial.placement().equals(placement))matches.put(trial.fen(),trial);
            }
            if(matches.size()==1){bootstrap.clear();return matches.values().iterator().next();}
        }
        bootstrap=possible(placement,startupTurn);bootstrapPlacement=placement;
        return bootstrap.size()==1?bootstrap.get(0):null;
    }
    private static List<Board> possible(String placement,String turn){
        List<Board> boards=new ArrayList<>();
        for(boolean white:new boolean[]{true,false}){
            if(turn.equals("Putih") && !white || turn.equals("Hitam") && white)continue;
            try{
                Board b=new Board(placement+(white?" w":" b")+" - - 0 1");
                int wp=0,bp=0,w=0,k=0;for(char p:b.cells){if(p=='P')wp++;if(p=='p')bp++;if(p!='.'){if(Character.isUpperCase(p))w++;else k++;}}
                if(wp<=8 && bp<=8 && w<=16 && k<=16)boards.add(b);
            }catch(IllegalArgumentException ignored){}
        }
        return boards;
    }
    private static int evidence(String placement){
        int score=0;char[] cells=cells(placement);
        for(int s=0;s<64;s++)if(cells[s]=='P' && (s/8==1 || s/8==2) || cells[s]=='p' && (s/8==5 || s/8==6))score++;
        return score;
    }
    private static Board opening(String placement){
        Board start=new Board(Board.START);if(start.placement().equals(placement))return start;
        for(String move:start.legalMoves()){Board next=start.play(move);if(next.placement().equals(placement))return next;}
        return null;
    }
    private static char[] cells(String placement){
        char[] cells=new char[64];Arrays.fill(cells,'.');int row=7,col=0;
        for(char p:placement.toCharArray()){if(p=='/'){row--;col=0;}else if(p>='1' && p<='8')col+=p-'0';else cells[row*8+col++]=p;}
        return cells;
    }
    public static String flip(String placement){
        char[] source=cells(placement);Board b=new Board(Board.START);
        for(int s=0;s<64;s++)b.cells[63-s]=source[s];return b.placement();
    }
    public static final class RecoveryGate {
        private long failedSince=-1;
        public boolean shouldScan(long now,boolean valid,long lastScan){
            if(valid){failedSince=-1;return false;}
            if(failedSince<0)failedSince=now;
            return now-failedSince>=1000 && now-lastScan>=3000;
        }
        public void reset(){failedSince=-1;}
    }
}
