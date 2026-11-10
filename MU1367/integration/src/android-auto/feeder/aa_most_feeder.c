/*
 * aa-most-feeder: Android Auto cluster video -> omonob's altscreen-most-bridge ring -> MOST -> AID.
 *
 * Started by MacsInSpace's libgal_hook.so in place of its stream-player (GAL_PLAYER_PATH), with the
 * stream URL as argv[1] ("tcp://127.0.0.1:12346" or a Unix socket path). The hook sends raw H.264
 * Annex B with no framing and expects one byte on /tmp/gal_ack.sock per frame the player has taken;
 * it ACKs the phone only then, so delaying that byte slows the phone down.
 *
 * Ring and bridge facts used here (docs/11-ring-altscreen.md, docs/06-audyt.md A63/A64):
 *   file 0x1000710 B: header {magic 'GRPC', version 1, generation, last seq}, 64 slots x 0x4001c;
 *   slot {seq, type (1 avcC, 2 frame), len, 0, frame no, u64 NTP 32.32 time, data <= 0x40000};
 *   writer: slot.seq = 0, fields + data, slot.seq = N, header.seq = N. The bridge reads from seq 1
 *   after it (re)initialises the file, adds start code + AUD itself and puts SPS/PPS from the avcC
 *   in front of every IDR, so frames go in as AVCC without AUD/SPS/PPS.
 *   MOST takeover as carplay-cluster-supervisor: dmdt dc 72 + dmdt sc 4 72, 500 ms, start bridge;
 *   back: SIGTERM bridge, flush(0) on /dev/mlb/debug/isoTX2, SIGKILL, 250 ms, dmdt dc 70 33 + sc 4 70.
 *
 * Fresh IDR (v2): the phone sends an IDR only every 64 s to 5 min, and after a latency reset the bridge drops every
 * frame until the next one; it asks for one by creating PMCP_AA_KF_REQ (default /ramdisk/carplay-alt-force-idr.request,
 * request_fresh_idr). In "most" mode with the ring ours the feeder removes that file and sends the byte 'K' on the ACK
 * pipe; the pmcp-patched hook (aa/hook/patch_keyframe.py) then cycles the cluster focus 2 -> 1 and the phone restarts its
 * stream with an IDR. Optionally also once PMCP_AA_KF_TAKE_MS after the takeover (default 0 = off since v3: on the car
 * a focus cycle in a session dropped the phone to ~3 fps and reset the connection ~130 s later, audit A-AA11).
 * At most one request per PMCP_AA_KF_MIN_MS.
 *
 * v3: in "most" mode the MOST takeover runs BEFORE the feeder connects to the hook's stream, so the phone is granted
 * the cluster only after the bridge is up and no frame waits for its ACK during the takeover (v2 took it at the first
 * IDR: ACKs stood still ~1.5 s, the hook presumed 6 frames dropped and discarded 5 late ACKs, A-AA11).
 *
 * v4: the takeover waits (PMCP_AA_WAIT_MS, default 6 s) while the guardian of the previous AA session is still stopping its
 * bridge or giving MOST back (gal restarts within 1 s, A-AA13; the guardian marks itself in <rundir>/pmcp-aa-guard.pid
 * until its dmdt restore is done), then waits PMCP_AA_SETTLE_MS (default 1 s) before the stream connects. The bridge's
 * output goes through a pipe to the guardian, which counts latency resets / IDR requests / MOST write errors and keeps
 * the last lines in <rundir>/pmcp-aa-bridge.txt; each session appends one line to <rundir>/pmcp-aa-sessions.txt (last 10
 * kept). Both are shown in the status. <rundir> = PMCP_AA_RUNDIR, default /ramdisk.
 *
 * v5: PMCP_AA_KF_METHOD=focus (byte 'K', focus cycle, default) or config (byte 'C': the patched hook resends the channel
 * setup response 0x8003, no focus change; aa/hook/patch_config_kf.py, experiment A-AA15).
 *
 * v6: start sync (PMCP_AA_SYNC_HOLD_MS, default 0 = off; the sync modes set 2500). The AID loses the session's first IDR
 * now and then (it is not ready yet; bridge keys = IDRs, drops = 0) and shows "starting map view" until the phone's next
 * IDR, 60 s to 5 min later (A-AA18). With sync on, the first IDR of a MOST session is written, its ACK is held, and the
 * same IDR is written again every PMCP_AA_SYNC_REPEAT_MS (default 500) until the hold ends. The phone stops after its
 * 8-frame window (the hook releases credit only when an ACK arrives, its hang rule is 20 s), the few frames it sent
 * meanwhile wait here and go out in order after the hold, then all ACKs. Every copy is the same picture, so the P frames
 * after it decode on the right reference whichever copy the AID took. The status lists the session's first IDRs
 * (time after the takeover, size) to check this on the car.
 *
 * v7 (car, A-AA20): the phone's first IDR of a stream is ~1 KB, an empty picture; the map comes in the P frames after it.
 * So repeating that IDR does not help: the AID must already decode when the first P frames come, or it shows the dark
 * picture with only the changes drawn on it until the phone's next IDR (60+ s). The hook waits for the player's
 * connections with no time limit before it grants the phone, so the feeder can wait as long as it likes after the
 * takeover: PMCP_AA_SETTLE_MS up to 15 s (the AA 3 settings use 5 s).
 * CarPlay: its cluster supervisor is a permanent daemon (started once per boot, idle without a phone), so its pid file
 * only says "running", and v3-v6 refused MOST for the rest of the boot once CarPlay had been used (car, A-AA20). It owns
 * MOST only while its bridge runs: /ramdisk/carplay-bridge.ready AND a live altscreen-most-bridge process that is not
 * ours (the marker can outlive a bridge that exited by itself). The takeover waits up to PMCP_AA_CP_WAIT_MS (default
 * 20 s) for that to end. Without /proc (host tests) the marker alone counts.
 *
 * v8 (car, A-AA27): after CarPlay the bridge failed with "open ring ... No space left on device". CarPlay's producer
 * (core.so in dio_manager, a permanent process) keeps the ring file mapped, so unlinking it (v2-v7) only hid the name: the
 * 16 MB stay used, the 20 MB /ramdisk has no room for a second ring, and AA had no picture until a restart (the same
 * cause as AA 2's "no MOST after CarPlay"). Now a ring of the right size and magic is reused in place: the header's
 * last sequence and every slot's sequence are set to 0 (so the bridge, starting at 1, replays nothing) and the file
 * stays; only a ring of another size or without magic is unlinked as before. The status line "plik ringu" says which.
 *
 * v9 (car, A-AA30): the AID also lost the picture in the middle of a drive (loading screen, 199 s session, one IDR, the
 * largest P frame 96 KB, 4.7 Mbit/s in one second, nothing dropped on our side). Two changes:
 *   pacing (PMCP_AA_PACE_KBPS, default 0 = off; PMCP_AA_PACE_BURST_KB, default 64): frames go into the ring no faster than
 *   this byte budget. A frame that overdraws it still goes whole, but the frames after it wait here (in order, their ACKs
 *   too, so the phone slows down) until the budget is back, so the AID's decoder never gets several large frames at once.
 *   The queue holds at most PACE_MAX frames / PACE_POOL bytes; when full everything queued goes out at once (counted).
 *   Diagnostics: frames per 10 s for the last 5 min, the longest gap between frames (and when), the last large frames,
 *   and how long ago the last frame came, so the status tells "the phone stopped sending" from "frames still came".
 *
 * v10 (car, A-AA33): one session of v9 ended like A-AA11. Around 128 s the pacing queue was full (48) and went out at
 * once; the bridge (omonob source: more than 1024 TS packets = ~188 KB = ~125 ms of MOST queued when a frame comes) did
 * a latency-reset, lost the frames until an IDR and asked for one; the feeder
 * turned that into a focus cycle; the phone sent the IDR, dropped to ~3 fps and the connection reset ~130 s later. The
 * start hold also put its 15 held frames into the ring at once. The rule now: the ring never gets a burst.
 *   - PMCP_AA_PACE_GAP_MS (default 0 = off): at least this long between two frames into the ring, also for the frames
 *     after the start hold and the ones queued by the byte budget;
 *   - the queue is larger (PACE_MAX / PACE_POOL); from 3/4 full it drains on a second byte budget,
 *     PMCP_AA_PACE_DRAIN_KBPS (default 8000, burst 128 KB: below the bridge's 188 KB and the 12.288 Mbit/s of MOST),
 *     still with the gap; when it is full only the oldest frames needed for room go out (counted), never the whole queue;
 *   - PMCP_AA_KF_BRIDGE (default 0): the bridge's IDR request file is removed and counted, but no focus cycle / config
 *     resend follows unless this is 1 (both break the phone's session, A-AA11/A-AA15).
 *
 * MU1367 v1.5.0-e (CarPlay Maps VC integration, GPL-3.0-or-later; base: chrzanowy/mhi2-aid-carplay af98480, v10):
 *   - video cache lease: from before the ring is touched until MOST is given back the feeder holds a shared POSIX
 *     lock on /ramdisk/cpmap-video-cache.lock (PMCP_AA_CACHE_LOCK), as the MU1367 bridge and CarPlay producer do.
 *     The MU1367 cluster supervisor removes the 16 MB ring only under the exclusive lock while CarPlay is idle,
 *     so it can never unlink the ring between this feeder's reset/map and the bridge's own lease.
 *   - cluster map policy: MOST is taken only when the MU menu requests the cluster map (the supervisor's
 *     cpvc_video_requested() rules: valid preferences with map bit 1 and CLUSTER_AUTO_ENABLE present). Otherwise
 *     the session runs as "analyze" and the AID keeps its VW content. PMCP_AA_PREF_DIR / PMCP_AA_AUTO_ENABLE are
 *     environment-only overrides for host tests; the hook starts this feeder with a fixed environment on the unit.
 *
 * Modes (PMCP_AA_MODE): "analyze" (default) only reads, ACKs and writes a summary; the cluster keeps
 * the VW map. "most" also takes the MOST channel over. The summary is rewritten once a second to
 * PMCP_AA_STATUS (default /ramdisk/pmcp-aa-feeder.txt); nothing grows without bound.
 *
 * The hook starts the player with a fixed environment (IPL_CONFIG_DIR, LD_LIBRARY_PATH, PATH), so on the
 * unit the settings come from PMCP_AA_CONF (default /mnt/app/carplaymaps/aa/feeder.conf, written and
 * hash-checked by pmcp.sh): KEY=VALUE lines, only the keys in CONF_KEYS, the environment wins (host tests).
 */
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <dirent.h>
#include <time.h>
#include <unistd.h>
#include <arpa/inet.h>
#include "cpmap_projection_preferences.h"
#include "cpvc_video_policy.h"
#ifndef CPVC_PREF_DIR
#define CPVC_PREF_DIR "/mnt/icab/persistent/cpmap-ui"   /* cpvc_authorized_runtime.h */
#endif

#define FEEDER_VERSION "10-mu1367.1"

#define RING_MAGIC      0x43505247u
#define RING_VERSION    1u
#define RING_SLOTS      64u
#define RING_SLOT_SIZE  0x4001cu
#define RING_HDR_SIZE   0x10u
#define RING_FILE_SIZE  (RING_HDR_SIZE + RING_SLOTS * RING_SLOT_SIZE)   /* 0x1000710 */
#define RING_DATA_MAX   0x40000u
#define RING_TYPE_AVCC  1u
#define RING_TYPE_FRAME 2u

