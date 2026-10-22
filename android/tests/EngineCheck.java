import id.chesslab.coach.*;
public class EngineCheck {
    public static void main(String[] args)throws Exception {
        try(Engine engine=new Engine(args[0])){
            for(String level:Engine.LEVELS){Board b=new Board(Board.START);Engine.Advice a=engine.analyse(b,level,180);if(!b.legalMoves().contains(a.move))throw new AssertionError(level);if(level.equals("Human") && a.milliseconds>=500)throw new AssertionError("Human budget still multiplied: "+a.milliseconds);System.out.println(level+": "+a.move+" "+a.score+" / "+a.milliseconds+" ms");}
            Board b=new Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1");Engine.Advice a=engine.analyse(b,"Human",180);if(!b.play(a.move).legalMoves().isEmpty() || !b.play(a.move).inCheck(false))throw new AssertionError("Lost forced mate");System.out.println("Human preserves mate: "+a.move);
            java.util.concurrent.atomic.AtomicBoolean cancelled=new java.util.concurrent.atomic.AtomicBoolean();
            java.util.concurrent.ScheduledExecutorService timer=java.util.concurrent.Executors.newSingleThreadScheduledExecutor();
            try{
                timer.schedule(()->cancelled.set(true),100,java.util.concurrent.TimeUnit.MILLISECONDS);
                long started=System.nanoTime();a=engine.analyse(new Board(Board.START),"Human",2000,cancelled::get);
                long elapsed=(System.nanoTime()-started)/1000000;
                if(a!=null || elapsed>1000)throw new AssertionError("Stale search was not cancelled promptly: "+elapsed);
                Board next=new Board(Board.START).play("e2e4");a=engine.analyse(next,"Maksimal",180);
                if(a==null || !next.legalMoves().contains(a.move))throw new AssertionError("UCI stream not drained after cancellation");
                System.out.println("Stale search cancelled in "+elapsed+" ms; next position analysed successfully");
            }finally{timer.shutdownNow();}
        }
    }
}
