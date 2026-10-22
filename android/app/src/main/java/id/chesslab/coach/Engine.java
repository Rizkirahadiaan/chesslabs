package id.chesslab.coach;

import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.BooleanSupplier;

/** One serialized UCI session; callers run this off the main/capture threads. */
public final class Engine implements AutoCloseable {
    public static final String[] LEVELS={"Maksimal","Human","Menengah","Pemula","Blunder 15%"};
    private final Process process;private final BufferedWriter input;
    private final BlockingQueue<String> output=new LinkedBlockingQueue<>();
    private final Random random=new Random();
    public static final class Advice {
        public String move,line="",score="";public int depth,cp,mate;public boolean isMate;public long milliseconds;
    }
    public Engine(String executable)throws Exception {
        process=new ProcessBuilder(executable).redirectErrorStream(true).start();
        input=new BufferedWriter(new OutputStreamWriter(process.getOutputStream()));
        Thread reader=new Thread(()->{try(BufferedReader r=new BufferedReader(new InputStreamReader(process.getInputStream()))){String line;while((line=r.readLine())!=null)output.offer(line);}catch(IOException ignored){}finally{output.offer("ENGINE_EXIT");}},"uci-output");reader.setDaemon(true);reader.start();
        try {send("uci");waitFor("uciok",10000);send("setoption name Threads value 2");send("setoption name Hash value 64");send("isready");waitFor("readyok",10000);}catch(Exception e){close();throw e;}
    }
    private synchronized void send(String command)throws IOException {input.write(command);input.newLine();input.flush();}
    private String read(long deadline)throws Exception {long remaining=deadline-System.currentTimeMillis();String line=remaining<=0?null:output.poll(remaining,TimeUnit.MILLISECONDS);if(line==null)throw new IOException("Stockfish tidak merespons");if(line.equals("ENGINE_EXIT"))throw new IOException("Stockfish berhenti");return line;}
    private void waitFor(String word,long milliseconds)throws Exception {long deadline=System.currentTimeMillis()+milliseconds;while(!read(deadline).equals(word)){} }
    public Advice analyse(Board board,String level,int milliseconds)throws Exception {
        return analyse(board,level,milliseconds,()->false);
    }
    public Advice analyse(Board board,String level,int milliseconds,BooleanSupplier cancelled)throws Exception {
        if(cancelled.getAsBoolean())return null;
        long started=System.nanoTime();
        List<String> legal=board.legalMoves();if(legal.isEmpty())return null;
        boolean human=level.equals("Human"),blunder=level.equals("Blunder 15%") && random.nextDouble()<.15;
        int skill=level.equals("Menengah")?10:level.equals("Pemula")?0:20;
        int count=human?Math.min(5,legal.size()):blunder?legal.size():1;
        send("setoption name Skill Level value "+skill);send("setoption name UCI_LimitStrength value false");send("setoption name MultiPV value "+count);
        send("position fen "+board.fen());send("go movetime "+milliseconds);
        long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(milliseconds+10000);
        boolean stopping=false;
        Map<Integer,Advice> candidates=new HashMap<>();String bestMove;
        while(true) {
            if(cancelled.getAsBoolean() && !stopping){send("stop");stopping=true;}
            String line=output.poll(30,TimeUnit.MILLISECONDS);
            if(line==null){if(System.nanoTime()>deadline)throw new IOException("Stockfish tidak merespons");continue;}
            if(line.equals("ENGINE_EXIT"))throw new IOException("Stockfish berhenti");
            if(line.startsWith("bestmove ")){bestMove=line.split(" ")[1];break;}
            if(!line.startsWith("info ") || !line.contains(" pv ") || !line.contains(" score ") || line.contains("bound"))continue;
            String[] parts=line.split(" +");Advice a=new Advice();int rank=1;
            try {for(int i=1;i<parts.length;i++) {
                if(parts[i].equals("depth"))a.depth=Integer.parseInt(parts[++i]);
                else if(parts[i].equals("multipv"))rank=Integer.parseInt(parts[++i]);
                else if(parts[i].equals("score")){a.isMate=parts[++i].equals("mate");int value=Integer.parseInt(parts[++i]);if(a.isMate)a.mate=value;else a.cp=value;}
                else if(parts[i].equals("pv")){a.move=parts[++i];a.line=String.join(" ",Arrays.copyOfRange(parts,i,Math.min(i+6,parts.length)));break;}
            }}catch(RuntimeException malformed){continue;}
            if(legal.contains(a.move)) {a.score=a.isMate?"Mat "+a.mate:String.format(Locale.US,"%+.2f",a.cp/100.0);candidates.put(rank,a);}
        }
        if(stopping || cancelled.getAsBoolean())return null;
        if(!legal.contains(bestMove))throw new IOException("Stockfish mengembalikan langkah tidak legal");
        Advice best=candidates.values().stream().filter(a->a.move.equals(bestMove)).findFirst().orElse(null);
        if(best==null){best=new Advice();best.move=bestMove;best.line=bestMove;}
        best.milliseconds=TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-started);
        for(Advice a:candidates.values())a.milliseconds=best.milliseconds;
        if(!human && !blunder)return best;
        List<Advice> ranked=new ArrayList<>(candidates.values());ranked.sort((a,b)->Integer.compare(value(b),value(a)));
        if(ranked.isEmpty())return best;
        Advice top=ranked.get(0);if(top.isMate)return top;
        List<Advice> eligible=new ArrayList<>();List<Double> weights=new ArrayList<>();double total=0;
        int pieces=0;for(char p:board.cells)if(p!='.')pieces++;
        int tolerance=board.inCheck(board.white) || pieces<=10?15:35;
        for(Advice a:ranked) {
            int loss=top.cp-a.cp;
            if(a.isMate || (blunder?loss<150:loss>tolerance))continue;
            double w=blunder?1:Math.exp(-loss/18.0+natural(board,a.move)/6.0);
            eligible.add(a);weights.add(w);total+=w;
        }
        if(eligible.isEmpty())return top;
        double roll=random.nextDouble()*total;
        for(int i=0;i<eligible.size();i++){roll-=weights.get(i);if(roll<=0)return eligible.get(i);}
        return eligible.get(eligible.size()-1);
    }
    private static int value(Advice a){return a.isMate?(a.mate>0?100000-a.mate:-100000-a.mate):a.cp;}
    private static int natural(Board b,String move) {
        int from=Board.square(move.substring(0,2)),to=Board.square(move.substring(2,4)),score=0;char p=Character.toLowerCase(b.cells[from]);
        if(p=='k' && Math.abs(to-from)==2)score+=8;
        if((p=='n' || p=='b') && from/8==(b.white?0:7))score+=5;
        if((to%8==3 || to%8==4) && (to/8==3 || to/8==4))score+=2;
        if(b.cells[to]!='.')score+=2;
        if(p=='q' && b.full<=10)score-=4;
        return score;
    }
    public void close(){try{send("quit");}catch(IOException ignored){}process.destroy();}
}
