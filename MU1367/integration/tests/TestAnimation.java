/* v1.5.3-e: the MU UI's startup-animation store (written here by the shipped VCMenu.jar) and its labels.
 * test_animation.c then reads the same files with the CarPlay bridge's C reader. SPDX-License-Identifier: GPL-3.0-or-later */
import java.io.File;
import org.omonob.cpmap.ui.AnimationMenuMessages;
import org.omonob.cpmap.ui.AnimationSettings;
import org.omonob.cpmap.ui.UiMessages;
public class TestAnimation {
    static void ok(boolean c,String m){if(!c)throw new AssertionError(m);}
    public static void main(String[] a)throws Exception{
        File root=new File(a[0]);
        AnimationSettings d=new AnimationSettings(new File(root,"default"),null);
        ok(d.read().mode==AnimationSettings.ONCE_PER_BOOT&&d.read().generation==0,"default is once per boot");
        for(int m=0;m<3;m++){AnimationSettings s=new AnimationSettings(new File(root,"m"+m),null);ok(s.set(m).mode==m&&s.read().mode==m,"mode "+m);}
        AnimationSettings r=new AnimationSettings(new File(root,"rot"),null);r.set(AnimationSettings.OFF);r.set(AnimationSettings.EVERY_CONNECT);
        ok(r.read().mode==AnimationSettings.EVERY_CONNECT&&r.read().generation==2,"second save rotates the previous state");
        String en=UiMessages.supportedLocales()[0];
        ok(AnimationMenuMessages.get(en,0).equals("Startup animation"),"row name");
        ok(AnimationMenuMessages.get(en,1).equals("Every connection")&&AnimationMenuMessages.get(en,2).equals("Once per boot (default)")&&AnimationMenuMessages.get(en,3).equals("Off"),"choices");
        System.out.println("ANIMATION_JAVA_PASS "+en);
    }
}
