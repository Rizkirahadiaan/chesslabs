package id.chesslab.coach;

/** The same polling and thinking budgets as the PC response profiles. */
public final class Timing {
    public final String name;public final int pollMillis,thinkMillis;
    private Timing(String name,int poll,int think){this.name=name;pollMillis=poll;thinkMillis=think;}
    public static Timing forName(String name){
        if("Mendalam".equals(name))return new Timing(name,180,1200);
        if("Seimbang".equals(name))return new Timing(name,120,450);
        return new Timing("Cepat",80,180);
    }
    public Timing next(){return forName(name.equals("Cepat")?"Seimbang":name.equals("Seimbang")?"Mendalam":"Cepat");}
}
