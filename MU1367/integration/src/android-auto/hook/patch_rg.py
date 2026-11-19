#!/usr/bin/env python3
"""AA gamma: feed Android Auto 1.7 navigation into the rg RAM mailbox (pmcp_rg.c). Host tool, run after the other
patches, only for the gamma hook build (build.sh ... gamma).

  python3 -I patch_rg.py SRC_DIR

Copies pmcp_rg.c / pmcp_rg.h into src/ and calls pmcp_rg_message() with every NavigationStatus message 0x8003 / 0x8006 /
0x8007 before the hook's own logging and nav_translate (which rewrites it in place). pmcp_rg_message does nothing unless
GAL_PMCP_RG=1. Each replacement must match exactly once.
"""
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
OLD = '''    if (strstr(g_service_class[channel], "NavigationStatus") != NULL &&
        (g_channel_last_id[channel] == 0x8006u ||
         g_channel_last_id[channel] == 0x8007u)) {
'''
NEW = '''    /* pmcp gamma: the raw navigation message to the rg mailbox writer (GAL_PMCP_RG=1), before it is rewritten */
    if (strstr(g_service_class[channel], "NavigationStatus") != NULL &&
        (g_channel_last_id[channel] == 0x8003u || g_channel_last_id[channel] == 0x8006u ||
         g_channel_last_id[channel] == 0x8007u)) {
        unsigned rg_nb = 0u;
        const unsigned char *rg_m = (const unsigned char *)iobuffer_bytes(buffer, &rg_nb);
        if (rg_m != NULL) pmcp_rg_message(rg_m, rg_nb);
    }
''' + OLD


def main():
    src = pathlib.Path(sys.argv[1])
    p = src / "src/video_sink_hook.c"
    t = p.read_text()
    for old, new in [(OLD, NEW), ('#include "nav_translate.h"\n', '#include "nav_translate.h"\n#include "pmcp_rg.h"\n')]:
        n = t.count(old)
        if n != 1:
            sys.exit("patch_rg: expected 1 match, found %d: %r" % (n, old[:70]))
        t = t.replace(old, new)
    p.write_text(t)
    for f in ("pmcp_rg.c", "pmcp_rg.h"):
        shutil.copyfile(HERE / f, src / "src" / f)
    print("patch_rg: OK")


if __name__ == "__main__":
    main()