#define IN_BUF_MAX      (1024u * 1024u)   /* raw Annex B waiting for an access unit boundary */
#define AU_MAX          RING_DATA_MAX     /* the ring cannot carry a larger frame */
#define PS_MAX          256u              /* one SPS or PPS */
#define ACK_QUEUE       64u
#define SYNC_POOL       (768u * 1024u)    /* frames the phone sent during the start hold (window: 8) */
#define SYNC_HELD_MAX   32u
#define IDR_LOG_MAX     6u
#define PACE_POOL       (4096u * 1024u)   /* frames waiting for the pacing budget (v9; v10: 4 MB) */
#define PACE_MAX        256u              /* v10: ~8 s at 30 fps */
#define WIN_N           30u               /* 10 s windows kept: 5 min */
#define WIN_US          10000000u
#define BIG_LOG_MAX     6u
#define BIG_BYTES       32768u            /* a "large" frame for the status */

static const char *g_mode, *g_status_path, *g_ring_path, *g_bridge_path, *g_dmdt_path, *g_ack_path;
static const char *g_flush_dev, *g_kf_req_path, *g_run_dir;
static unsigned long g_wait_ms, g_settle_ms, g_cp_wait_ms;
static const char *g_cp_ready_path;
static unsigned long g_sync_hold_ms, g_sync_repeat_ms;
static double g_pace_bps, g_pace_burst;  /* v9 pacing: bytes per second into the ring, 0 = off; burst in bytes */
static uint64_t g_pace_gap_us;           /* v10: least time between two frames into the ring, 0 = off */
static double g_drain_bps, g_drain_burst, g_dtok;   /* v10: byte budget for draining a 3/4 full queue */
static uint64_t g_dtok_t;
static uint64_t g_pace_last_us;          /* v10: when the last frame went into the ring */
static int g_kf_bridge_on;               /* v10: 1 = the bridge's IDR request sends K/C to the hook */
static uint8_t g_kf_byte = 'K';   /* K = focus cycle, C = resend setup response (v5) */
static unsigned long g_kf_take_ms, g_kf_min_ms;
static uint64_t g_kf_take_due;   /* one request this long after the takeover; 0 = none pending */
static uint64_t g_kf_last_us;    /* last 'K' sent */
static int g_kf_waiting;         /* a 'K' went out and no IDR has come since */
static unsigned g_idle_ms;       /* the hook writes a frame at once: a pause this long ends it */
static volatile sig_atomic_t g_stop;
static const char *g_lease_path;         /* MU1367: shared video cache lock (cpmap_resources.h protocol) */
static int g_lease_fd = -1;
static char g_policy[96] = "-";          /* MU1367: why MOST may or may not be taken */
static void lease_drop(void);

/* ---------------------------------------------------------------- time */

static uint64_t now_us(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000u + (uint64_t)ts.tv_nsec / 1000u;
}

/* NTP 32.32 from the monotonic clock: the bridge only uses differences (PTS = delta x 90 kHz). */
static uint64_t now_ntp(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ((uint64_t)ts.tv_sec << 32) | (uint64_t)(((uint64_t)ts.tv_nsec << 32) / 1000000000u);
}

static void sleep_ms(unsigned ms)
{
    struct timespec ts = { (time_t)(ms / 1000u), (long)(ms % 1000u) * 1000000L };
    while (nanosleep(&ts, &ts) != 0 && errno == EINTR && !g_stop) {}
}

static const char *env_or(const char *name, const char *def)
{
    const char *v = getenv(name);
    return (v != NULL && *v != '\0') ? v : def;
}

static unsigned long env_ul(const char *name, unsigned long def, unsigned long lo, unsigned long hi)
{
    const char *v = getenv(name);
    char *end;
    unsigned long x;
    if (v == NULL || *v == '\0') return def;
    x = strtoul(v, &end, 10);
    return (*end != '\0' || x < lo || x > hi) ? def : x;
}

/* Settings file: only mode and pacing, never a path, so the file cannot point the feeder at another program. */
static const char *const CONF_KEYS[] = { "PMCP_AA_MODE", "PMCP_AA_RATE_KBPS", "PMCP_AA_BURST_KB", "PMCP_AA_IDLE_MS",
                                         "PMCP_AA_KF_TAKE_MS", "PMCP_AA_KF_MIN_MS", "PMCP_AA_WAIT_MS",
                                         "PMCP_AA_SETTLE_MS", "PMCP_AA_KF_METHOD", "PMCP_AA_SYNC_HOLD_MS",
                                         "PMCP_AA_SYNC_REPEAT_MS", "PMCP_AA_CP_WAIT_MS", "PMCP_AA_PACE_KBPS",
                                         "PMCP_AA_PACE_BURST_KB", "PMCP_AA_PACE_GAP_MS", "PMCP_AA_KF_BRIDGE",
                                         "PMCP_AA_PACE_DRAIN_KBPS", NULL };

static void load_conf(const char *path)
{
    char line[128];
    FILE *f = fopen(path, "r");
    if (f == NULL) return;
    while (fgets(line, (int)sizeof line, f) != NULL) {
        char *eq = strchr(line, '='), *end;
        int i;
        if (line[0] == '#' || eq == NULL) continue;
        *eq = '\0';
        end = eq + 1 + strcspn(eq + 1, "\r\n");
        *end = '\0';
        for (i = 0; CONF_KEYS[i] != NULL; ++i)
            if (strcmp(line, CONF_KEYS[i]) == 0) (void)setenv(line, eq + 1, 0);
    }
    fclose(f);
}

/* ---------------------------------------------------------------- statistics */

typedef struct {
    uint64_t t_start_us, t_first_frame_us;
    unsigned long frames, idrs, b_slices, dropped_big, dropped_unparsed, ring_writes, avcc_writes;
    unsigned long bytes_in, max_idr, max_p, sum_p, p_count;
    uint64_t last_idr_us, idr_gap_min, idr_gap_max, idr_gap_sum;
    unsigned long idr_gaps;
    unsigned long sec_bytes, sec_max_bytes; uint64_t sec_start_us;
    unsigned long acks_sent, ack_delayed, ack_delay_max_ms;
    int sps_ok, profile, constraints, level, width, height, refs, poc_type, frame_mbs_only, vui;
    int cabac, pps_ok;
    char most_state[64], last_error[96];
    int dmdt_release_rc, dmdt_restore_rc;
    long bridge_pid;
    unsigned long kf_bridge, kf_take, kf_sent, kf_skipped, kf_failed, kf_idr_ms_last, kf_idr_ms_max, kf_no_idr;
    unsigned long kf_ignored;                  /* v10: bridge requests not passed on */
    unsigned long take_wait_ms;
    char take_wait_reason[40];
    char ring_file[48];                        /* v8: what happened to an existing ring file */
    uint64_t t_taken_us;                       /* MOST taken (ring ready) */
    unsigned long idr_log_ms[IDR_LOG_MAX], idr_log_bytes[IDR_LOG_MAX], idr_logged;
    unsigned long sync_state;                  /* 0 off/not yet, 1 holding, 2 done */
    unsigned long sync_repeats, sync_held, sync_hold_ms, sync_overflow;
    /* v9 */
    unsigned long pace_delayed, pace_wait_max_ms, pace_q_hi, pace_overflow;
    unsigned long pace_drain;                 /* v10: frames out over the byte budget to drain the queue */
    uint64_t last_frame_us, gap_max_us, gap_max_at_us;
    unsigned long gaps_1s, gaps_3s;
    unsigned long win[WIN_N], win_kb[WIN_N];  /* frames / KB per 10 s window, circular */
    uint64_t win_no;                          /* absolute number of the current window, from the first frame */
    unsigned long big_n, big_log_s[BIG_LOG_MAX], big_log_kb[BIG_LOG_MAX];
} stats_t;

static stats_t S;

static void set_error(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(S.last_error, sizeof S.last_error, fmt, ap);
    va_end(ap);
}

/* <rundir>/name */
static const char *run_path(char *buf, size_t n, const char *name)
{
    snprintf(buf, n, "%s/%s", g_run_dir, name);
    return buf;
}

/* Copies a small text file into the status, each line prefixed. */
static void copy_lines(FILE *f, const char *path, const char *prefix)
{
    char line[256];
    FILE *in = fopen(path, "r");
    if (in == NULL) return;
    while (fgets(line, (int)sizeof line, in) != NULL) {
        line[strcspn(line, "\r\n")] = '\0';
        fprintf(f, "%s%s\n", prefix, line);
    }
    fclose(in);
}

/* v9: moves the 10 s windows on to the one holding t (empty windows count 0). */
static void win_advance(uint64_t t)
{
    uint64_t w;
    if (S.t_first_frame_us == 0u || t < S.t_first_frame_us) return;
    w = (t - S.t_first_frame_us) / WIN_US;
    if (w <= S.win_no) return;
    if (w - S.win_no >= WIN_N) { memset(S.win, 0, sizeof S.win); memset(S.win_kb, 0, sizeof S.win_kb); }
    else while (S.win_no < w) { S.win_no++; S.win[S.win_no % WIN_N] = 0; S.win_kb[S.win_no % WIN_N] = 0; }
    S.win_no = w;
}

/* Seconds since the MOST takeover (or the start, in analysis). */
static unsigned long since_take_s(uint64_t t)
{
    uint64_t base = S.t_taken_us ? S.t_taken_us : S.t_start_us;
    return t > base ? (unsigned long)((t - base) / 1000000u) : 0ul;
}

static void write_status_v9(FILE *f, uint64_t t)
{
    unsigned long k, first;
    if (g_pace_bps > 0.0 || g_pace_gap_us != 0u)
        fprintf(f, "dawkowanie: %.0f kbit/s zapas %.0f KB odstep %lums opoznione=%lu czekanie max=%lums kolejka max=%lu/%u "
                "oproznianie=%lu przepelnienie=%lu\n",
                g_pace_bps * 8.0 / 1000.0, g_pace_burst / 1000.0, (unsigned long)(g_pace_gap_us / 1000u), S.pace_delayed,
                S.pace_wait_max_ms, S.pace_q_hi, PACE_MAX, S.pace_drain, S.pace_overflow);
    else
        fprintf(f, "dawkowanie: wylaczone\n");
    if (S.last_frame_us)
        fprintf(f, "przerwy: ostatnia klatka %lums temu, najdluzsza %lums (%lus po przejeciu) >1s=%lu >3s=%lu\n",
                (unsigned long)((t - S.last_frame_us) / 1000u), (unsigned long)(S.gap_max_us / 1000u),
                since_take_s(S.gap_max_at_us), S.gaps_1s, S.gaps_3s);
    if (S.t_first_frame_us) {
        win_advance(t);
        first = S.win_no + 1u > WIN_N ? (unsigned long)(S.win_no + 1u - WIN_N) : 0ul;
        fprintf(f, "klatki co 10s (od %lus, najstarsze->teraz):", (unsigned long)(first * 10u));
        for (k = first; k <= S.win_no; ++k) fprintf(f, " %lu", S.win[k % WIN_N]);
        fprintf(f, "\nKB co 10s:");
        for (k = first; k <= S.win_no; ++k) fprintf(f, " %lu", S.win_kb[k % WIN_N]);
        fprintf(f, "\n");
    }
    fprintf(f, "duze klatki >=%uKB: %lu", BIG_BYTES / 1024u, S.big_n);
    if (S.big_n) {
        unsigned long n = S.big_n < BIG_LOG_MAX ? S.big_n : BIG_LOG_MAX;
        fprintf(f, " ostatnie (s po przejeciu/KB):");
        for (k = S.big_n - n; k < S.big_n; ++k) fprintf(f, " %lu/%lu", S.big_log_s[k % BIG_LOG_MAX], S.big_log_kb[k % BIG_LOG_MAX]);
    }
    fprintf(f, "\n");
}

