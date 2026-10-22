package android.graphics;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.awt.image.DataBufferInt;
import java.awt.image.SinglePixelPackedSampleModel;
import javax.imageio.ImageIO;
import java.io.*;
/** JVM-only image adapter for exercising recognition math, not Android behavior. */
public class Bitmap {
    public final BufferedImage image;
    public Bitmap(BufferedImage b){image=b;}
    public static Bitmap load(String path)throws IOException{
        BufferedImage source=ImageIO.read(new File(path));
        BufferedImage argb=new BufferedImage(source.getWidth(),source.getHeight(),BufferedImage.TYPE_INT_ARGB);
        Graphics2D g=argb.createGraphics();g.drawImage(source,0,0,null);g.dispose();return new Bitmap(argb);
    }
    public static Bitmap createBitmap(Bitmap b,int x,int y,int w,int h){return new Bitmap(b.image.getSubimage(x,y,w,h));}
    public static Bitmap createScaledBitmap(Bitmap b,int w,int h,boolean filter){BufferedImage image=new BufferedImage(w,h,BufferedImage.TYPE_INT_ARGB);Graphics2D g=image.createGraphics();g.setRenderingHint(RenderingHints.KEY_INTERPOLATION,RenderingHints.VALUE_INTERPOLATION_BILINEAR);g.drawImage(b.image,0,0,w,h,null);g.dispose();return new Bitmap(image);}
    public int getWidth(){return image.getWidth();}public int getHeight(){return image.getHeight();}public int getPixel(int x,int y){return image.getRGB(x,y);}
    public void getPixels(int[] pixels,int offset,int stride,int x,int y,int w,int h){
        // CaptureService uses ARGB_8888. Copy packed ARGB rows instead of timing a
        // PNG decoder's BGR-to-ARGB conversion on every read in the JVM adapter.
        if(image.getType()==BufferedImage.TYPE_INT_ARGB && image.getRaster().getDataBuffer() instanceof DataBufferInt){
            DataBufferInt buffer=(DataBufferInt)image.getRaster().getDataBuffer();
            SinglePixelPackedSampleModel model=(SinglePixelPackedSampleModel)image.getRaster().getSampleModel();
            int start=buffer.getOffset()+model.getOffset(x-image.getRaster().getSampleModelTranslateX(),y-image.getRaster().getSampleModelTranslateY());
            for(int row=0;row<h;row++)System.arraycopy(buffer.getData(),start+row*model.getScanlineStride(),pixels,offset+row*stride,w);
        }else image.getRGB(x,y,w,h,pixels,offset,stride);
    }
    public void recycle(){}
}
