#!/usr/bin/env python3
"""Let the player ask the MacsInSpace gal hook for a fresh IDR from the phone. Host tool, run after patch_no_sd.py.

  python3 -I patch_keyframe.py SRC_DIR

Why: under pmcp the phone's H.264 goes to the AID unchanged (aa-most-feeder -> altscreen-most-bridge -> MOST). The phone
sends an IDR only every 64 s to 5 min (car, audit A-AA2/A-AA3). After a latency reset the bridge drops every frame until
the next IDR and asks for one by creating /ramdisk/carplay-alt-force-idr.request (request_fresh_idr); under CarPlay core.so
answers it, under AA nothing did, so the cluster map froze for minutes.

What this adds:
  - ACK pipe: a byte 'K' (0x4b) from the player is not an ACK but a keyframe request; every other byte stays one ACK
    (the feeder sends 0x01 per frame).
  - focus control: fc_keyframe_request() makes the controller, when ACTIVE and at most once per 3 s, take the existing
    "loss with the player kept" path (handle_loss(..., 0), as for a late MediaStop): mode 2, the phone stops the stream,
    the normal grant writes mode 1 and gates frames until the phone's new IDR (vc_stream_out_require_keyframe).
    The player and its connections stay. Requests in any other state are ignored (a grant brings an IDR anyway).
Each replacement must match exactly once.
"""
import pathlib
import sys

EDITS = {
    "src/focus_ctl.h": [
        ('void fc_run_mailbox(void);\n',
         'void fc_run_mailbox(void);\n'
         '/* pmcp: the player asked for a fresh IDR (ACK pipe byte \'K\'). Controller thread or any thread. */\n'
         'void fc_keyframe_request(void);\n'),
    ],
    "src/focus_ctl.c": [
        ('static volatile int g_dirty;        /* another thread wants a step now */\n',
         'static volatile int g_dirty;        /* another thread wants a step now */\n'
         '/* pmcp keyframe requests: set by fc_keyframe_request, taken by step(). Controller thread only otherwise. */\n'
         '#define FC_KEYFRAME_MIN_MS     3000LL\n'
         'static volatile int g_kf_requested;\n'
         'static long long g_kf_last_ms = -FC_KEYFRAME_MIN_MS;\n'
         'static unsigned long g_kf_done, g_kf_ignored;\n'),
        # take the request with the other step inputs
        ('    ring_count = g_ring_count;\n'
         '    pthread_mutex_unlock(&g_lock);\n'
         '\n'
         '    if (new_setup) {\n',
         '    ring_count = g_ring_count;\n'
         '    pthread_mutex_unlock(&g_lock);\n'
         '    kf_requested = g_kf_requested;\n'
         '    g_kf_requested = 0;\n'
         '\n'
         '    if (new_setup) {\n'),
        ('    unsigned ring_count;\n'
         '    int gate = g_sink != 0 && ((const unsigned char *)g_sink)[4] != 0;\n',
         '    unsigned ring_count;\n'
         '    int kf_requested;\n'
         '    int gate = g_sink != 0 && ((const unsigned char *)g_sink)[4] != 0;\n'),
        ('        if (late_stop) handle_loss(now, "late_stop", 0);\n'
         '        else active_step(now, state, ring_count);\n'
         '        break;\n',
         '        if (late_stop) handle_loss(now, "late_stop", 0);\n'
         '        else active_step(now, state, ring_count);\n'
         '        if (kf_requested) keyframe_step(now);\n'
         '        kf_requested = 0;\n'
         '        break;\n'),
        # after the switch: a request that arrived in HOLD/IDLE is only logged
        ('    default:\n'
         '        break;\n'
         '    }\n'
         '}\n',
         '    default:\n'
         '        break;\n'
         '    }\n'
         '    if (kf_requested) {\n'
         '        ++g_kf_ignored;\n'
         '        gal_hook_logf("event=focus.keyframe_request action=ignored reason=state_%s ignored=%lu fix=pmcp_keyframe",\n'
         '                      fc_state_name(), g_kf_ignored);\n'
         '    }\n'
         '}\n'),
        # keyframe_step before step(), after handle_loss
        ('static void step(long long now)\n{\n',
         '/*\n'
         ' * pmcp: a fresh IDR without replacing the player. Same path as a late MediaStop:\n'
         ' * mode 2 now, the phone stops the stream, hold_step grants mode 1 again (after\n'
         ' * the phone\'s own stop or FC_STOP_WAIT_MS) and grant() gates frames until the\n'
         ' * phone\'s new IDR. Only when ACTIVE, at most once per FC_KEYFRAME_MIN_MS.\n'
         ' */\n'
         'static void keyframe_step(long long now)\n'
         '{\n'
         '    int active;\n'
         '\n'
         '    pthread_mutex_lock(&g_lock);\n'
         '    active = (g_state == FC_ACTIVE);\n'
         '    pthread_mutex_unlock(&g_lock);\n'
         '    if (!active || now - g_kf_last_ms < FC_KEYFRAME_MIN_MS) {\n'
         '        ++g_kf_ignored;\n'
         '        gal_hook_logf("event=focus.keyframe_request action=ignored reason=%s since_last_ms=%lld ignored=%lu fix=pmcp_keyframe",\n'
         '                      active ? "too_soon" : "not_active", now - g_kf_last_ms, g_kf_ignored);\n'
         '        return;\n'
         '    }\n'
         '    g_kf_last_ms = now;\n'
         '    ++g_kf_done;\n'
         '    gal_hook_logf("event=focus.keyframe_request action=refocus count=%lu fix=pmcp_keyframe", g_kf_done);\n'
         '    handle_loss(now, "keyframe_request", 0);\n'
         '}\n'
         '\n'
         'static void step(long long now)\n{\n'),
        ('void fc_run_mailbox(void)\n{\n',
         'void fc_keyframe_request(void)\n'
         '{\n'
         '    if (!g_started) return;\n'
         '    g_kf_requested = 1;\n'
         '    fc_notify();\n'
         '}\n'
         '\n'
         'void fc_run_mailbox(void)\n{\n'),
    ],
    "src/vc_stream_out.c": [
        ('        while ((n = recv(g_ack_client_fd, buf, sizeof(buf), 0)) > 0) {\n'
         '            if (cb) cb((unsigned)n);\n'
         '        }\n',
         '        while ((n = recv(g_ack_client_fd, buf, sizeof(buf), 0)) > 0) {\n'
         '            /* pmcp: \'K\' asks for a fresh IDR and is no ACK; any other byte is one ACK. */\n'
         '            unsigned acks = 0u;\n'
         '            ssize_t i;\n'
         '            for (i = 0; i < n; ++i) {\n'
         '                if (buf[i] == \'K\') fc_keyframe_request();\n'
         '                else ++acks;\n'
         '            }\n'
         '            if (cb && acks != 0u) cb(acks);\n'
         '        }\n'),
    ],
}


def main():
    src = pathlib.Path(sys.argv[1])
    for rel, edits in EDITS.items():
        p = src / rel
        text = p.read_text()
        for old, new in edits:
            n = text.count(old)
            if n != 1:
                sys.exit("patch_keyframe: %s: expected 1 match, found %d: %r" % (rel, n, old[:70]))
            text = text.replace(old, new)
        p.write_text(text)
    print("patch_keyframe: OK")


if __name__ == "__main__":
    main()