static void write_status(void)
{
    char pb[256];
    char tmp[256];
    FILE *f;
    uint64_t t = now_us();
    double secs = (double)(t - S.t_start_us) / 1e6;
    double fsecs = S.t_first_frame_us ? (double)(t - S.t_first_frame_us) / 1e6 : 0.0;
    snprintf(tmp, sizeof tmp, "%s.tmp", g_status_path);
    f = fopen(tmp, "w");
    if (f == NULL) return;
    fprintf(f, "PMCP AA FEEDER v%s mode=%s czas=%.0fs\n", FEEDER_VERSION, g_mode, secs);
    fprintf(f, "mu1367: policy=%s lease=%d\n", g_policy, g_lease_fd >= 0);
    fprintf(f, "klatki=%lu IDR=%lu fps=%.1f B-slice=%lu\n", S.frames, S.idrs,
            fsecs > 0.5 ? (double)S.frames / fsecs : 0.0, S.b_slices);
    if (S.sps_ok)
        fprintf(f, "SPS profil=%d constr=0x%02x poziom=%d %dx%d refs=%d poc=%d progr=%d vui=%d\n",
                S.profile, S.constraints, S.level, S.width, S.height, S.refs, S.poc_type,
                S.frame_mbs_only, S.vui);
    else
        fprintf(f, "SPS brak\n");
    fprintf(f, "PPS %s\n", S.pps_ok ? (S.cabac ? "CABAC" : "CAVLC") : "brak");
    if (S.idr_gaps)
        fprintf(f, "IDR co ms: min=%llu sr=%llu max=%llu\n", (unsigned long long)(S.idr_gap_min / 1000u),
                (unsigned long long)(S.idr_gap_sum / S.idr_gaps / 1000u),
                (unsigned long long)(S.idr_gap_max / 1000u));
    else
        fprintf(f, "IDR co ms: -\n");
    fprintf(f, "B max IDR=%lu P sr=%lu P max=%lu\n", S.max_idr, S.p_count ? S.sum_p / S.p_count : 0ul, S.max_p);
    fprintf(f, "kbit/s sr=%.0f max1s=%lu\n", fsecs > 0.5 ? (double)S.bytes_in * 8.0 / fsecs / 1000.0 : 0.0,
            S.sec_max_bytes * 8ul / 1000ul);
    fprintf(f, "ack=%lu opoznione=%lu max=%lums\n", S.acks_sent, S.ack_delayed, S.ack_delay_max_ms);
    fprintf(f, "odrzucone duze=%lu nieparsowalne=%lu\n", S.dropped_big, S.dropped_unparsed);
    fprintf(f, "MOST %s ring=%lu avcC=%lu straznik=%ld dmdt=%d/%d\n", S.most_state[0] ? S.most_state : "-",
            S.ring_writes, S.avcc_writes, S.bridge_pid, S.dmdt_release_rc, S.dmdt_restore_rc);
    fprintf(f, "IDR prosby (%s): bridge=%lu start=%lu wyslane=%lu pominiete=%lu bledy=%lu IDR po %lums (max %lums) bez IDR=%lu"
            " zignorowane=%lu%s\n",
            g_kf_byte == 'C' ? "config" : "focus", S.kf_bridge, S.kf_take, S.kf_sent, S.kf_skipped, S.kf_failed, S.kf_idr_ms_last,
            S.kf_idr_ms_max, S.kf_no_idr, S.kf_ignored, g_kf_bridge_on ? "" : " (prosby bridge nie ida do telefonu)");
    fprintf(f, "blad: %s\n", S.last_error[0] ? S.last_error : "-");
    if (S.ring_file[0]) fprintf(f, "plik ringu: %s\n", S.ring_file);
    if (S.take_wait_ms) fprintf(f, "czekanie przed przejeciem MOST: %lums (%s)\n", S.take_wait_ms,
                                S.take_wait_reason[0] ? S.take_wait_reason : "-");
    if (g_sync_hold_ms)
        fprintf(f, "sync startu: %s powtorki IDR=%lu wstrzymane klatki=%lu wstrzymanie=%lums przepelnienie=%lu (plan %lums co %lums)\n",
                S.sync_state == 0 ? "czeka na IDR" : (S.sync_state == 1 ? "TRWA" : "zrobiony"), S.sync_repeats, S.sync_held,
                S.sync_hold_ms, S.sync_overflow, g_sync_hold_ms, g_sync_repeat_ms);
    if (S.idr_logged) {
        unsigned long k;
        fprintf(f, "pierwsze IDR (ms po przejeciu/KB):");
        for (k = 0; k < S.idr_logged && k < IDR_LOG_MAX; ++k)
            fprintf(f, " %lu/%lu", S.idr_log_ms[k], (S.idr_log_bytes[k] + 512ul) / 1024ul);
        fprintf(f, "\n");
    }
    write_status_v9(f, t);
    copy_lines(f, run_path(pb, sizeof pb, "pmcp-aa-bridge.txt"), "");
    copy_lines(f, run_path(pb, sizeof pb, "pmcp-aa-sessions.txt"), "poprzednia ");
    if (fclose(f) == 0) rename(tmp, g_status_path);
}

/* ---------------------------------------------------------------- H.264 bit reader */

typedef struct { uint8_t b[PS_MAX]; unsigned n, pos; int err; } bits_t;

/* Copy a NAL payload without its header byte and without emulation prevention bytes. */
static void bits_init(bits_t *r, const uint8_t *nal, unsigned len)
{
    unsigned i, zeros = 0;
    r->n = r->pos = 0; r->err = 0;
    for (i = 1; i < len && r->n < sizeof r->b; ++i) {
        if (zeros >= 2 && nal[i] == 3) { zeros = 0; continue; }
        zeros = nal[i] == 0 ? zeros + 1 : 0;
        r->b[r->n++] = nal[i];
    }
}

static unsigned bit1(bits_t *r)
{
    unsigned v;
    if (r->pos >= r->n * 8u) { r->err = 1; return 0; }
    v = (r->b[r->pos >> 3] >> (7u - (r->pos & 7u))) & 1u;
    r->pos++;
    return v;
}

static unsigned bitsn(bits_t *r, unsigned n)
{
    unsigned v = 0;
    while (n--) v = (v << 1) | bit1(r);
    return v;
}

static unsigned ue(bits_t *r)
{
    unsigned zeros = 0;
    while (!r->err && bit1(r) == 0) if (++zeros > 31) { r->err = 1; return 0; }
    return zeros ? ((1u << zeros) - 1u + bitsn(r, zeros)) : 0u;
}

static int se(bits_t *r)
{
    unsigned k = ue(r);
    return (k & 1u) ? (int)((k + 1u) / 2u) : -(int)(k / 2u);
}

static void skip_scaling_list(bits_t *r, unsigned size)
{
    int last = 8, next = 8;
    unsigned j;
    for (j = 0; j < size && !r->err; ++j) {
        if (next != 0) next = (last + se(r) + 256) % 256;
        last = next == 0 ? last : next;
    }
}

static void parse_sps(const uint8_t *nal, unsigned len)
{
    bits_t r;
    unsigned chroma = 1, i, w_mbs, h_map, cl = 0, cr = 0, ct = 0, cb = 0;
    bits_init(&r, nal, len);
    S.profile = (int)bitsn(&r, 8); S.constraints = (int)bitsn(&r, 8); S.level = (int)bitsn(&r, 8);
    (void)ue(&r);
    if (S.profile == 100 || S.profile == 110 || S.profile == 122 || S.profile == 244 || S.profile == 44 ||
        S.profile == 83 || S.profile == 86 || S.profile == 118 || S.profile == 128) {
        chroma = ue(&r);
        if (chroma == 3) (void)bit1(&r);
        (void)ue(&r); (void)ue(&r); (void)bit1(&r);
        if (bit1(&r))
            for (i = 0; i < (chroma != 3 ? 8u : 12u); ++i)
                if (bit1(&r)) skip_scaling_list(&r, i < 6 ? 16u : 64u);
    }
    (void)ue(&r);
    S.poc_type = (int)ue(&r);
    if (S.poc_type == 0) (void)ue(&r);
    else if (S.poc_type == 1) {
        unsigned n;
        (void)bit1(&r); (void)se(&r); (void)se(&r);
        n = ue(&r);
        for (i = 0; i < n && !r.err; ++i) (void)se(&r);
    }
    S.refs = (int)ue(&r);
    (void)bit1(&r);
    w_mbs = ue(&r) + 1u; h_map = ue(&r) + 1u;
    S.frame_mbs_only = (int)bit1(&r);
    if (!S.frame_mbs_only) (void)bit1(&r);
    (void)bit1(&r);
    if (bit1(&r)) { cl = ue(&r); cr = ue(&r); ct = ue(&r); cb = ue(&r); }
    S.vui = (int)bit1(&r);
    S.width = (int)(w_mbs * 16u - 2u * (cl + cr));
    S.height = (int)((2u - (unsigned)S.frame_mbs_only) * h_map * 16u - 2u * (2u - (unsigned)S.frame_mbs_only) * (ct + cb));
    S.sps_ok = !r.err;
    (void)chroma;
}

static void parse_pps(const uint8_t *nal, unsigned len)
{
    bits_t r;
    bits_init(&r, nal, len);
    (void)ue(&r); (void)ue(&r);
    S.cabac = (int)bit1(&r);
    S.pps_ok = !r.err;
}

/* slice_type of a VCL NAL: 0/5 P, 1/6 B, 2/7 I. -1 if unreadable. */
static int slice_type(const uint8_t *nal, unsigned len, unsigned *first_mb)
{
    bits_t r;
    unsigned t;
    bits_init(&r, nal, len < 16u ? len : 16u);
    *first_mb = ue(&r);
    t = ue(&r);
    return r.err ? -1 : (int)(t % 5u);
}

/* ---------------------------------------------------------------- ring */

static volatile uint8_t *g_ring;
static uint32_t g_seq;
static unsigned long g_frame_no;

static inline void wr32(volatile uint8_t *p, uint32_t v) { *(volatile uint32_t *)(void *)p = v; }
static inline uint32_t rd32(const volatile uint8_t *p) { return *(const volatile uint32_t *)(const void *)p; }

static void ring_put(uint32_t type, const uint8_t *data, unsigned len, uint32_t frame_no)
{
    volatile uint8_t *slot;
    uint64_t ts = now_ntp();
    if (g_ring == NULL || len == 0u || len > RING_DATA_MAX) return;
    g_seq = g_seq + 1u == 0u ? 1u : g_seq + 1u;
    slot = g_ring + RING_HDR_SIZE + ((g_seq - 1u) & (RING_SLOTS - 1u)) * RING_SLOT_SIZE;
    wr32(slot + 0x00, 0u);
    __sync_synchronize();
    wr32(slot + 0x04, type);
    wr32(slot + 0x08, len);
    wr32(slot + 0x0c, 0u);
    wr32(slot + 0x10, frame_no);
    wr32(slot + 0x14, (uint32_t)ts);
    wr32(slot + 0x18, (uint32_t)(ts >> 32));
    memcpy((void *)(slot + 0x1c), data, len);
    __sync_synchronize();
    wr32(slot + 0x00, g_seq);
    __sync_synchronize();
    wr32(g_ring + 0x0c, g_seq);
    if (type == RING_TYPE_AVCC) S.avcc_writes++; else S.ring_writes++;
}

