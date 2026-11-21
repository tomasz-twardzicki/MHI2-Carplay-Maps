import java.io.File;
import org.omonob.cpmap.ui.Card791Options;
import org.omonob.cpmap.ui.CardPositionSettings;

public final class TestCardDefault {
    public static void main(String[] args) throws Exception {
        CardPositionSettings store = new CardPositionSettings(new File(args[0]));
        if (store.read().position != 3 || Card791Options.choiceForPosition(store.read().position) != 1)
            throw new Exception("Fresh default must be Off");
        store.set(Card791Options.positionForChoice(0));
        if (store.read().position != 2) throw new Exception("Explicit On must persist");
        store.set(Card791Options.positionForChoice(1));
        if (store.read().position != 3) throw new Exception("Explicit Off must persist");
        System.out.println("CARD_OFF_DEFAULT_PASS explicit_on_off_persisted=1");
    }
}
