#!/usr/bin/env python3
"""Take every SD card path out of the MacsInSpace gal hook before it is built for pmcp. Host tool.

  python3 -I patch_no_sd.py SRC_DIR

The upstream hook reads its settings, writes its log and searches for helper binaries and libraries on the SD card
(/fs/sdb0, /fs/sda0) and in /tmp. Under pmcp the gal wrapper hands it one fixed settings file in /mnt/app/carplaymaps/aa
(GAL_HOOK_CONF), so nothing a card brings may change what runs inside gal or the programs it starts.
It also limits the hook log to GAL_HOOK_LOG_MAX_KB (default 128 KB, never unlimited): the log lives on the 20 MB /ramdisk
next to the 16 MB video ring. GAL_HOOK_NAV_LOG_MAX (1..200, default 6 as upstream) sets how many 0x8006/0x8007 navigation
messages of each kind are logged in hex; the gal wrapper raises it only for the one capture start (pmcp.sh aa-capture).
Each replacement must match exactly once; afterwards no "/fs/sd" may be left outside comments.
"""
import pathlib
import re
import sys

AA = "/mnt/app/carplaymaps/aa"
EDITS = {
    "src/gal_hook.c": [
        ('#define GAL_HOOK_LOG "/fs/sdb0/logs/gal_dualscreen.log"', '#define GAL_HOOK_LOG "/tmp/gal_dualscreen.log"'),
        ('candidates[1] = "/fs/sdb0/gal_dualscreen.conf";', 'candidates[1] = NULL;'),
        ('candidates[2] = "/fs/sda0/gal_dualscreen.conf";', 'candidates[2] = NULL;'),
        ('candidates[3] = "/eso/lib/gal_dualscreen/gal_dualscreen.conf";', 'candidates[3] = NULL;'),
        ('candidates[4] = "/tmp/gal_dualscreen.conf";', 'candidates[4] = NULL;'),
        # /ramdisk is 20 MB and the video ring takes 16 MB of it: the log limit is in KB (default 128 KB), never unlimited
        ('    const char *value = getenv("GAL_HOOK_LOG_MAX_MB");\n'
         '    unsigned long mb = value != NULL && *value != \'\\0\' ?\n'
         '        strtoul(value, NULL, 10) : GAL_HOOK_LOG_MAX_MB_DEFAULT;\n'
         '    if (mb == 0ul) return 0;\n'
         '    if (mb > 1024ul) mb = 1024ul;\n'
         '    return (off_t)(mb * 1024ul * 1024ul);',
         '    const char *value = getenv("GAL_HOOK_LOG_MAX_KB");\n'
         '    unsigned long kb = value != NULL && *value != \'\\0\' ? strtoul(value, NULL, 10) : 128ul;\n'
         '    if (kb == 0ul || kb > 1024ul) kb = 128ul;\n'
         '    return (off_t)(kb * 1024ul);'),
    ],
    "src/video_sink_hook.c": [
        # how many navigation messages of each kind are logged: GAL_HOOK_NAV_LOG_MAX (1..200), default 6 as upstream
        ('        static unsigned logged[2];\n'
         '        unsigned slot = g_channel_last_id[channel] == 0x8006u ? 0u : 1u;\n'
         '        if (logged[slot] < 6u) {',
         '        static unsigned logged[2], nav_max;\n'
         '        unsigned slot = g_channel_last_id[channel] == 0x8006u ? 0u : 1u;\n'
         '        if (nav_max == 0u) {\n'
         '            const char *v = getenv("GAL_HOOK_NAV_LOG_MAX");\n'
         '            unsigned long n = v != NULL && *v != \'\\0\' ? strtoul(v, NULL, 10) : 6ul;\n'
         '            nav_max = n >= 1ul && n <= 200ul ? (unsigned)n : 6u;\n'
         '        }\n'
         '        if (logged[slot] < nav_max) {'),
    ],
    "src/vc_player_mgr.c": [
        ('#define DMDT_FLUSH_PRELOAD   "LD_PRELOAD=/eso/lib/gal_dualscreen/libdmdt_flush.so:/mnt/app/eso/lib/gal_dualscreen/libdmdt_flush.so:'
         '/mnt/app/eso/lib/libdmdt_flush.so:/fs/sdb0/lib/libdmdt_flush.so:/fs/sda0/lib/libdmdt_flush.so"',
         '#define DMDT_FLUSH_PRELOAD   "LD_PRELOAD=%s/libdmdt_flush.so"' % AA),
        ('        "/fs/sdb0/stream-player",\n        "/fs/sda0/stream-player",\n        "./stream-player",\n'
         '        "/tmp/stream-player",\n', ''),
        ('setenv("LD_LIBRARY_PATH", "/proc/boot:/lib:/lib/dll:/usr/lib:/mnt/app/root/lib-target:/mnt/app/usr/lib:'
         '/mnt/app/armle/lib:/mnt/app/armle/lib/dll:/mnt/app/armle/usr/lib:/eso/lib:/mnt/app/eso/lib:/fs/sdb0/lib", 1);',
         'setenv("LD_LIBRARY_PATH", "/proc/boot:/lib:/lib/dll:/usr/lib:/mnt/app/root/lib-target:/mnt/app/usr/lib:'
         '/mnt/app/armle/lib:/mnt/app/armle/lib/dll:/mnt/app/armle/usr/lib:/eso/lib:/mnt/app/eso/lib", 1);'),
        ('(char *)"LD_LIBRARY_PATH=/proc/boot:/lib:/lib/dll:/usr/lib:/mnt/app/root/lib-target:/mnt/app/usr/lib:'
         '/mnt/app/armle/lib:/mnt/app/armle/lib/dll:/mnt/app/armle/usr/lib:/eso/lib:/mnt/app/eso/lib:/fs/sdb0/lib",',
         '(char *)"LD_LIBRARY_PATH=/proc/boot:/lib:/lib/dll:/usr/lib:/mnt/app/root/lib-target:/mnt/app/usr/lib:'
         '/mnt/app/armle/lib:/mnt/app/armle/lib/dll:/mnt/app/armle/usr/lib:/eso/lib:/mnt/app/eso/lib",'),
        ('(char *)"PATH=/proc/boot:/bin:/usr/bin:/usr/sbin:/sbin:/eso/bin:/mnt/app/eso/bin:/fs/sdb0/bin:/mnt/app/navigation",',
         '(char *)"PATH=/proc/boot:/bin:/usr/bin:/usr/sbin:/sbin:/eso/bin:/mnt/app/eso/bin:/mnt/app/navigation",'),
    ],
}


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def main():
    src = pathlib.Path(sys.argv[1])
    for rel, edits in EDITS.items():
        p = src / rel
        text = p.read_text()
        for old, new in edits:
            n = text.count(old)
            if n != 1:
                sys.exit("patch_no_sd: %s: expected 1 match, found %d: %r" % (rel, n, old[:70]))
            text = text.replace(old, new)
        p.write_text(text)
    left = []
    for p in sorted(src.rglob("*.[ch]")):
        code = strip_comments(p.read_text())
        for word in ("/fs/sd", "gal_dualscreen.conf\""):
            if word in code:
                left.append("%s: %s" % (p.relative_to(src), word))
    if left:
        sys.exit("patch_no_sd: still in the code: " + ", ".join(left))
    print("patch_no_sd: OK")


if __name__ == "__main__":
    main()
