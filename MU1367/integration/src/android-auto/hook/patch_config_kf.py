#!/usr/bin/env python3
"""Experiment: ask the phone for a fresh IDR by resending the channel setup response, without a focus cycle. Host tool,
run after patch_keyframe.py.

  python3 -I patch_config_kf.py SRC_DIR

Why: patch_keyframe.py's byte 'K' cycles the cluster focus 2 -> 1. On the car the phone answered with an IDR in 0.84 s,
but then streamed ~3 fps and reset the connection ~130 s later (audit A-AA11). libautoreceiver.so on MU1161 has no
keyframe request message. Candidate: MediaSinkBase::sendConfig(sink, 2), the AVChannelSetupResponse (message 0x8003)
gal sends once at setup (log: arg=2, one configuration index). Whether the phone answers a second one with a new codec
config / IDR, ignores it or drops the session is what the feeder measures (feeder status "IDR po ...ms", "bez IDR").

What this adds:
  - ACK pipe: a byte 'C' (0x43) is a request too, not an ACK.
  - focus control: fc_config_request() -> config_step(): only when ACTIVE, at most once per 3 s (own limit), calls
    fc_ops.send_config(sink, 2) under the endpoint write lock; no focus change, no state change. Logged
    event=focus.config_request action=sent|ignored.
  - video_sink_hook.c: fc_ops.send_config = this hook's own sendConfig interposer (so it is logged as
    event=aap.config_response role=secondary like gal's own call).
Each replacement must match exactly once.
"""
import pathlib
import sys

EDITS = {
    "src/focus_ctl.h": [
        ('    fc_frames_rendered_fn frames_rendered; /* ACK this many frames to the phone */\n',
         '    fc_frames_rendered_fn frames_rendered; /* ACK this many frames to the phone */\n'
         '    int (*send_config)(void *sink, int arg); /* pmcp: MediaSinkBase::sendConfig, may be NULL */\n'),
        ('void fc_keyframe_request(void);\n',
         'void fc_keyframe_request(void);\n'
         "/* pmcp experiment: resend the channel setup response instead (ACK pipe byte 'C'), no focus change. */\n"
         'void fc_config_request(void);\n'),
    ],
    "src/focus_ctl.c": [
        ('static unsigned long g_kf_done, g_kf_ignored;\n',
         'static unsigned long g_kf_done, g_kf_ignored;\n'
         'static volatile int g_cfg_requested;\n'
         'static long long g_cfg_last_ms = -FC_KEYFRAME_MIN_MS;\n'
         'static unsigned long g_cfg_done, g_cfg_ignored;\n'),
        ('static void keyframe_step(long long now)\n{\n',
         '/*\n'
         ' * pmcp experiment: resend the secondary channel setup response (0x8003) without a\n'
         ' * focus change. Same write lock as every other write on this endpoint.\n'
         ' */\n'
         'static void config_step(long long now)\n'
         '{\n'
         '    int active, rc;\n'
         '\n'
         '    pthread_mutex_lock(&g_lock);\n'
         '    active = (g_state == FC_ACTIVE);\n'
         '    pthread_mutex_unlock(&g_lock);\n'
         '    if (!active || g_ops.send_config == 0 || now - g_cfg_last_ms < FC_KEYFRAME_MIN_MS) {\n'
         '        ++g_cfg_ignored;\n'
         '        gal_hook_logf("event=focus.config_request action=ignored reason=%s ignored=%lu fix=pmcp_keyframe",\n'
         '                      !active ? "not_active" : (g_ops.send_config == 0 ? "no_symbol" : "too_soon"),\n'
         '                      g_cfg_ignored);\n'
         '        return;\n'
         '    }\n'
         '    g_cfg_last_ms = now;\n'
         '    ++g_cfg_done;\n'
         '    pthread_mutex_lock(&g_write_lock);\n'
         '    rc = g_ops.send_config(g_sink, 2);\n'
         '    pthread_mutex_unlock(&g_write_lock);\n'
         '    gal_hook_logf("event=focus.config_request action=sent count=%lu rc=%d fix=pmcp_keyframe", g_cfg_done, rc);\n'
         '}\n'
         '\n'
         'static void keyframe_step(long long now)\n{\n'),
        ('    kf_requested = g_kf_requested;\n'
         '    g_kf_requested = 0;\n',
         '    kf_requested = g_kf_requested;\n'
         '    g_kf_requested = 0;\n'
         '    if (g_cfg_requested) {\n'
         '        g_cfg_requested = 0;\n'
         '        config_step(now);\n'
         '    }\n'),
        ('void fc_keyframe_request(void)\n{\n',
         'void fc_config_request(void)\n'
         '{\n'
         '    if (!g_started) return;\n'
         '    g_cfg_requested = 1;\n'
         '    fc_notify();\n'
         '}\n'
         '\n'
         'void fc_keyframe_request(void)\n{\n'),
    ],
    "src/vc_stream_out.c": [
        ("                if (buf[i] == 'K') fc_keyframe_request();\n",
         "                if (buf[i] == 'K') fc_keyframe_request();\n"
         "                else if (buf[i] == 'C') fc_config_request();\n"),
        ("            /* pmcp: 'K' asks for a fresh IDR and is no ACK; any other byte is one ACK. */\n",
         "            /* pmcp: 'K' and 'C' ask for a fresh IDR and are no ACK; any other byte is one ACK. */\n"),
    ],
    "src/video_sink_hook.c": [
        ('            ops.frames_rendered = on_frames_rendered;\n',
         '            ops.frames_rendered = on_frames_rendered;\n'
         "            ops.send_config = pmcp_send_config;   /* pmcp experiment: ACK pipe byte 'C' */\n"),
        ('static void fc_write_focus(void *sink, int mode, int unconstrained)\n',
         "/* pmcp: the controller resends the setup response through this hook's own interposer (logged). */\n"
         'int _ZN13MediaSinkBase10sendConfigEi(void *sink, int arg);\n'
         'static int pmcp_send_config(void *sink, int arg)\n'
         '{\n'
         '    return _ZN13MediaSinkBase10sendConfigEi(sink, arg);\n'
         '}\n'
         '\n'
         'static void fc_write_focus(void *sink, int mode, int unconstrained)\n'),
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
                sys.exit("patch_config_kf: %s: expected 1 match, found %d: %r" % (rel, n, old[:70]))
            text = text.replace(old, new)
        p.write_text(text)
    print("patch_config_kf: OK")


if __name__ == "__main__":
    main()
