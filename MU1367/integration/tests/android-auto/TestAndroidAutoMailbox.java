/* SPDX-License-Identifier: GPL-3.0-or-later
 * v1.5.0-e: reads the hook mailbox steps (rg_test.c, pmcp_rg.c from chrzanowy/mhi2-aid-carplay
 * af98480) with the MU1367 release MailboxReader + LiveModel from CarPlayMU1367Guidance.jar. */
package com.cpmap.rgi;

import java.io.*;
import java.nio.file.*;

public final class TestAndroidAutoMailbox {
    static int fails;
    static void check(boolean c, String m) { System.out.println((c ? "ok     " : "FAILED ") + m); if (!c) fails++; }
    public static void main(String[] a) throws Exception {
        String dir = a[0];
        Path cur = Paths.get(dir, "cur.bin");
        MailboxReader r = new MailboxReader(cur.toString());
        final int N = 15;
        LiveModel.Frame[] f = new LiveModel.Frame[N];
        for (int i = 0; i < N; i++) {
            Files.copy(Paths.get(dir, "step-" + i + ".bin"), cur, StandardCopyOption.REPLACE_EXISTING);
            f[i] = r.next(1000L * (i + 1));
            boolean same = f[i] == null;
            if (same) f[i] = r.model.frame();          /* same serial: nothing changed, the model's current frame */
            if (!same) System.out.println("step " + i + ": active=" + f[i].active + " main=" + f[i].main + " dir=" + f[i].direction
                + " m=" + f[i].meters + " rem=" + f[i].remainingMeters + "/" + f[i].remainingSeconds + " progress=" + f[i].progress);
            else System.out.println("step " + i + ": same serial, model: main=" + f[i].main + " m=" + f[i].meters);
        }
        check(f[0] != null && !f[0].active, "0 baseline: not active");
        check(f[1] != null && f[1].active && f[1].main == 13 && f[1].direction == 64 && f[1].meters == -1, "1 left turn arrow, no distance");
        check(f[2] != null && f[2].active && f[2].main == 13 && f[2].meters == 250, "2 distance 250 m");
        check(f[3] != null && f[3].main == 13 && f[3].direction == 64 && f[3].meters == 250, "3 same step: same arrow and distance");
        check(f[4] != null && f[4].main == 21 && f[4].direction == 192 && f[4].meters == 80, "4 roundabout exit to the right, 80 m");
        check(f[5] != null && f[5].main != 21 && !(f[5].meters == 900 && f[5].main == 21), "5 unknown type: no roundabout arrow, 900 m not attached to it (main=" + (f[5] == null ? -1 : f[5].main) + ")");
        check(f[6] != null && f[6].main == 13 && f[6].direction == 192 && f[6].meters == 120, "6 right turn 120 m");
        check(f[7] != null && f[7].active && f[7].main == 13 && f[7].meters == 110, "7 still navigating, 110 m");
        check(f[8] != null && f[8].progress > f[7].progress, "8 route event repeated while the phone navigates");
        check(f[10] != null && f[9] != null && f[10].progress == f[9].progress, "10 phone silent: no route repeats (progress " + f[9].progress + " -> " + f[10].progress + ")");
        check(f[11] != null && f[11].active && f[11].main == 13 && f[11].meters == 100 && f[11].progress > f[10].progress, "11 phone back: arrow and 100 m again");
        check(f[12] != null && !f[12].active, "12 long silence: route ended");
        check(f[13] != null && f[13].active && f[13].main == 13 && f[13].direction == 64 && f[13].meters == 300, "13 new route after the silent end");
        check(f[14] != null && !f[14].active, "14 route ended: not active");
        boolean noEta = true;
        for (int i = 0; i < N; i++) if (f[i] != null && (f[i].remainingMeters != -1 || f[i].remainingSeconds != -1)) noEta = false;
        check(noEta, "no ETA / remaining distance ever set");
        System.out.println("FAILED CHECKS Java: " + fails);
        System.exit(fails == 0 ? 0 : 1);
    }
}
