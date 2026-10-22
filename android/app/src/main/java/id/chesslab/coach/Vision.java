package id.chesslab.coach;

import android.graphics.*;
import java.io.*;
import java.util.*;

/** Local, theme-learned recognizer. Screen images never leave the device. */
public final class Vision {
    private static final int N=24;
    static final class Feature {
        float[] edges = new float[N*N]; float energy,tone;
        float pieceEnergy; // Training-only occupancy check; ignores coordinate labels at the edges.
        Feature(Bitmap tile) {
            Bitmap small=Bitmap.createScaledBitmap(tile,N,N,true);
            int[] pixels=new int[N*N];small.getPixels(pixels,0,N,0,0,N,N);
            if(small!=tile)small.recycle();
            float[] gray=new float[N*N];for(int i=0;i<gray.length;i++)gray[i]=(Color.red(pixels[i])*.299f+Color.green(pixels[i])*.587f+Color.blue(pixels[i])*.114f)/255;
            for(int y=3;y<N-3;y++)for(int x=3;x<N-3;x++) {
                if(!featurePixel(x,y))continue;
                int i=y*N+x;float gx=gray[i+1]-gray[i-1],gy=gray[i+N]-gray[i-N];
                edges[i]=(float)Math.sqrt(gx*gx+gy*gy);
            }
            for(int y=9;y<16;y++)for(int x=8;x<16;x++)tone+=gray[y*N+x]/56;
            normalize();
        }
        Feature(DataInputStream in)throws IOException {
            float norm=(float)Math.sqrt(in.readFloat());tone=in.readFloat();
            for(int i=0;i<edges.length;i++)edges[i]=in.readFloat()*norm;
            // Apply the same mask to old themes so an update does not require relearning.
            normalize();
        }
        private void normalize(){
            energy=pieceEnergy=0;
            for(int y=0;y<N;y++)for(int x=0;x<N;x++){
                int i=y*N+x;if(!featurePixel(x,y))edges[i]=0;
                energy+=edges[i]*edges[i];
                if(x>=6 && x<N-6 && y>=6 && y<N-4)pieceEnergy+=edges[i]*edges[i];
            }
            if(energy>0){float norm=(float)Math.sqrt(energy);for(int i=0;i<edges.length;i++)edges[i]/=norm;}
        }
        void write(DataOutputStream out)throws IOException {out.writeFloat(energy);out.writeFloat(tone);for(float v:edges)out.writeFloat(v);}
        float similarity(Feature other) {
            if(energy<.12f || other.energy<.12f)return energy<.12f && other.energy<.12f?1:0;
            float best=0;
            for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++) {
                float sum=0;for(int y=2;y<N-2;y++)for(int x=2;x<N-2;x++)sum+=edges[y*N+x]*other.edges[(y+dy)*N+x+dx];
                best=Math.max(best,sum);
            }
            return best*(1-Math.abs(tone-other.tone)*.75f);
        }
    }
    private static boolean featurePixel(int x,int y){
        // Match the PC mask: file letters, rank numbers and our markers are not pieces.
        return x>=3 && x<N-3 && y>=3 && y<N-4 && !(y<6 && (x<7 || x>=17)) && !(y<7 && x>=18);
    }
    public static final class Theme {
        final List<Feature> features=new ArrayList<>();final List<Character> labels=new ArrayList<>();
        public static Theme train(Bitmap screen,Rect box,boolean whiteBottom) {
            Theme theme=new Theme(); Board board=new Board(Board.START);
            for(int r=0;r<8;r++)for(int c=0;c<8;c++) {
                Bitmap tile=tile(screen,box,r,c);Feature feature=new Feature(tile);tile.recycle();
                char label=board.cells[index(r,c,whiteBottom)];
                // Check every square, not just one sample of each piece type. Otherwise
                // learning after e4/e6 silently labels moved pawns as empty squares.
                if((feature.pieceEnergy>=.12f)!=(label!='.'))
                    throw new IllegalArgumentException("Tema belum disimpan. Kembalikan semua bidak ke posisi AWAL; periksa Area.");
                theme.features.add(feature);theme.labels.add(label);
            }
            return theme;
        }
        public void save(File f)throws IOException {try(DataOutputStream out=new DataOutputStream(new FileOutputStream(f))) {out.writeInt(1);out.writeInt(features.size());for(int i=0;i<features.size();i++){out.writeChar(labels.get(i));features.get(i).write(out);}}}
        public static Theme load(File f)throws IOException {try(DataInputStream in=new DataInputStream(new FileInputStream(f))) {if(in.readInt()!=1)throw new IOException("Versi tema salah");int n=in.readInt();if(n!=64)throw new IOException("Tema tidak lengkap");Theme t=new Theme();for(int i=0;i<n;i++){t.labels.add(in.readChar());t.features.add(new Feature(in));}return t;}}
    }
    public static Boolean initialWhiteBottom(Bitmap screen,Rect box){
        float upper=0,lower=0;
        for(int c=0;c<8;c++){
            Bitmap a=tile(screen,box,1,c),b=tile(screen,box,6,c);
            upper+=new Feature(a).tone;lower+=new Feature(b).tone;a.recycle();b.recycle();
        }
        return Math.abs(lower-upper)<.64f?null:lower>upper;
    }
    public static final class Observation {
        public final String placement; public final float confidence; public final boolean whiteBottom;
        public final String uncertainSquare; public final int uncertainSquares;
        Observation(String p,float c,boolean w){this(p,c,w,null,0);}
        Observation(String p,float c,boolean w,String square,int count){placement=p;confidence=c;whiteBottom=w;uncertainSquare=square;uncertainSquares=count;}
        public String guidance(){
            if(placement!=null)return "Posisi terbaca.";
            if(uncertainSquares>8)return "Banyak petak belum terbaca. Periksa Area; pelajari tema dari posisi awal.";
            if(uncertainSquares>0)return "Petak "+uncertainSquare+" belum jelas"+(uncertainSquares>1?" ("+uncertainSquares+" petak)":"")+". Tunggu bidak diam; periksa Area.";
            return "Raja belum terbaca lengkap. Periksa Area atau pelajari ulang posisi awal.";
        }
    }
    public static int index(int row,int col,boolean whiteBottom){return whiteBottom?(7-row)*8+col:row*8+7-col;}
    private static Bitmap tile(Bitmap b,Rect box,int r,int c){int x=box.left+c*box.width()/8,y=box.top+r*box.height()/8;return Bitmap.createBitmap(b,x,y,box.left+(c+1)*box.width()/8-x,box.top+(r+1)*box.height()/8-y);}
    public static Observation read(Bitmap b,Rect box,Theme theme,boolean whiteBottom) {
        return new Reader().read(b,box,theme,whiteBottom);
    }
    private static final class Cell {
        final char symbol;final float score;final boolean certain;
        Cell(char s,float p,boolean valid){symbol=s;score=p;certain=valid;}
    }
    private static Cell classify(Feature f,Theme theme){
        // Flat centres and edge-masked empty squares need no template comparisons.
        if(f.pieceEnergy<.12f)return new Cell('.',1,true);
        String labels="PNBRQKpnbrqk";float[] scores=new float[12];Arrays.fill(scores,-1);
        for(int i=0;i<theme.features.size();i++){
            int label=labels.indexOf(theme.labels.get(i));if(label<0)continue;
            Feature other=theme.features.get(i);
            if(other.pieceEnergy<.12f || 1-Math.abs(f.tone-other.tone)*.75f<=scores[label])continue;
            scores[label]=Math.max(scores[label],f.similarity(other));
        }
        float best=-1,second=-1;char symbol='.';
        for(int i=0;i<scores.length;i++){float score=scores[i];if(score>best){second=best;best=score;symbol=labels.charAt(i);}else second=Math.max(second,score);}
        return new Cell(symbol,best,best>=.72f && best-second>=.035f);
    }
    /** Exact pixel comparison reuses all unchanged tiles, including uncertain results. */
    public static final class Reader {
        private Theme lastTheme;private Rect lastBox;private int[] previous,current;
        private final Cell[] cached=new Cell[64];
        public int classifiedTiles;
        public void clear(){lastTheme=null;lastBox=null;previous=current=null;Arrays.fill(cached,null);}
        public Observation read(Bitmap b,Rect box,Theme theme,boolean whiteBottom){
            int width=box.width(),height=box.height();
            if(theme!=lastTheme || lastBox==null || lastBox.left!=box.left || lastBox.top!=box.top || lastBox.right!=box.right || lastBox.bottom!=box.bottom){
                clear();lastTheme=theme;lastBox=new Rect(box);previous=new int[width*height];current=new int[width*height];
            }
            b.getPixels(current,0,width,box.left,box.top,width,height);classifiedTiles=0;
            boolean sameFrame=cached[0]!=null && Arrays.equals(current,previous);
            char[] cells=new char[64];float confidence=1;int uncertain=0;String firstUncertain=null;
            for(int r=0;r<8;r++)for(int c=0;c<8;c++){
                int cell=r*8+c;boolean same=cached[cell]!=null;
                for(int y=r*height/8;!sameFrame && same && y<(r+1)*height/8;y++)
                    for(int i=y*width+c*width/8,end=y*width+(c+1)*width/8;i<end;i++)if(current[i]!=previous[i]){same=false;break;}
                if(!same){Bitmap crop=tile(b,box,r,c);Feature feature=new Feature(crop);crop.recycle();cached[cell]=classify(feature,theme);classifiedTiles++;}
                Cell result=cached[cell];int square=index(r,c,whiteBottom);cells[square]=result.symbol;
                confidence=Math.min(confidence,result.score);
                if(!result.certain){uncertain++;if(firstUncertain==null)firstUncertain=Board.name(square);}
            }
            int[] swap=previous;previous=current;current=swap;
            if(uncertain>0)return new Observation(null,Math.max(0,confidence),whiteBottom,firstUncertain,uncertain);
            int wk=0,bk=0;for(char p:cells){if(p=='K')wk++;if(p=='k')bk++;}
            if(wk!=1 || bk!=1)return new Observation(null,confidence,whiteBottom);
            Board result=new Board(Board.START);result.cells=cells;
            return new Observation(result.placement(),confidence,whiteBottom);
        }
    }
    /** Search square/checker geometry without any hard-coded app or board colour. */
    public static Rect detect(Bitmap image) {
        Pixels pixels=new Pixels(image);
        int max=Math.min(image.getWidth(),image.getHeight());float best=0;Rect found=null;
        for(int size=max;size>=Math.max(160,max/2);size-=Math.max(8,max/50)) {
            int step=Math.max(8,size/24);
            for(int y=0;y+size<=image.getHeight();y+=step)for(int x=0;x+size<=image.getWidth();x+=step) {
                float score=gridScore(pixels,x,y,size);
                if(score>best){best=score;found=new Rect(x,y,x+size,y+size);}
            }
        }
        if(found==null || best<2.2f)return null;
        // Side samples can match up to half a tile away from the true edge.
        Rect coarse=new Rect(found);int range=Math.max(8,coarse.width()/12);best=0;
        for(int size=coarse.width()-range;size<=coarse.width()+range;size+=4)
            for(int y=Math.max(0,coarse.top-range);y<=coarse.top+range && y+size<=image.getHeight();y+=4)
                for(int x=Math.max(0,coarse.left-range);x<=coarse.left+range && x+size<=image.getWidth();x+=4) {
                    float score=boundaryScore(pixels,x,y,size,2,2);if(score>best){best=score;found=new Rect(x,y,x+size,y+size);}
                }
        Rect fine=new Rect(found);best=0;
        for(int size=fine.width()-4;size<=fine.width()+4;size++)
            for(int y=Math.max(0,fine.top-4);y<=fine.top+4 && y+size<=image.getHeight();y++)
                for(int x=Math.max(0,fine.left-4);x<=fine.left+4 && x+size<=image.getWidth();x++) {
                    float score=boundaryScore(pixels,x,y,size,1,0);if(score>best){best=score;found=new Rect(x,y,x+size,y+size);}
                }
        return found;
    }
    // Copy once so all search samples read memory instead of repeatedly calling Bitmap.getPixel.
    private static final class Pixels {
        final int width;final int[] data;
        Pixels(Bitmap bitmap){width=bitmap.getWidth();int height=bitmap.getHeight();data=new int[width*height];bitmap.getPixels(data,0,width,0,0,width,height);}
        int getPixel(int x,int y){return data[y*width+x];}
    }
    private static float boundaryScore(Pixels b,int x,int y,int size,int before,int after) {
        float sum=0;
        for(int line=1;line<8;line++)for(int cell=0;cell<8;cell++) {
            int edge=line*size/8,along=(int)((cell+.24)*size/8);
            // Adjacent pixels avoid the four-pixel score plateau that shrank boards.
            int a=b.getPixel(x+edge-before,y+along),c=b.getPixel(x+edge+after,y+along);
            sum+=distance(a,c);
            a=b.getPixel(x+along,y+edge-before);c=b.getPixel(x+along,y+edge+after);
            sum+=distance(a,c);
        }
        return sum/(112*20);
    }
    private static float distance(int a,int b){int r=Color.red(a)-Color.red(b),g=Color.green(a)-Color.green(b),bl=Color.blue(a)-Color.blue(b);return (float)Math.sqrt(r*r+g*g+bl*bl);}
    private static float gridScore(Pixels b,int x,int y,int size) {
        // Rank labels and tall pieces contaminated the old single top-left sample.
        return Math.max(gridScoreAt(b,x,y,size,.08f,.5f),
            Math.max(gridScoreAt(b,x,y,size,.92f,.5f),gridScoreAt(b,x,y,size,.5f,.08f)));
    }
    private static float gridScoreAt(Pixels b,int x,int y,int size,float sx,float sy) {
        float[][] sums=new float[2][3];float[] squares=new float[2];
        for(int r=0;r<8;r++)for(int c=0;c<8;c++) {
            int p=b.getPixel(x+(int)((c+sx)*size/8),y+(int)((r+sy)*size/8)),side=(r+c)%2;
            int red=Color.red(p),green=Color.green(p),blue=Color.blue(p);
            sums[side][0]+=red;sums[side][1]+=green;sums[side][2]+=blue;
            squares[side]+=red*red+green*green+blue*blue;
        }
        float delta=0,variance=0;
        for(int k=0;k<3;k++){float a=sums[0][k]/32,bb=sums[1][k]/32;delta+=(a-bb)*(a-bb);variance-=a*a+bb*bb;}
        variance+=(squares[0]+squares[1])/32;
        return (float)(Math.sqrt(delta)/(8+Math.sqrt(Math.max(0,variance))));
    }
}
