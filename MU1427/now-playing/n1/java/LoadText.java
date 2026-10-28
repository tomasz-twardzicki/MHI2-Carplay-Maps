/* SPDX-License-Identifier: GPL-3.0-or-later. Factory-J9 probe, never installed. */
package com.cpmap.audio;
import org.dsi.ifc.carplay.TrackData;
import de.vw.mib.bap.mqbab2.generated.audiosd.serializer.CurrentStationInfo_Status;
public final class LoadText {
    static int checks;
    static void check(boolean ok) throws Exception { if(!ok) throw new Exception("N1 factory check"); checks++; }
    public static void main(String[] args) throws Exception {
        check(Class.forName("de.vw.mib.asl.internal.carplay.target.HsmTarget").getDeclaredMethod("initializeDSI",new Class[0])!=null);
        check(Class.forName("de.vw.mib.bap.mqbab2.audiosd.functions.CurrentStationInfo").newInstance()!=null);
        TextModel model=new TextModel();
        model.track(new TrackData("Title",1,"Album","Artist","",""),1);
        CurrentStationInfo_Status out=new CurrentStationInfo_Status(); TextBridge.render(out,model.frame());
        check(out.primaryInformation.toString().equals("Title"));
        check(out.secondaryInformation.toString().equals("Artist"));
        check(out.tertiaryInformation.toString().equals("Album"));
        check(out.pi_Type==72 && out.si_Type==73 && out.ti_Type==74);
        model.clear(); TextBridge.render(out,model.frame());
        check(out.primaryInformation.toString().equals("Apple CarPlay"));
        check(out.secondaryInformation.toString().equals(""));
        check(out.tertiaryInformation.toString().equals(""));
        check(out.si_Type==0 && out.ti_Type==0);
        model.track(null,2); check(model.frame().title.equals(""));
        check(!TextBridge.fill(out));
        System.out.print("N0_J9_PASS checks="); System.out.println(checks);
    }
}
