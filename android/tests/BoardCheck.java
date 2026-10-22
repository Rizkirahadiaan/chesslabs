import id.chesslab.coach.Board;
import java.io.*;
import java.util.*;
public final class BoardCheck {
    static long perft(Board b,int depth){if(depth==0)return 1;long n=0;for(String m:b.legalMoves())n+=perft(b.play(m),depth-1);return n;}
    public static void main(String[] args)throws Exception {
        if(args.length>0 && args[0].equals("perft")){
            long[] expected={1,20,400,8902,197281};
            for(int d=1;d<=4;d++){long actual=perft(new Board(Board.START),d);if(actual!=expected[d])throw new AssertionError("perft "+d+": "+actual);System.out.println("perft "+d+" = "+actual);}
            return;
        }
        BufferedReader in=new BufferedReader(new InputStreamReader(System.in));String fen;
        while((fen=in.readLine())!=null){Board b=new Board(fen);List<String> moves=b.legalMoves();Collections.sort(moves);System.out.println(String.join(" ",moves));}
    }
}