/* ---------------------------------------------------------------- SPS/PPS -> avcC */

static uint8_t g_sps[PS_MAX], g_pps[PS_MAX];
static unsigned g_sps_len, g_pps_len;
static int g_avcc_dirty;

static void keep_param_set(uint8_t *dst, unsigned *dst_len, const uint8_t *nal, unsigned len)
{
    if (len > PS_MAX) { set_error("SPS/PPS za dlugi %u", len); return; }
    if (len == *dst_len && memcmp(dst, nal, len) == 0) return;
    memcpy(dst, nal, len); *dst_len = len; g_avcc_dirty = 1;
}

static void send_avcc(void)
{
    uint8_t a[11u + 2u * PS_MAX];
    unsigned n = 0;
    if (!g_avcc_dirty || g_sps_len < 4u || g_pps_len == 0u) return;
    a[n++] = 1; a[n++] = g_sps[1]; a[n++] = g_sps[2]; a[n++] = g_sps[3];
    a[n++] = 0xff;                       /* 4-byte NAL lengths */
    a[n++] = 0xe1;                       /* one SPS */
    a[n++] = (uint8_t)(g_sps_len >> 8); a[n++] = (uint8_t)g_sps_len;
    memcpy(a + n, g_sps, g_sps_len); n += g_sps_len;
    a[n++] = 1;                          /* one PPS */
    a[n++] = (uint8_t)(g_pps_len >> 8); a[n++] = (uint8_t)g_pps_len;
    memcpy(a + n, g_pps, g_pps_len); n += g_pps_len;
    ring_put(RING_TYPE_AVCC, a, n, 0u);
    g_avcc_dirty = 0;
}

/* ---------------------------------------------------------------- ACK pacing */

static int g_ack_fd = -1;
static uint64_t g_ack_due[ACK_QUEUE], g_ack_queued_at[ACK_QUEUE];
static unsigned g_ack_head, g_ack_count;
static double g_tokens;          /* bytes the bridge may still take without queueing */
static uint64_t g_tokens_t;
static double g_rate_bps, g_burst;

static void ack_connect(void)
{
    struct sockaddr_un a;
    int fd;
    if (g_ack_fd >= 0) return;
    fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return;
    memset(&a, 0, sizeof a);
    a.sun_family = AF_UNIX;
    strncpy(a.sun_path, g_ack_path, sizeof a.sun_path - 1u);
    if (connect(fd, (struct sockaddr *)&a, sizeof a) != 0) { close(fd); return; }
    (void)fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);
    g_ack_fd = fd;
}

/* Sends every ACK due by t (UINT64_MAX: all of them, when the queue is full); delays are measured to now. */
static void ack_send_due(uint64_t t)
{
    uint64_t now = now_us();
    while (g_ack_count > 0u && g_ack_due[g_ack_head] <= t) {
        unsigned long d_ms = (unsigned long)((now - g_ack_queued_at[g_ack_head]) / 1000u);
        ack_connect();
        if (g_ack_fd >= 0) {
            uint8_t one = 1;
            ssize_t w = send(g_ack_fd, &one, 1, 0);
            if (w != 1 && errno != EAGAIN && errno != EWOULDBLOCK) { close(g_ack_fd); g_ack_fd = -1; }
            if (w == 1) S.acks_sent++;
        }
        if (d_ms > 1ul) S.ack_delayed++;
        if (d_ms > S.ack_delay_max_ms) S.ack_delay_max_ms = d_ms;
        g_ack_head = (g_ack_head + 1u) % ACK_QUEUE;
        g_ack_count--;
    }
}

/* One ACK per frame; when the frame overdraws the byte budget, the ACK waits until the budget has
 * refilled, so the phone (which only sends a few frames ahead of its ACKs) slows down. */
static void ack_schedule(unsigned bytes)
{
    uint64_t t = now_us(), due = t, last;
    unsigned idx;
    if (g_rate_bps > 0.0) {
        g_tokens += (double)(t - g_tokens_t) * g_rate_bps / 1e6;
        if (g_tokens > g_burst) g_tokens = g_burst;
        g_tokens_t = t;
        g_tokens -= (double)bytes;
        if (g_tokens < 0.0) due = t + (uint64_t)(-g_tokens * 1e6 / g_rate_bps);
    }
    if (g_ack_count == ACK_QUEUE) ack_send_due(UINT64_MAX);
    last = g_ack_count ? g_ack_due[(g_ack_head + g_ack_count - 1u) % ACK_QUEUE] : 0u;
    if (due < last) due = last;
    idx = (g_ack_head + g_ack_count) % ACK_QUEUE;
    g_ack_due[idx] = due; g_ack_queued_at[idx] = t;
    g_ack_count++;
    ack_send_due(t);
}

/* ---------------------------------------------------------------- MOST takeover */

static pid_t g_guard_pid = -1;
static int g_guard_fd = -1;      /* write end; its EOF tells the guardian to give MOST back */

static int run_wait_argv(char *const argv[])
{
    pid_t pid = fork();
    int st, i;
    if (pid < 0) return -1;
    if (pid == 0) {
        int nul = open("/dev/null", O_RDWR);
        if (nul >= 0) { dup2(nul, 0); dup2(nul, 1); dup2(nul, 2); }
        unsetenv("LD_PRELOAD");
        setenv("IPL_CONFIG_DIR", "/etc/eso/production", 1);
        setenv("LD_LIBRARY_PATH", "/mnt/app/root/lib-target:/eso/lib:/mnt/app/usr/lib:/mnt/app/armle/lib:"
               "/mnt/app/armle/lib/dll:/mnt/app/armle/usr/lib", 1);
        execv(argv[0], argv);
        _exit(127);
    }
    for (i = 0; i < 300; ++i) {               /* dmdt has taken up to ~1 s on the car; give it 3 s */
        pid_t r = waitpid(pid, &st, WNOHANG);
        if (r == pid) return WIFEXITED(st) ? WEXITSTATUS(st) : -2;
        if (r < 0 && errno != EINTR) return -1;
        sleep_ms(10);
    }
    kill(pid, SIGKILL);
    (void)waitpid(pid, &st, 0);
    return -3;
}

static int dmdt(const char *a, const char *b, const char *c)
{
    char *argv[5];
    argv[0] = (char *)g_dmdt_path; argv[1] = (char *)a; argv[2] = (char *)b; argv[3] = (char *)c; argv[4] = NULL;
    return run_wait_argv(argv);
}

/* Is pid running the program named name? 1 yes, 0 no (another program: stale pid file), -1 unknown (no /proc). */
static int pid_is(long pid, const char *name)
{
    char path[64], exe[256];
    int fd, n;
    snprintf(path, sizeof path, "/proc/%ld/exefile", pid);
    if ((fd = open(path, O_RDONLY)) < 0) return -1;
    n = (int)read(fd, exe, sizeof exe - 1u);
    close(fd);
    if (n <= 0) return -1;
    exe[n] = '\0';
    return strstr(exe, name) != NULL;
}

/* A live altscreen-most-bridge other than pid `ours`? 1 yes, 0 no, -1 unknown (no /proc). */
static int other_bridge_alive(long ours)
{
    DIR *d = opendir("/proc");
    struct dirent *e;
    int seen = 0, found = 0;
    if (d == NULL) return -1;
    while (!found && (e = readdir(d)) != NULL) {
        char *end;
        long pid = strtol(e->d_name, &end, 10);
        int r;
        if (*end != '\0' || pid <= 0) continue;
        r = pid_is(pid, "altscreen-most-bridge");
        if (r >= 0) seen = 1;
        if (r == 1 && pid != ours) found = 1;
    }
    closedir(d);
    return found ? 1 : (seen ? 0 : -1);
}

static int pid_alive(const char *pidfile)
{
    char buf[32];
    long pid;
    int fd = open(pidfile, O_RDONLY), n;
    if (fd < 0) return 0;
    n = (int)read(fd, buf, sizeof buf - 1u);
    close(fd);
    if (n <= 0) return 0;
    buf[n] = '\0';
    pid = strtol(buf, NULL, 10);
    return pid > 0 && kill((pid_t)pid, 0) == 0;
}

/* Puts the stock VW map back on the cluster video output (supervisor's "oem-most-restore"). */
static void dmdt_restore(void)
{
    S.dmdt_restore_rc = dmdt("dc", "70", "33");
    if (dmdt("sc", "4", "70") != 0 && S.dmdt_restore_rc == 0) S.dmdt_restore_rc = -4;
}

/*
 * Guardian: a child that owns the bridge. It runs the bridge and waits on a pipe from the feeder;
 * when the pipe closes (feeder exits, crashes or is SIGKILLed by the hook after its 300 ms grace)
 * or the bridge exits, it stops the bridge as the supervisor does and gives MOST back to the VW
 * encoder. So the bridge can never outlive the feeder and keep writing to isoTX2.
 */
/* Bridge output, read by the guardian: counters and the last lines, rewritten to <rundir>/pmcp-aa-bridge.txt. */
typedef struct {
    unsigned long resets, idr_req, idr_resume, wait_writer, most_fail, lines;
    char last[2][160], metrics[160];
    char buf[512];
    unsigned len;
    int dirty;
} bridge_out_t;

static void bo_line(bridge_out_t *o, const char *l)
{
    o->lines++;
    if (strstr(l, "latency-reset")) o->resets++;
    if (strstr(l, "latency-request-idr") || strstr(l, "IDR request")) o->idr_req++;
    if (strstr(l, "resume-idr")) o->idr_resume++;
    if (strstr(l, "latency-wait-writer")) o->wait_writer++;
    if (strstr(l, "MOST write failed")) o->most_fail++;
    if (strstr(l, "bridge: metrics")) snprintf(o->metrics, sizeof o->metrics, "%s", l);
    else { memcpy(o->last[0], o->last[1], sizeof o->last[0]); snprintf(o->last[1], sizeof o->last[1], "%s", l); }
    o->dirty = 1;
}

static void bo_read(bridge_out_t *o, int fd)
{
    ssize_t n;
    unsigned i, s;
    if (fd < 0) return;
    while ((n = read(fd, o->buf + o->len, sizeof o->buf - 1u - o->len)) > 0) {
        o->len += (unsigned)n;
        for (i = 0, s = 0; i < o->len; ++i)
            if (o->buf[i] == '\n') { o->buf[i] = '\0'; bo_line(o, o->buf + s); s = i + 1u; }
        if (s > 0u) { memmove(o->buf, o->buf + s, o->len - s); o->len -= s; }
        if (o->len == sizeof o->buf - 1u) { o->buf[o->len] = '\0'; bo_line(o, o->buf); o->len = 0; }   /* overlong line */
    }
}

