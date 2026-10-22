package id.chesslab.coach;

import java.util.*;

/** Legal move tracker. Square indices: a1=0, h8=63. No UI dependencies. */
public final class Board {
    public static final String START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    public char[] cells = new char[64];
    public boolean white;
    public String rights;
    public int ep, half, full;
    public Board(String fen) {
        Arrays.fill(cells, '.');
        String[] parts = fen.trim().split("\\s+");
        if (parts.length != 6) throw new IllegalArgumentException("FEN harus lengkap (6 bagian)");
        String[] rows = parts[0].split("/");
        if (rows.length != 8) throw new IllegalArgumentException("FEN harus 8 baris");
        for (int r=0;r<8;r++) {
            int f=0;
            for (char p: rows[r].toCharArray()) {
                if (p >= '1' && p <= '8') f += p-'0';
                else { if (f>=8 || "prnbqkPRNBQK".indexOf(p)<0) throw new IllegalArgumentException("Bidak FEN salah"); cells[(7-r)*8+f++]=p; }
            }
            if (f!=8) throw new IllegalArgumentException("Jumlah petak FEN salah");
        }
        if (!parts[1].equals("w") && !parts[1].equals("b")) throw new IllegalArgumentException("Giliran FEN salah");
        white=parts[1].equals("w"); rights=parts[2].equals("-")?"":parts[2];
        if (!rights.matches("K?Q?k?q?")) throw new IllegalArgumentException("Hak rokade salah");
        ep=parts[3].equals("-")?-1:square(parts[3]);
        half=Integer.parseInt(parts[4]); full=Integer.parseInt(parts[5]);
        if (half<0 || full<1 || count('K')!=1 || count('k')!=1) throw new IllegalArgumentException("FEN tidak valid");
        if (ep>=0 && ep/8!=(white?5:2)) throw new IllegalArgumentException("En passant tidak valid");
        if (inCheck(!white)) throw new IllegalArgumentException("Posisi FEN tidak legal: raja lawan skak");
        for(int i=0;i<8;i++) if(Character.toLowerCase(cells[i])=='p' || Character.toLowerCase(cells[i+56])=='p') throw new IllegalArgumentException("Pion di baris promosi");
    }
    private Board(Board b) { cells=b.cells.clone(); white=b.white; rights=b.rights; ep=b.ep; half=b.half; full=b.full; }
    public Board copy() { return new Board(this); }
    int count(char p) { int n=0; for(char c:cells) if(c==p)n++; return n; }
    public static int square(String s) {
        if(s.length()!=2 || s.charAt(0)<'a' || s.charAt(0)>'h' || s.charAt(1)<'1' || s.charAt(1)>'8') throw new IllegalArgumentException("Petak tidak valid");
        return (s.charAt(1)-'1')*8+s.charAt(0)-'a';
    }
    public static String name(int i) { return ""+(char)('a'+i%8)+(char)('1'+i/8); }
    public String placement() {
        StringBuilder s=new StringBuilder();
        for(int r=7;r>=0;r--) { int n=0; for(int f=0;f<8;f++) { char p=cells[r*8+f]; if(p=='.')n++; else {if(n>0)s.append(n); n=0; s.append(p);} } if(n>0)s.append(n); if(r>0)s.append('/'); }
        return s.toString();
    }
    public String fen() { return placement()+" "+(white?"w":"b")+" "+(rights.isEmpty()?"-":rights)+" "+(ep<0?"-":name(ep))+" "+half+" "+full; }
    public boolean attacked(int sq, boolean byWhite) {
        int x=sq%8,y=sq/8;
        for(int from=0;from<64;from++) {
            char p=cells[from]; if(p=='.' || Character.isUpperCase(p)!=byWhite)continue;
            int dx=x-from%8,dy=y-from/8,ax=Math.abs(dx),ay=Math.abs(dy);
            switch(Character.toLowerCase(p)) {
                case 'p': if(ax==1 && dy==(byWhite?1:-1))return true; break;
                case 'n': if(ax*ay==2)return true; break;
                case 'k': if(Math.max(ax,ay)==1)return true; break;
                default:
                    char kind=Character.toLowerCase(p);
                    boolean line=(ax==ay && ax>0 && kind!='r') || ((dx==0 ^ dy==0) && kind!='b');
                    if(!line)break;
                    int sx=Integer.signum(dx),sy=Integer.signum(dy),fx=from%8+sx,fy=from/8+sy;
                    while(fx!=x || fy!=y) {if(cells[fy*8+fx]!='.')break;fx+=sx;fy+=sy;}
                    if(fx==x && fy==y)return true;
            }
        }
        return false;
    }
    public boolean inCheck(boolean side) { for(int i=0;i<64;i++) if(cells[i]==(side?'K':'k'))return attacked(i,!side); return true; }
    public List<String> legalMoves() {
        List<String> moves=new ArrayList<>();
        for(int from=0;from<64;from++) {
            char p=cells[from]; if(p=='.' || Character.isUpperCase(p)!=white)continue;
            for(int to=0;to<64;to++) {
                char target=cells[to]; if(from==to || target!='.' && (Character.isUpperCase(target)==white || Character.toLowerCase(target)=='k'))continue;
                int dx=to%8-from%8,dy=to/8-from/8,ax=Math.abs(dx),ay=Math.abs(dy),direction=white?1:-1;
                char kind=Character.toLowerCase(p); boolean valid=false;
                switch(kind) {
                    case 'p':
                        valid=dx==0 && target=='.' && (dy==direction || dy==2*direction && from/8==(white?1:6) && cells[from+8*direction]=='.');
                        valid |= ax==1 && dy==direction && (target!='.' || to==ep && cells[to-8*direction]==(white?'p':'P'));
                        break;
                    case 'n':valid=ax*ay==2;break;
                    case 'k':
                        valid=Math.max(ax,ay)==1;
                        if(dy==0 && ax==2 && from==(white?4:60) && !inCheck(white)) {
                            boolean king=dx>0; int rook=white?(king?7:0):(king?63:56);
                            char right=white?(king?'K':'Q'):(king?'k':'q');
                            valid=rights.indexOf(right)>=0 && cells[rook]==(white?'R':'r');
                            for(int i=from+Integer.signum(dx);i!=rook;i+=Integer.signum(dx)) if(cells[i]!='.')valid=false;
                            if(attacked(from+Integer.signum(dx),!white))valid=false;
                        }break;
                    default:
                        valid=(ax==ay && kind!='r') || ((dx==0 ^ dy==0) && kind!='b');
                        if(valid) for(int f=from%8+Integer.signum(dx),r=from/8+Integer.signum(dy);f!=to%8 || r!=to/8;f+=Integer.signum(dx),r+=Integer.signum(dy)) if(cells[r*8+f]!='.'){valid=false;break;}
                }
                if(!valid)continue;
                String base=name(from)+name(to);
                String promotions=kind=='p' && (to/8==0 || to/8==7)?"qrbn":" ";
                for(char promote:promotions.toCharArray()) {String move=base+(promote==' '?"":promote); Board next=play(move); if(!next.inCheck(white))moves.add(move);}
            }
        }
        return moves;
    }
    /** Apply a move already validated by legalMoves. */
    public Board play(String move) {
        Board b=copy(); int from=square(move.substring(0,2)),to=square(move.substring(2,4)); char p=cells[from];
        b.half=Character.toLowerCase(p)=='p' || cells[to]!='.'?0:half+1; b.ep=-1;
        b.cells[from]='.'; b.cells[to]=move.length()==5?(white?Character.toUpperCase(move.charAt(4)):move.charAt(4)):p;
        if(Character.toLowerCase(p)=='p') {if(to==ep && cells[to]=='.')b.cells[to+(white?-8:8)]='.'; if(Math.abs(to-from)==16)b.ep=(from+to)/2;}
        if(Character.toLowerCase(p)=='k') {
            b.rights=b.rights.replace(white?"K":"k","").replace(white?"Q":"q","");
            if(Math.abs(to-from)==2) {int rook=to>from?from+3:from-4; b.cells[(from+to)/2]=cells[rook];b.cells[rook]='.';}
        }
        int[] corners={0,7,56,63};String rs="QKqk";
        for(int i=0;i<4;i++)if(from==corners[i] || to==corners[i])b.rights=b.rights.replace(""+rs.charAt(i),"");
        b.white=!white;if(!white)b.full++;return b;
    }
    public static Board reconcile(Board current, String placement) {
        if(current.placement().equals(placement))return current;
        List<Board> next=new ArrayList<>();
        for(String m:current.legalMoves()) { Board b=current.play(m); if(b.placement().equals(placement))return b; next.add(b); }
        Board found=null;
        for(Board b:next)for(String m:b.legalMoves()) {Board c=b.play(m);if(c.placement().equals(placement)) {if(found!=null && !found.fen().equals(c.fen()))return null;found=c;}}
        return found;
    }
}
