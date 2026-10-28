/* Host-only test. SPDX-License-Identifier: GPL-3.0-or-later */
import java.io.File;
import org.omonob.cpmap.ui.*;
public final class TestCardDefault {
 public static void main(String[] args)throws Exception{
  CardPositionSettings s=new CardPositionSettings(new File(args[0]));
  if(s.read().position!=3||Card791Options.choiceForPosition(s.read().position)!=1)throw new Exception("Default card must be OFF");
  s.set(Card791Options.positionForChoice(0));if(s.read().position!=2)throw new Exception("App-Connect ON");
  s.set(Card791Options.positionForChoice(1));if(s.read().position!=3)throw new Exception("App-Connect OFF");
  System.out.println("CARD_OFF_DEFAULT_PASS explicit_on_off_persisted=1");
 }
}