static void bo_write(bridge_out_t *o)
{
    char path[256], tmp[260];
    FILE *f;
    if (!o->dirty) return;
    run_path(path, sizeof path, "pmcp-aa-bridge.txt");
    snprintf(tmp, sizeof tmp, "%s.tmp", path);
    f = fopen(tmp, "w");
    if (f == NULL) return;
    fprintf(f, "bridge: reset_opoznienia=%lu prosba_idr=%lu wznow_po_idr=%lu czeka_na_zapis=%lu blad_MOST=%lu linie=%lu\n",
            o->resets, o->idr_req, o->idr_resume, o->wait_writer, o->most_fail, o->lines);
    if (o->metrics[0]) fprintf(f, "bridge metryki: %s\n", o->metrics);
    if (o->last[0][0]) fprintf(f, "bridge: %s\n", o->last[0]);
    if (o->last[1][0]) fprintf(f, "bridge: %s\n", o->last[1]);
    if (fclose(f) == 0) rename(tmp, path);
    o->dirty = 0;
}

/*
 * Guardian: a child that owns the bridge. It runs the bridge and waits on a pipe from the feeder;
 * when the pipe closes (feeder exits, crashes or is SIGKILLed by the hook after its 300 ms grace)
 * or the bridge exits, it stops the bridge as the supervisor does and gives MOST back to the VW
 * encoder. So the bridge can never outlive the feeder and keep writing to isoTX2.
 * v4: <rundir>/pmcp-aa-guard.pid exists from the start until the dmdt restore is done, so the next session waits for
 * it; the bridge's stdout/stderr come through a pipe (bridge_out_t).
 */
