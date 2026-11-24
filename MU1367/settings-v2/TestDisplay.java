/* SPDX-License-Identifier: GPL-3.0-or-later */
import java.io.*;
import org.omonob.cpmap.ui.*;
public final class TestDisplay {
    static int checks;
    static void check(boolean ok)throws Exception{checks++;if(!ok)throw new Exception("display assertion "+checks);}
    static byte[] read(File f)throws Exception{byte[] b=new byte[(int)f.length()];FileInputStream in=new FileInputStream(f);try{check(in.read(b)==b.length);}finally{in.close();}return b;}
    static void write(File f,byte[] b)throws Exception{FileOutputStream out=new FileOutputStream(f);try{out.write(b);}finally{out.close();}}
    public static void main(String[] args)throws Exception{
        File root=new File(args[0]);DisplaySettings store=new DisplaySettings(root);
        if(args.length>1){store.select(DisplaySettings.STREAM,Integer.parseInt(args[1]));store.select(DisplaySettings.LAYOUT,Integer.parseInt(args[2]));DisplaySettings.State s=store.read();System.out.println(s.stream+","+s.layout+","+s.generation);return;}
        check(store.read().stream==0&&store.read().layout==0&&store.read().generation==0);
        for(int s=0;s<4;s++)for(int l=0;l<4;l++){
            int previous=store.read().layout;
            store.select(DisplaySettings.STREAM,s);check(store.read().layout==previous);
            store.select(DisplaySettings.LAYOUT,l);
            DisplaySettings.State value=new DisplaySettings(root).read();
            check(value.stream==s&&value.layout==l);check(DisplaySettings.label(6,s).length()>0);check(DisplaySettings.label(7,l).length()>0);
        }
        File primary=new File(root,"display.state"),previous=new File(root,"display.previous");
        byte[] good=read(primary);write(primary,new byte[]{33});check(store.read().source.equals("recovered"));
        byte[] backup=read(previous);write(previous,new byte[]{33});boolean failed=false;
        try{store.read();}catch(IOException expected){failed=true;}check(failed);
        failed=false;try{store.select(6,1);}catch(IOException expected){failed=true;}check(failed);
        write(primary,good);write(previous,backup);
        for(int field=6;field<8;field++)for(int choice=-1;choice<=4;choice+=5){
            failed=false;try{store.select(field,choice);}catch(IllegalArgumentException expected){failed=true;}check(failed);
            check(new String(read(primary),"US-ASCII").equals(new String(good,"US-ASCII")));
        }
        System.out.println("DISPLAY_SETTINGS_PASS checks="+checks);
    }
}