static void guardian(int rfd)
{
    static bridge_out_t bo;
    pid_t b;
    int st, i, bp[2] = { -1, -1 };
    char c, gpath[256], bpath[256];
    uint64_t last_write = 0;
    signal(SIGTERM, SIG_IGN); signal(SIGINT, SIG_IGN); signal(SIGHUP, SIG_IGN); signal(SIGPIPE, SIG_IGN);
    for (i = 3; i < 256; ++i) if (i != rfd) close(i);   /* no copy of the hook's sockets may outlive the feeder */
    run_path(gpath, sizeof gpath, "pmcp-aa-guard.pid");
    run_path(bpath, sizeof bpath, "pmcp-aa-bridge.pid");
    {
        char pf[32];
        int fd = open(gpath, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        snprintf(pf, sizeof pf, "%ld\n", (long)getpid());
        if (fd >= 0) { (void)write(fd, pf, strlen(pf)); close(fd); }
    }
    if (pipe(bp) != 0) { bp[0] = bp[1] = -1; }
    b = fork();
    if (b == 0) {
        int nul = open("/dev/null", O_RDWR);
        close(rfd);
        if (bp[1] >= 0) { dup2(bp[1], 1); dup2(bp[1], 2); close(bp[0]); close(bp[1]); }
        else if (nul >= 0) { dup2(nul, 1); dup2(nul, 2); }
        if (nul >= 0) { dup2(nul, 0); if (nul > 2) close(nul); }
        signal(SIGTERM, SIG_DFL); signal(SIGINT, SIG_DFL); signal(SIGHUP, SIG_DFL); signal(SIGPIPE, SIG_DFL);
        unsetenv("LD_PRELOAD");
        execl(g_bridge_path, g_bridge_path, (char *)NULL);
        _exit(127);
    }
    if (bp[1] >= 0) close(bp[1]);
    if (bp[0] >= 0) (void)fcntl(bp[0], F_SETFL, fcntl(bp[0], F_GETFL, 0) | O_NONBLOCK);
    if (b > 0) {
        char pf[64];
        int fd;
        snprintf(pf, sizeof pf, "%ld\n", (long)b);
        fd = open(bpath, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) { (void)write(fd, pf, strlen(pf)); close(fd); }
        (void)fcntl(rfd, F_SETFL, fcntl(rfd, F_GETFL, 0) | O_NONBLOCK);
        for (;;) {                                /* pipe EOF or bridge exit, checked every 20 ms */
            ssize_t n = read(rfd, &c, 1);
            uint64_t now = now_us();
            bo_read(&bo, bp[0]);
            if (now - last_write >= 1000000u) { bo_write(&bo); last_write = now; }
            if (n == 0 || (n < 0 && errno != EAGAIN && errno != EINTR)) break;
            if (waitpid(b, &st, WNOHANG) == b) { b = -1; break; }
            sleep_ms(20);
        }
        if (b > 0) {
            kill(b, SIGTERM);
            for (i = 0; i < 50 && waitpid(b, &st, WNOHANG) == 0; ++i) { bo_read(&bo, bp[0]); sleep_ms(20); }
            if (i == 50) {
                int fd2 = open(g_flush_dev, O_WRONLY);
                if (fd2 >= 0) { (void)write(fd2, "flush(0)\n", 9); close(fd2); }
                for (i = 0; i < 50 && waitpid(b, &st, WNOHANG) == 0; ++i) { bo_read(&bo, bp[0]); sleep_ms(20); }
                if (i == 50) { kill(b, SIGKILL); (void)waitpid(b, &st, 0); }
            }
        }
        bo_read(&bo, bp[0]);
        bo.dirty = 1;
        bo_write(&bo);
        (void)unlink(bpath);
    }
    sleep_ms(250);
    dmdt_restore();
    (void)unlink(gpath);                          /* only now may the next session take MOST */
    _exit(0);
}

static void most_restore(void)
{
    int st, i;
    if (g_ring != NULL) { munmap((void *)g_ring, RING_FILE_SIZE); g_ring = NULL; }
    if (g_guard_fd >= 0) { close(g_guard_fd); g_guard_fd = -1; }
    if (g_guard_pid > 0) {                       /* short wait only: the guardian finishes on its own */
        for (i = 0; i < 10 && waitpid(g_guard_pid, &st, WNOHANG) == 0; ++i) sleep_ms(10);
        g_guard_pid = -1;
        snprintf(S.most_state, sizeof S.most_state, "oddawane (straznik)");
    }
    lease_drop();
}

/* Why MOST cannot be taken now, or NULL. */
static const char *busy_reason(void)
{
    char pb[256];
    if (access(g_cp_ready_path, F_OK) == 0 && other_bridge_alive(-1) != 0) return "bridge CarPlay";
    if (pid_alive(run_path(pb, sizeof pb, "pmcp-aa-guard.pid")) || pid_alive(run_path(pb, sizeof pb, "pmcp-aa-bridge.pid")))
        return "poprzednia sesja AA";
    return NULL;
}

/* v8: an existing ring of the right size and magic (CarPlay's, still mapped by dio_manager, or our earlier one) is
 * reused in place: last sequence and every slot sequence to 0, so the bridge (wants sequence 1) replays nothing. Unlinking
 * it would leave its 16 MB used while mapped and the new ring would not fit on /ramdisk. Anything else: unlinked. */
static int ring_prepare(void)
{
    struct stat sb;
    int fd = open(g_ring_path, O_RDWR);
    if (fd < 0) {
        if (errno == ENOENT) { snprintf(S.ring_file, sizeof S.ring_file, "nowy"); return 0; }
        set_error("open ring errno=%d", errno); return -1;
    }
    if (fstat(fd, &sb) == 0 && (unsigned long)sb.st_size == RING_FILE_SIZE) {
        void *m = mmap(NULL, RING_FILE_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        if (m != MAP_FAILED) {
            volatile uint8_t *r = (volatile uint8_t *)m;
            if (rd32(r) == RING_MAGIC && rd32(r + 4) == RING_VERSION) {
                unsigned i;
                for (i = 0; i < RING_SLOTS; ++i) wr32(r + RING_HDR_SIZE + (size_t)i * RING_SLOT_SIZE, 0u);
                wr32(r + 0x0c, 0u);
                (void)msync(m, RING_FILE_SIZE, MS_SYNC);
                munmap(m, RING_FILE_SIZE);
                close(fd);
                snprintf(S.ring_file, sizeof S.ring_file, "uzyty ponownie (wyzerowany, bez usuwania)");
                return 0;
            }
            munmap(m, RING_FILE_SIZE);
        }
    }
    close(fd);
    if (unlink(g_ring_path) != 0 && errno != ENOENT) { set_error("unlink ring errno=%d", errno); return -1; }
    snprintf(S.ring_file, sizeof S.ring_file, "inny rozmiar/magic: usuniety");
    return 0;
}

/* MU1367: shared lease on the video cache lock. The supervisor's cleanup asks for the exclusive lock without waiting
 * and only for an instant, so a short retry loop is enough; on failure MOST is not taken. */
static int lease_take(void)
{
    struct flock lk;
    int i, fd = open(g_lease_path, O_RDWR | O_CREAT, 0600);
    if (fd < 0) { set_error("lease open errno=%d", errno); return -1; }
    (void)fcntl(fd, F_SETFD, FD_CLOEXEC);
    for (i = 0; i < 200 && !g_stop; ++i) {
        memset(&lk, 0, sizeof lk);
        lk.l_type = F_RDLCK; lk.l_whence = SEEK_SET;
        if (fcntl(fd, F_SETLK, &lk) == 0) { g_lease_fd = fd; return 0; }
        if (errno != EAGAIN && errno != EACCES && errno != EINTR) break;
        sleep_ms(10);
    }
    set_error("lease busy errno=%d", errno);
    close(fd);
    return -1;
}

static void lease_drop(void)
{
    if (g_lease_fd >= 0) { close(g_lease_fd); g_lease_fd = -1; }   /* the last close releases the process lease */
}

/* MU1367: the CarPlay supervisor's video policy, applied to Android Auto. 1 = cluster map requested. */
static int map_requested(void)
{
    struct cpmap_projection_preferences p;
    const char *dir = env_or("PMCP_AA_PREF_DIR", CPVC_PREF_DIR);
    const char *auto_enable = env_or("PMCP_AA_AUTO_ENABLE", "/mnt/app/carplaymaps/CLUSTER_AUTO_ENABLE");
    int r = cpmap_read_projection_preferences(dir, &p);
    int enabled = access(auto_enable, F_OK) == 0;
    int requested = cpvc_video_requested(&p, r >= 0, 1, enabled);
    snprintf(g_policy, sizeof g_policy, "prefs=%d map_mask=%d auto_enable=%d -> %s", r, r >= 0 ? p.map_mask : -1,
             enabled, requested == CPVC_VIDEO_MAP ? "map" : "vw");
    return requested == CPVC_VIDEO_MAP;
}

/* Called once at start in "most" mode, before the stream connects (v3). Leaves everything as it was on any failure. */
static int most_take(void)
{
    int fd, i, rc, p[2];
    const char *busy;
    uint64_t t0 = now_us();
    /* Our previous session's guardian may still be stopping its bridge / restoring MOST: wait for it (v4). CarPlay's
     * supervisor or bridge: never fight it, but wait a while for it to go (v7). The hook does not grant the phone
     * before we connect, so nothing streams meanwhile. */
    uint64_t last_st = 0;
    while ((busy = busy_reason()) != NULL && !g_stop) {
        unsigned long lim = strcmp(busy, "poprzednia sesja AA") == 0 ? g_wait_ms : g_cp_wait_ms;
        uint64_t t = now_us();
        if (t - t0 >= (uint64_t)lim * 1000u) break;
        snprintf(S.take_wait_reason, sizeof S.take_wait_reason, "%s", busy);
        if (t - last_st >= 1000000u) {
            S.take_wait_ms = (unsigned long)((t - t0) / 1000u);
            snprintf(S.most_state, sizeof S.most_state, "czeka (%s)", busy);
            write_status(); last_st = t;
        }
        sleep_ms(100);
    }
    S.take_wait_ms = (unsigned long)((now_us() - t0) / 1000u);
    if (busy != NULL) {
        snprintf(S.most_state, sizeof S.most_state, "zajety (%s)", busy);
        return -1;
    }
    if (access(g_bridge_path, X_OK) != 0) { set_error("brak bridge %s", g_bridge_path); return -1; }
    if (lease_take() != 0) return -1;            /* MU1367: before the ring is touched */
    /* A ring left by an earlier session (ours or CarPlay's) is reset in place, never unlinked while it may be mapped (v8). */
    if (ring_prepare() != 0) { lease_drop(); return -1; }
    (void)unlink(g_kf_req_path);                /* a request left by an earlier bridge is not ours */
    if (pipe(p) != 0) { set_error("pipe errno=%d", errno); lease_drop(); return -1; }
    rc = dmdt("dc", "72", NULL);
    S.dmdt_release_rc = rc != 0 ? rc : dmdt("sc", "4", "72");
    if (rc != 0 || S.dmdt_release_rc != 0) {
        set_error("dmdt release rc=%d", S.dmdt_release_rc);
        close(p[0]); close(p[1]);
        dmdt_restore();                           /* the first call may have gone through */
        lease_drop();
        return -1;
    }
    sleep_ms(500);
    g_guard_pid = fork();
    if (g_guard_pid == 0) { close(p[1]); guardian(p[0]); }
    close(p[0]);
    if (g_guard_pid < 0) { set_error("fork straznik errno=%d", errno); close(p[1]); dmdt_restore(); lease_drop(); return -1; }
    g_guard_fd = p[1];
    (void)fcntl(g_guard_fd, F_SETFD, FD_CLOEXEC);
    S.bridge_pid = (long)g_guard_pid;
    for (i = 0; i < 300 && !g_stop; ++i) {     /* the bridge creates and initialises the ring */
        int st;
        if (waitpid(g_guard_pid, &st, WNOHANG) == g_guard_pid) {
            g_guard_pid = -1; set_error("bridge wyszedl przy starcie"); most_restore(); return -1;
        }
        fd = open(g_ring_path, O_RDWR);
        if (fd >= 0) {
            struct stat sb;
            if (fstat(fd, &sb) == 0 && (unsigned long)sb.st_size == RING_FILE_SIZE) {
                void *m = mmap(NULL, RING_FILE_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
                if (m != MAP_FAILED) {
                    if (rd32((volatile uint8_t *)m) == RING_MAGIC && rd32((volatile uint8_t *)m + 4) == RING_VERSION) {
                        close(fd);
                        g_ring = (volatile uint8_t *)m;
                        g_seq = rd32(g_ring + 0x0c);
                        g_avcc_dirty = 1;
                        snprintf(S.most_state, sizeof S.most_state, "przejety gen=%u", (unsigned)rd32(g_ring + 8));
                        S.t_taken_us = now_us();
                        if (g_kf_take_ms != 0u) g_kf_take_due = now_us() + (uint64_t)g_kf_take_ms * 1000u;
                        return 0;
                    }
                    munmap(m, RING_FILE_SIZE);
                }
            }
            close(fd);
        }
        sleep_ms(10);
    }
    set_error("ring bridge nie gotowy");
    most_restore();
    return -1;
}

/* ---------------------------------------------------------------- fresh IDR (v2) */

/* Sends 'K' on the ACK pipe: the patched hook cycles the focus and the phone restarts with an IDR. */
static void kf_send(uint64_t t)
{
    uint8_t k = g_kf_byte;
    if (g_kf_last_us != 0u && t - g_kf_last_us < (uint64_t)g_kf_min_ms * 1000u) { S.kf_skipped++; return; }
    ack_connect();
    if (g_ack_fd >= 0 && send(g_ack_fd, &k, 1, 0) == 1) {
        S.kf_sent++;
        g_kf_last_us = t;
        if (g_kf_waiting) S.kf_no_idr++;      /* the previous request brought no IDR before this one */
        g_kf_waiting = 1;
    } else {
        S.kf_failed++;
    }
}

/* Main loop, every pass (at most 200 ms apart): the bridge's request file and the one after the takeover. */
static void kf_poll(uint64_t t)
{
    static uint64_t last_check;
    if (g_ring == NULL) return;
    if (t - last_check >= 100000u && (last_check = t, access(g_kf_req_path, F_OK) == 0)) {
        (void)unlink(g_kf_req_path);
        S.kf_bridge++;
        if (g_kf_bridge_on) kf_send(t); else S.kf_ignored++;   /* v10: no focus cycle for the bridge by default */
    }
    if (g_kf_take_due != 0u && t >= g_kf_take_due) {
        g_kf_take_due = 0u;
        S.kf_take++;
        kf_send(t);
    }
}

/* ---------------------------------------------------------------- access units */

static uint8_t g_in[IN_BUF_MAX];
static unsigned g_in_len;
static uint8_t g_au[AU_MAX];
static int g_most_failed;

typedef struct { unsigned off, len; } nal_t;

/* Start code at p[i]? Returns its length (3 or 4) or 0. */
static unsigned start_code_at(const uint8_t *p, unsigned i, unsigned n)
{
    if (i + 3u <= n && p[i] == 0 && p[i + 1] == 0 && p[i + 2] == 1) return 3u;
    if (i + 4u <= n && p[i] == 0 && p[i + 1] == 0 && p[i + 2] == 0 && p[i + 3] == 1) return 4u;
    return 0u;
}

/* ---------------------------------------------------------------- start sync (v6) */

static uint8_t g_sync_idr[AU_MAX];             /* the session's first IDR as ring data */
static unsigned g_sync_idr_len;
static unsigned g_sync_idr_ack;                /* its input size, for the held ACK */
static uint64_t g_sync_until, g_sync_next, g_sync_t0;
static uint8_t g_sync_pool[SYNC_POOL];
static unsigned g_sync_pool_len;
static struct { unsigned off, len, ack; } g_sync_held[SYNC_HELD_MAX];
static unsigned g_sync_held_n;

static void ack_schedule(unsigned bytes);

/* ---------------------------------------------------------------- pacing (v9) */

static uint8_t g_pace_pool[PACE_POOL];
static unsigned g_pace_pool_len;
static struct { unsigned len, ack; uint64_t t_in; } g_pace_q[PACE_MAX];   /* in order, data packed in the pool */
static unsigned g_pace_n;
static double g_ptok;                          /* bytes of budget; may go negative after a large frame */
static uint64_t g_ptok_t;

static void drain_refill(uint64_t t)
{
    if (g_dtok_t == 0u) { g_dtok_t = t; g_dtok = g_drain_burst; return; }
    if (t > g_dtok_t) {
        g_dtok += (double)(t - g_dtok_t) * g_drain_bps / 1e6;
        if (g_dtok > g_drain_burst) g_dtok = g_drain_burst;
        g_dtok_t = t;
    }
}

static void pace_refill(uint64_t t)
{
    if (g_ptok_t == 0u) { g_ptok_t = t; g_ptok = g_pace_burst; return; }
    if (t > g_ptok_t) {
        g_ptok += (double)(t - g_ptok_t) * g_pace_bps / 1e6;
        if (g_ptok > g_pace_burst) g_ptok = g_pace_burst;
        g_ptok_t = t;
    }
}

/* One frame into the ring now, charged to the budget, then its ACK. */
static void pace_emit(const uint8_t *au, unsigned len, unsigned ack)
{
    g_pace_last_us = now_us();
    if (g_ring != NULL) ring_put(RING_TYPE_FRAME, au, len, (uint32_t)++g_frame_no);
    if (g_pace_bps > 0.0) g_ptok -= (double)len;
    drain_refill(g_pace_last_us); g_dtok -= (double)len;
    ack_schedule(ack);
}

/* The oldest queued frame out. */
static void pace_pop(uint64_t t)
{
    unsigned len = g_pace_q[0].len, k;
    unsigned long w = (unsigned long)((t - g_pace_q[0].t_in) / 1000u);
    if (w > S.pace_wait_max_ms) S.pace_wait_max_ms = w;
    pace_emit(g_pace_pool, len, g_pace_q[0].ack);
    memmove(g_pace_pool, g_pace_pool + len, g_pace_pool_len - len);
    g_pace_pool_len -= len;
    for (k = 1; k < g_pace_n; ++k) g_pace_q[k - 1u] = g_pace_q[k];
    g_pace_n--;
}

/* Everything queued out at once (stream config change, end; v10: no longer for a full queue or the start hold). The budget then starts from 0, not
 * from the debt of the whole flush, or the frames after it would wait for seconds. */
static void pace_flush(void)
{
    uint64_t t = now_us();
    if (g_pace_n == 0u) return;
    while (g_pace_n > 0u) pace_pop(t);
    if (g_ptok < 0.0) g_ptok = 0.0;
}

/* v10: the gap since the last frame into the ring has passed. */
static int pace_gap_ok(uint64_t t)
{
    return g_pace_gap_us == 0u || g_pace_last_us == 0u || t >= g_pace_last_us + g_pace_gap_us;
}

/* v10: the queue is 3/4 full: drain it at the gap rate, whatever the byte budget says. */
static int pace_draining(void)
{
    return g_pace_n * 4u >= PACE_MAX * 3u || g_pace_pool_len * 4u >= PACE_POOL * 3u;
}

/* One queued frame may go now. */
static int pace_may_pop(uint64_t t)
{
    if (g_pace_n == 0u) return 0;
    if (!pace_gap_ok(t)) return 0;
    if (g_pace_bps <= 0.0 || g_ptok >= 0.0) return 1;
    if (!pace_draining()) return 0;
    drain_refill(t);
    return g_dtok >= 0.0;
}

/* Main loop: queued frames out while the budget and the gap allow (with a gap: one per pass). */
static void pace_poll(uint64_t t)
{
    if (g_pace_n == 0u) return;
    if (g_pace_bps > 0.0) pace_refill(t);
    while (pace_may_pop(t)) {
        if (g_pace_bps > 0.0 && g_ptok < 0.0) {     /* draining: the debt is capped so the queue does not stall after */
            S.pace_drain++;
            if (g_ptok < -g_pace_burst) g_ptok = -g_pace_burst;   /* the drain budget limits these */
        }
        pace_pop(t);
        if (g_pace_gap_us != 0u) break;
    }
}

/* Milliseconds until the next queued frame may go, or -1. */
static int pace_timeout_ms(uint64_t t)
{
    int ms = 0;
    if (g_pace_n == 0u) return -1;
    if (g_pace_bps > 0.0) {
        pace_refill(t);
        if (g_ptok < 0.0) {
            if (!pace_draining()) ms = (int)(-g_ptok * 1000.0 / g_pace_bps) + 1;
            else { drain_refill(t); if (g_dtok < 0.0) ms = (int)(-g_dtok * 1000.0 / g_drain_bps) + 1; }
        }
    }
    if (!pace_gap_ok(t)) {
        int g = (int)((g_pace_last_us + g_pace_gap_us - t + 999u) / 1000u);
        if (g > ms) ms = g;
    }
    return ms;
}

/* A frame (ring data + its input size for the ACK): straight out when nothing waits and the budget allows, else queued. */
static void pace_out(const uint8_t *au, unsigned len, unsigned ack)
{
    uint64_t t;
    if (g_pace_bps <= 0.0 && g_pace_gap_us == 0u) { pace_emit(au, len, ack); return; }
    t = now_us();
    if (g_pace_bps > 0.0) pace_refill(t);
    if (g_pace_n == 0u && (g_pace_bps <= 0.0 || g_ptok >= 0.0) && pace_gap_ok(t)) { pace_emit(au, len, ack); return; }
    if (g_pace_n == PACE_MAX || g_pace_pool_len + len > PACE_POOL) {
        /* v10: full: only the oldest frames needed for room go out (the gap is not kept for them), never the whole queue */
        S.pace_overflow++;
        while (g_pace_n > 0u && (g_pace_n == PACE_MAX || g_pace_pool_len + len > PACE_POOL)) pace_pop(t);
        if (g_ptok < -g_pace_burst) g_ptok = -g_pace_burst;
    }
    memcpy(g_pace_pool + g_pace_pool_len, au, len);
    g_pace_pool_len += len;
    g_pace_q[g_pace_n].len = len; g_pace_q[g_pace_n].ack = ack; g_pace_q[g_pace_n].t_in = t;
    g_pace_n++;
    S.pace_delayed++;
    if (g_pace_n > S.pace_q_hi) S.pace_q_hi = g_pace_n;
}

/* End of the hold: the held frames in order, then every held ACK (the IDR's first). */
static void sync_end(uint64_t t)
{
    unsigned k;
    if (S.sync_state != 1u) return;
    S.sync_state = 2u;
    S.sync_hold_ms = (unsigned long)((t - g_sync_t0) / 1000u);
    ack_schedule(g_sync_idr_ack);
    /* v9: the held frames in order through the pacing, each ACK when its frame goes (v6-v8: all at once) */
    for (k = 0; k < g_sync_held_n; ++k) pace_out(g_sync_pool + g_sync_held[k].off, g_sync_held[k].len, g_sync_held[k].ack);
    g_sync_held_n = 0; g_sync_pool_len = 0;
}

/* Main loop: the next copy of the IDR, or the end of the hold. */
static void sync_poll(uint64_t t)
{
    if (S.sync_state != 1u) return;
    if (g_ring == NULL || t >= g_sync_until || g_stop) { sync_end(t); return; }
    if (t >= g_sync_next) {
        ring_put(RING_TYPE_FRAME, g_sync_idr, g_sync_idr_len, (uint32_t)++g_frame_no);
        S.sync_repeats++;
        g_sync_next = t + (uint64_t)g_sync_repeat_ms * 1000u;
    }
}

/* Milliseconds until the next sync event, or -1. */
static int sync_timeout_ms(uint64_t t)
{
    uint64_t d;
    if (S.sync_state != 1u) return -1;
    d = g_sync_next < g_sync_until ? g_sync_next : g_sync_until;
    return d > t ? (int)((d - t + 999u) / 1000u) : 0;
}

/* A frame during the hold waits here; returns 0 when the pool is full (then the hold ends first). */
static int sync_hold_frame(const uint8_t *au, unsigned len, unsigned ack)
{
    if (g_sync_held_n == SYNC_HELD_MAX || g_sync_pool_len + len > SYNC_POOL) return 0;
    memcpy(g_sync_pool + g_sync_pool_len, au, len);
    g_sync_held[g_sync_held_n].off = g_sync_pool_len;
    g_sync_held[g_sync_held_n].len = len;
    g_sync_held[g_sync_held_n].ack = ack;
    g_sync_held_n++; g_sync_pool_len += len;
    S.sync_held++;
    return 1;
}

/* Turns one access unit (Annex B, possibly with AUD/SPS/PPS) into ring data. */
static void handle_au(const uint8_t *p, unsigned n)
{
    nal_t nals[64];
    unsigned cnt = 0, i = 0, j, out = 0, sc;
    int is_idr = 0, has_vcl = 0;
    uint64_t t = now_us();
    while (i < n && (sc = start_code_at(p, i, n)) == 0u) ++i;
    while (i < n && cnt < 64u) {
        unsigned start = i + sc, end = start;
        while (end < n && start_code_at(p, end, n) == 0u) ++end;
        sc = end < n ? start_code_at(p, end, n) : 0u;
        j = end;
        while (j > start && p[j - 1] == 0) --j;   /* trailing_zero_8bits belong to no NAL */
        if (j > start) { nals[cnt].off = start; nals[cnt].len = j - start; cnt++; }
        i = end;
    }
    for (j = 0; j < cnt; ++j) {
        const uint8_t *nal = p + nals[j].off;
        unsigned len = nals[j].len, type = nal[0] & 0x1fu, first_mb;
        int st;
        if (type == 7u) { keep_param_set(g_sps, &g_sps_len, nal, len); parse_sps(nal, len); continue; }
        if (type == 8u) { keep_param_set(g_pps, &g_pps_len, nal, len); parse_pps(nal, len); continue; }
        if (type == 9u) continue;
        if (type == 5u) is_idr = 1;
        if (type == 1u || type == 5u) {
            has_vcl = 1;
            st = slice_type(nal, len, &first_mb);
            if (st == 1) S.b_slices++;
        }
        if (out + 4u + len > AU_MAX) { S.dropped_big++; set_error("klatka > 256 KB"); return; }
        g_au[out++] = (uint8_t)(len >> 24); g_au[out++] = (uint8_t)(len >> 16);
        g_au[out++] = (uint8_t)(len >> 8); g_au[out++] = (uint8_t)len;
        memcpy(g_au + out, nal, len); out += len;
    }
    if (!has_vcl) return;                        /* codec config only */
    S.frames++; S.bytes_in += n;
    if (S.t_first_frame_us == 0u) S.t_first_frame_us = t;
    if (t - S.sec_start_us >= 1000000u) {
        if (S.sec_bytes > S.sec_max_bytes) S.sec_max_bytes = S.sec_bytes;
        S.sec_bytes = 0; S.sec_start_us = t;
    }
    S.sec_bytes += n;
    if (S.last_frame_us != 0u) {                 /* v9 gaps */
        uint64_t g = t - S.last_frame_us;
        if (g > S.gap_max_us) { S.gap_max_us = g; S.gap_max_at_us = S.last_frame_us; }
        if (g >= 1000000u) S.gaps_1s++;
        if (g >= 3000000u) S.gaps_3s++;
    }
    S.last_frame_us = t;
    win_advance(t);
    S.win[S.win_no % WIN_N]++;
    S.win_kb[S.win_no % WIN_N] += (n + 512u) / 1024u;
    if (n >= BIG_BYTES) {
        S.big_log_s[S.big_n % BIG_LOG_MAX] = since_take_s(t);
        S.big_log_kb[S.big_n % BIG_LOG_MAX] = (n + 512u) / 1024u;
        S.big_n++;
    }
    if (is_idr) {
        S.idrs++;
        if (g_kf_waiting) {
            S.kf_idr_ms_last = (unsigned long)((t - g_kf_last_us) / 1000u);
            if (S.kf_idr_ms_last > S.kf_idr_ms_max) S.kf_idr_ms_max = S.kf_idr_ms_last;
            g_kf_waiting = 0;
        }
        if (n > S.max_idr) S.max_idr = n;
        if (S.idr_logged < IDR_LOG_MAX && S.t_taken_us != 0u) {
            S.idr_log_ms[S.idr_logged] = (unsigned long)((t - S.t_taken_us) / 1000u);
            S.idr_log_bytes[S.idr_logged] = n;
            S.idr_logged++;
        }
        if (S.last_idr_us) {
            uint64_t g = t - S.last_idr_us;
            if (S.idr_gaps == 0u || g < S.idr_gap_min) S.idr_gap_min = g;
            if (g > S.idr_gap_max) S.idr_gap_max = g;
            S.idr_gap_sum += g; S.idr_gaps++;
        }
        S.last_idr_us = t;
    } else {
        if (n > S.max_p) S.max_p = n;
        S.sum_p += n; S.p_count++;
    }
    if (S.sync_state == 1u) {                     /* start hold: the frame and its ACK wait */
        if (sync_hold_frame(g_au, out, n)) return;
        S.sync_overflow++;
        sync_end(t);
    }
    if (g_ring != NULL) {
        if (g_avcc_dirty) pace_flush();           /* frames before a new avcC go out first, in order */
        send_avcc();
        if (is_idr && g_sync_hold_ms != 0u && S.sync_state == 0u) {
            pace_flush();
            ring_put(RING_TYPE_FRAME, g_au, out, (uint32_t)++g_frame_no);
            if (g_pace_bps > 0.0) { pace_refill(t); g_ptok -= (double)out; }
            memcpy(g_sync_idr, g_au, out); g_sync_idr_len = out; g_sync_idr_ack = n;
            g_sync_t0 = t;
            g_sync_until = t + (uint64_t)g_sync_hold_ms * 1000u;
            g_sync_next = t + (uint64_t)g_sync_repeat_ms * 1000u;
            S.sync_state = 1u;
            return;                               /* its ACK waits for the end of the hold */
        }
        pace_out(g_au, out, n);                   /* v9: maybe after the frames already waiting */
        return;
    }
    ack_schedule(n);
}

/* Is the NAL at p (after its start code) the first of a new access unit, given the current one
 * already holds a picture? AUD, SPS, PPS, SEI, or a slice with first_mb_in_slice == 0. */
static int starts_au(const uint8_t *nal, unsigned avail)
{
    unsigned type;
    if (avail < 2u) return 0;
    type = nal[0] & 0x1fu;
    if (type == 9u || type == 7u || type == 8u || type == 6u) return 1;
    if (type == 1u || type == 5u) return (nal[1] & 0x80u) != 0u;   /* ue(v) == 0 is a single '1' bit */
    return 0;
}

/* Splits g_in into access units; with flush, the tail is one too (the hook paused after it). */
static void process_input(int flush)
{
    unsigned i = 0, au_start = 0, sc;
    int au_has_vcl = 0;
    while (i < g_in_len) {
        sc = start_code_at(g_in, i, g_in_len);
        if (sc == 0u) { ++i; continue; }
        if (i + sc + 2u > g_in_len) break;                      /* header not here yet */
        {
            const uint8_t *nal = g_in + i + sc;
            unsigned type = nal[0] & 0x1fu;
            if (au_has_vcl && starts_au(nal, g_in_len - i - sc)) {
                handle_au(g_in + au_start, i - au_start);
                au_start = i; au_has_vcl = 0;
            }
            if (type == 1u || type == 5u) au_has_vcl = 1;
        }
        i += sc;
    }
    if (flush && au_has_vcl) { handle_au(g_in + au_start, g_in_len - au_start); au_start = g_in_len; }
    if (au_start > 0u) { memmove(g_in, g_in + au_start, g_in_len - au_start); g_in_len -= au_start; }
    if (g_in_len == IN_BUF_MAX) { g_in_len = 0; S.dropped_unparsed++; set_error("bufor wejscia pelny"); }
}

/* ---------------------------------------------------------------- connection */

static int connect_stream(const char *url)
{
    int fd;
    if (strncmp(url, "tcp://", 6) == 0) {
        struct sockaddr_in a;
        char host[64];
        const char *colon = strrchr(url + 6, ':');
        unsigned hl;
        int rcv = 2 * 1024 * 1024;
        if (colon == NULL || (hl = (unsigned)(colon - (url + 6))) >= sizeof host) return -1;
        memcpy(host, url + 6, hl); host[hl] = '\0';
        memset(&a, 0, sizeof a);
        a.sin_family = AF_INET;
        a.sin_port = htons((unsigned short)strtoul(colon + 1, NULL, 10));
        if (inet_pton(AF_INET, host, &a.sin_addr) != 1) return -1;
        fd = socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) return -1;
        (void)setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &rcv, sizeof rcv);
        if (connect(fd, (struct sockaddr *)&a, sizeof a) != 0) { close(fd); return -1; }
    } else {
        struct sockaddr_un a;
        fd = socket(AF_UNIX, SOCK_STREAM, 0);
        if (fd < 0) return -1;
        memset(&a, 0, sizeof a);
        a.sun_family = AF_UNIX;
        strncpy(a.sun_path, url, sizeof a.sun_path - 1u);
        if (connect(fd, (struct sockaddr *)&a, sizeof a) != 0) { close(fd); return -1; }
    }
    return fd;
}

/* One line per session in <rundir>/pmcp-aa-sessions.txt, the last 10 kept (small /ramdisk). */
static void append_session(void)
{
    char path[256], tmp[260], line[256], keep[10][256];
    unsigned n = 0, i;
    FILE *f;
    uint64_t t = now_us();
    double secs = (double)(t - S.t_start_us) / 1e6, fsecs = S.t_first_frame_us ? (double)(t - S.t_first_frame_us) / 1e6 : 0.0;
    run_path(path, sizeof path, "pmcp-aa-sessions.txt");
    if ((f = fopen(path, "r")) != NULL) {
        while (fgets(line, (int)sizeof line, f) != NULL) {
            line[strcspn(line, "\r\n")] = '\0';
            if (n == 10u) { for (i = 1; i < 10u; ++i) memcpy(keep[i - 1u], keep[i], sizeof keep[0]); n = 9u; }
            snprintf(keep[n++], sizeof keep[0], "%s", line);
        }
        fclose(f);
    }
    if (n == 10u) { for (i = 1; i < 10u; ++i) memcpy(keep[i - 1u], keep[i], sizeof keep[0]); n = 9u; }
    snprintf(keep[n++], sizeof keep[0], "sesja start=%.0fs czas=%.0fs klatki=%lu fps=%.1f IDR=%lu przerwa_max=%lums MOST=%s czekanie=%lums blad=%s",
             (double)S.t_start_us / 1e6, secs, S.frames, fsecs > 0.5 ? (double)S.frames / fsecs : 0.0, S.idrs,
             (unsigned long)(S.gap_max_us / 1000u), S.most_state[0] ? S.most_state : "-", S.take_wait_ms,
             S.last_error[0] ? S.last_error : "-");
    snprintf(tmp, sizeof tmp, "%s.tmp", path);
    if ((f = fopen(tmp, "w")) == NULL) return;
    for (i = 0; i < n; ++i) fprintf(f, "%s\n", keep[i]);
    if (fclose(f) == 0) rename(tmp, path);
}

static void on_signal(int sig) { (void)sig; g_stop = 1; }

int main(int argc, char **argv)
{
    const char *url = argc > 1 ? argv[1] : "tcp://127.0.0.1:12346";
    int fd = -1, i;
    uint64_t last_status = 0, last_rx = 0;
    char pidbuf[32];

    load_conf(env_or("PMCP_AA_CONF", "/mnt/app/carplaymaps/aa/feeder.conf"));
    g_mode = env_or("PMCP_AA_MODE", "analyze");
    if (strcmp(g_mode, "most") != 0) g_mode = "analyze";
    g_lease_path = env_or("PMCP_AA_CACHE_LOCK", "/ramdisk/cpmap-video-cache.lock");
    if (strcmp(g_mode, "most") == 0 && !map_requested()) g_mode = "analyze";   /* MU1367: MU menu map off */
    g_status_path = env_or("PMCP_AA_STATUS", "/ramdisk/pmcp-aa-feeder.txt");
    g_ring_path = env_or("PMCP_AA_RING", "/ramdisk/carplay-alt-ring.bin");
    g_bridge_path = env_or("PMCP_AA_BRIDGE", "/mnt/app/carplaymaps/altscreen-most-bridge");
    g_dmdt_path = env_or("PMCP_AA_DMDT", "/eso/bin/apps/dmdt");
    g_ack_path = env_or("PMCP_AA_ACK", "/tmp/gal_ack.sock");
    g_flush_dev = env_or("PMCP_AA_FLUSH_DEV", "/dev/mlb/debug/isoTX2");
    g_kf_req_path = env_or("PMCP_AA_KF_REQ", "/ramdisk/carplay-alt-force-idr.request");
    g_run_dir = env_or("PMCP_AA_RUNDIR", "/ramdisk");
    g_wait_ms = env_ul("PMCP_AA_WAIT_MS", 6000ul, 0ul, 20000ul);
    g_settle_ms = env_ul("PMCP_AA_SETTLE_MS", 1000ul, 0ul, 15000ul);
    g_cp_wait_ms = env_ul("PMCP_AA_CP_WAIT_MS", 20000ul, 0ul, 60000ul);
    g_cp_ready_path = env_or("PMCP_AA_CP_READY", "/ramdisk/carplay-bridge.ready");
    g_sync_hold_ms = env_ul("PMCP_AA_SYNC_HOLD_MS", 0ul, 0ul, 8000ul);           /* 0 = no start sync */
    g_sync_repeat_ms = env_ul("PMCP_AA_SYNC_REPEAT_MS", 500ul, 100ul, 2000ul);
    g_pace_bps = (double)env_ul("PMCP_AA_PACE_KBPS", 0ul, 0ul, 20000ul) * 1000.0 / 8.0;   /* 0 = no pacing (v9) */
    g_pace_burst = (double)env_ul("PMCP_AA_PACE_BURST_KB", 64ul, 8ul, 256ul) * 1000.0;
    g_pace_gap_us = (uint64_t)env_ul("PMCP_AA_PACE_GAP_MS", 0ul, 0ul, 200ul) * 1000u;      /* 0 = no gap (v10) */
    g_drain_bps = (double)env_ul("PMCP_AA_PACE_DRAIN_KBPS", 8000ul, 500ul, 12000ul) * 1000.0 / 8.0;
    g_drain_burst = 128.0 * 1000.0;
    g_kf_bridge_on = env_ul("PMCP_AA_KF_BRIDGE", 0ul, 0ul, 1ul) == 1ul;              /* 0 = bridge request only counted */
    if (strcmp(env_or("PMCP_AA_KF_METHOD", "focus"), "config") == 0) g_kf_byte = 'C';
    g_kf_take_ms = env_ul("PMCP_AA_KF_TAKE_MS", 0ul, 0ul, 10000ul);      /* 0 = no request after the takeover */
    g_kf_min_ms = env_ul("PMCP_AA_KF_MIN_MS", 3000ul, 1000ul, 60000ul);
    /* Default budget 700 KB/s (5.6 Mbit/s) with 150 KB of burst: below the bridge's ~12 Mbit/s MOST
     * output and inside its 1024-packet (188 KB) queue. 0 = ACK on arrival. */
    g_rate_bps = (double)env_ul("PMCP_AA_RATE_KBPS", 700ul, 0ul, 4000ul) * 1000.0;
    g_burst = (double)env_ul("PMCP_AA_BURST_KB", 150ul, 16ul, 180ul) * 1000.0;
    if (strcmp(g_mode, "analyze") == 0 && getenv("PMCP_AA_RATE_KBPS") == NULL) g_rate_bps = 0.0;
    g_tokens = g_burst;
    g_idle_ms = (unsigned)env_ul("PMCP_AA_IDLE_MS", 8ul, 2ul, 30ul);

    signal(SIGTERM, on_signal); signal(SIGINT, on_signal); signal(SIGHUP, on_signal);
    signal(SIGPIPE, SIG_IGN);
    memset(&S, 0, sizeof S);
    S.t_start_us = now_us(); g_tokens_t = S.t_start_us; S.sec_start_us = S.t_start_us;
    S.bridge_pid = -1;
    snprintf(pidbuf, sizeof pidbuf, "%ld\n", (long)getpid());
    {
        char pf[256];
        int pfd;
        snprintf(pf, sizeof pf, "%s.pid", g_status_path);
        pfd = open(pf, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (pfd >= 0) { (void)write(pfd, pidbuf, strlen(pidbuf)); close(pfd); }
    }

    /* v3: take MOST first; the hook grants the phone only once we are connected, so nothing waits for an ACK meanwhile.
     * One attempt per start; on failure the session runs as analysis (the cluster keeps the VW map). */
    if (strcmp(g_mode, "most") == 0) {
        if (most_take() != 0) g_most_failed = 1;
        else if (g_settle_ms) { write_status(); sleep_ms((unsigned)g_settle_ms); }   /* let the AID lock on first */
    }
    write_status();
    for (i = 0; i < 100 && !g_stop && (fd = connect_stream(url)) < 0; ++i) sleep_ms(50);
    if (fd < 0) { set_error("brak polaczenia %s", url); most_restore(); write_status(); return 2; }
    ack_connect();

    while (!g_stop) {
        struct pollfd pfd;
        int timeout = 200, r;
        uint64_t t = now_us();
        if (g_ack_count > 0u) {
            uint64_t due = g_ack_due[g_ack_head];
            int ms = due > t ? (int)((due - t + 999u) / 1000u) : 0;
            if (ms < timeout) timeout = ms;
        }
        if (g_in_len > 0u && last_rx != 0u && timeout > (int)g_idle_ms) timeout = (int)g_idle_ms;
        { int st = sync_timeout_ms(t); if (st >= 0 && st < timeout) timeout = st; }
        { int pt = pace_timeout_ms(t); if (pt >= 0 && pt < timeout) timeout = pt; }
        pfd.fd = fd; pfd.events = POLLIN; pfd.revents = 0;
        r = poll(&pfd, 1, timeout);
        t = now_us();
        if (r > 0 && (pfd.revents & (POLLIN | POLLHUP | POLLERR))) {
            ssize_t n = recv(fd, g_in + g_in_len, IN_BUF_MAX - g_in_len, 0);
            if (n == 0 || (n < 0 && errno != EINTR && errno != EAGAIN)) { set_error("strumien zamkniety"); break; }
            if (n > 0) { g_in_len += (unsigned)n; last_rx = t; process_input(0); }
        } else if (r == 0 && g_in_len > 0u && last_rx != 0u && t - last_rx >= (uint64_t)g_idle_ms * 1000u) {
            process_input(1);
            last_rx = 0;
        }
        sync_poll(now_us());
        pace_poll(now_us());
        ack_send_due(now_us());
        kf_poll(now_us());
        if (g_guard_pid > 0) {                   /* bridge gone mid-session: the guardian gave MOST back */
            int st;
            if (waitpid(g_guard_pid, &st, WNOHANG) == g_guard_pid) {
                g_guard_pid = -1;
                if (g_ring != NULL) { munmap((void *)g_ring, RING_FILE_SIZE); g_ring = NULL; }
                if (g_guard_fd >= 0) { close(g_guard_fd); g_guard_fd = -1; }
                set_error("bridge zakonczyl sie w trakcie");
                snprintf(S.most_state, sizeof S.most_state, "oddane (bridge)");
                g_most_failed = 1;
            }
        }
        if (t - last_status >= 1000000u) { write_status(); last_status = t; }
    }
    sync_end(now_us());
    pace_flush();
    ack_send_due(UINT64_MAX);
    close(fd);
    most_restore();
    write_status();
    append_session();
    if (g_ack_fd >= 0) close(g_ack_fd);
    return 0;
}
