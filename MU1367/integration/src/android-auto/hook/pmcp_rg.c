/* SPDX-License-Identifier: GPL-3.0-or-later
 * pmcp (AA gamma): Android Auto 1.7 navigation -> the RAM mailbox the rg route guidance Java package reads.
 *
 * Google Maps at protocol 1.6+ sends 0x8006 NavigationState (the next step: NavigationType, roundabout exit number,
 * angle), 0x8007 NavigationCurrentPosition (metres to that step) and 0x8003 NavigationStatus. Here they become the
 * synthetic iAP2 route guidance events tomasz-twardzicki's rg bridge decodes (LiveModel.java, MailboxReader.java,
 * upstream/tomasz 024dd159 MU1427/route-guidance): 0x5202 manoeuvre {components [0x10], index, type, side, junction,
 * angle} and 0x5201 route {components [0x10], state, order [index], manoeuvre distance}. No ETA / remaining distance
 * keys: those stay in the AA picture.
 *
 * Files (own directory, never the CarPlay reader's /ramdisk/carplay-route-guidance):
 *   GAL_PMCP_RG_DIR (default /ramdisk/pmcp-aa-rg)/latest.bin  RGM1 mailbox, kind 1 snapshot of an RGI1 image, written
 *                                                             tmp + rename; heartbeat (serial + 1, same bytes) every
 *                                                             0.5 s, the route event again every 2.5 s while guiding
 *                                                             and the phone still sends navigation
 * Liveness (review 2026-11-03, M1): the route event is repeated only while 0x8006/0x8007 arrived within
 * GAL_PMCP_RG_STALE_MS (default 10 s). Without them the repeats stop, so the bridge releases the arrow within 5 s
 * (a crashed Maps, navigation moved to another app); the next 0x8006/0x8007 brings it back. After
 * GAL_PMCP_RG_END_MS (default 60 s) of silence the route is ended (state 0), as on 0x8003 inactive.
 * Unknown NavigationType (M2): a new step index with no manoeuvre, so a following distance never lands on the
 * previous arrow.
 *   GAL_PMCP_RG_STATUS (default /ramdisk/pmcp-aa-rg.txt)      counters and the last manoeuvres, for pmcp aa-status
 * Only when GAL_PMCP_RG=1. pmcp_rg_message() runs on gal's reader thread and only copies values under a mutex; all
 * file work is on this module's own thread.
 */
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "pmcp_rg.h"

#define RG_SNAP     33088u
#define RG_SLOTS    16u
#define RG_EV_MAX   64u
#define RG_LAST     5u
#define RG_UNK      8u

typedef struct { uint32_t seq; uint16_t id, len; uint8_t d[RG_EV_MAX]; } rg_ev;

static pthread_mutex_t g_m = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_cv = PTHREAD_COND_INITIALIZER;
static int g_on = -1, g_started;
static char g_dir[128], g_status[128];
static rg_ev g_ring[RG_SLOTS];
static uint32_t g_seq, g_session, g_life_s, g_life_ns, g_serial;
static uint64_t g_nonce;
static int g_dirty;                   /* a new event since the last write */
static int g_guiding;                 /* 0x8003 active */
static int g_state_sent;              /* the bridge has seen route state 1 (it caches manoeuvres only then) */
static unsigned g_index;              /* current manoeuvre index, 0 = none */
static int g_cur_t = -1, g_cur_j, g_cur_side, g_cur_a, g_cur_has_a;
static long g_meters = -1;
static uint64_t g_route_ms;           /* last 0x5201 */
static unsigned long g_n3, g_n6, g_n7, g_known, g_unknown, g_events, g_writes, g_werr;
static unsigned g_unk[RG_UNK], g_unk_n;
static char g_last[RG_LAST][96];
static unsigned g_last_n;
static uint64_t g_t0;
static uint64_t g_nav_ms;             /* last 0x8006 / 0x8007 */
static unsigned g_stale_ms = 10000u, g_end_ms = 60000u;
static int g_paused;                  /* route repeats stopped: no navigation from the phone */
static unsigned long g_pauses, g_silent_ends;
static unsigned g_unk_last;           /* NavigationType of the current unknown step (g_cur_t == -1) */

static uint64_t now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000u + (uint64_t)ts.tv_nsec / 1000000u;
}
static void le32(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); }
static void le16(uint8_t *p, unsigned v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }

/* ---- protobuf reader (bounded) ---- */
typedef struct { const uint8_t *p, *e; } pb;
static uint64_t pb_var(pb *s)
{
    uint64_t v = 0; int sh = 0;
    while (s->p < s->e) {
        uint8_t b = *s->p++;
        if (sh < 64) v |= (uint64_t)(b & 0x7fu) << sh;
        if (!(b & 0x80u)) break;
        sh += 7;
    }
    return v;
}
static int pb_tag(pb *s, unsigned *f, unsigned *w)
{
    uint64_t t;
    if (s->p >= s->e) return 0;
    t = pb_var(s);
    if (t == 0) return 0;
    *f = (unsigned)(t >> 3); *w = (unsigned)(t & 7u);
    return 1;
}
static int pb_sub(pb *s, pb *d)
{
    uint64_t n = pb_var(s);
    if (n > (uint64_t)(s->e - s->p)) { s->p = s->e; return 0; }
    d->p = s->p; d->e = s->p + n; s->p += n;
    return 1;
}
static void pb_skip(pb *s, unsigned w)
{
    pb d;
    if (w == 0u) (void)pb_var(s);
    else if (w == 2u) (void)pb_sub(s, &d);
    else if (w == 1u) s->p = (s->e - s->p >= 8) ? s->p + 8 : s->e;
    else if (w == 5u) s->p = (s->e - s->p >= 4) ? s->p + 4 : s->e;
    else s->p = s->e;
}

/* ---- TLV writer (iAP2, big-endian) ---- */
typedef struct { uint8_t *b; unsigned n, cap; int full; } tw;
static void tlv(tw *o, unsigned key, const uint8_t *v, unsigned len)
{
    if (o->n + 4u + len > o->cap) { o->full = 1; return; }
    o->b[o->n] = (uint8_t)((len + 4u) >> 8); o->b[o->n + 1] = (uint8_t)(len + 4u);
    o->b[o->n + 2] = (uint8_t)(key >> 8); o->b[o->n + 3] = (uint8_t)key;
    memcpy(o->b + o->n + 4, v, len);
    o->n += 4u + len;
}
static void tlv_u(tw *o, unsigned key, uint32_t v, unsigned width)
{
    uint8_t b[4]; unsigned i;
    for (i = 0; i < width; ++i) b[i] = (uint8_t)(v >> (8u * (width - 1u - i)));
    tlv(o, key, b, width);
}

static void push_event(unsigned id, const tw *o)
{
    rg_ev *e;
    if (o->full) return;
    g_seq++;
    e = &g_ring[(g_seq - 1u) & (RG_SLOTS - 1u)];
    e->seq = g_seq; e->id = (uint16_t)id; e->len = (uint16_t)o->n;
    memcpy(e->d, o->b, o->n);
    g_events++;
    g_dirty = 1;
}

static void route_event(int state)
{
    uint8_t b[RG_EV_MAX]; tw o = { b, 0, sizeof b, 0 };
    tlv_u(&o, 0, 0x10, 2);
    tlv_u(&o, 1, (uint32_t)state, 1);
    g_state_sent = state == 1;
    if (state == 1 && g_index) {
        tlv_u(&o, 13, g_index, 2);
        if (g_meters >= 0) tlv_u(&o, 10, (uint32_t)g_meters, 4);
    }
    push_event(0x5201, &o);
    g_route_ms = now_ms();
}

static void maneuver_event(void)
{
    uint8_t b[RG_EV_MAX]; tw o = { b, 0, sizeof b, 0 };
    tlv_u(&o, 0, 0x10, 2);
    tlv_u(&o, 1, g_index, 2);
    tlv_u(&o, 3, (uint32_t)g_cur_t, 1);
    tlv_u(&o, 8, (uint32_t)g_cur_side, 1);
    tlv_u(&o, 9, (uint32_t)g_cur_j, 1);
    if (g_cur_has_a) tlv_u(&o, 11, (uint32_t)(uint16_t)(int16_t)g_cur_a, 2);
    push_event(0x5202, &o);
}

/* 1.7 NavigationType (kombibridge numbering, as nav_translate.c) -> iAP2 RouteGuidanceManeuver type, junction, side
 * (0 right-hand traffic, 1 left-hand: from the roundabout direction), signed angle (negative = left). 0 = unknown. */
int pmcp_rg_map(unsigned nt, unsigned exit_no, unsigned angle, int *t, int *j, int *side, int *a, int *has_a)
{
    static const signed char k[51] = {
        -1, 5, 5, 13, 14, 49, 50, 1, 2, 47, 48, 4, 4,   /*  0..12 */
        49, 50, 1, 2, 47, 48, 4, 4,                     /* 13..20 on-ramp slight, normal, sharp, u-turn */
        22, 23, 22, 23, 13, 14, 52, 53, 5,              /* 21..29 off-ramp, fork, merge L/R/- */
        -1, -1, -2, -2, -3, -3,                         /* 30, 31 unassigned; 32..35 enter-and-exit CW, CCW */
        3, 15, 15, 12, 12, 24, 25,                      /* 36 straight, ferries, destinations */
        6, 7, 6, 7,                                     /* 43..46 roundabout enter/exit CW, CCW */
        15, 15, 15, 15 };                               /* 47..50 ferries L/R */
    int v = nt < 51u ? k[nt] : -1;
    *j = 0; *side = 0; *a = 0; *has_a = 0;
    if (v == -1) return 0;
    if (v == -2 || v == -3) {                           /* enter and exit: exit number + angle */
        int cw = v == -2;
        *side = cw ? 1 : 0; *j = 1;
        if (exit_no >= 1u && exit_no <= 19u && angle >= 1u && angle <= 360u) {
            *t = 27 + (int)exit_no;
            *a = cw ? (int)angle - 180 : 180 - (int)angle;
            *has_a = 1;
        } else {
            *t = 6;
        }
        return 1;
    }
    *t = v;
    if (nt >= 43u && nt <= 46u) { *j = 1; *side = nt <= 44u ? 1 : 0; }
    if (v == 4) { *a = (nt == 11u || nt == 19u) ? -180 : 180; *has_a = 1; }
    return 1;
}

static const char *type_name(int t)
{
    switch (t) {
    case 1: return "w lewo"; case 2: return "w prawo"; case 3: return "prosto"; case 4: return "zawroc";
    case 5: return "dalej"; case 6: return "rondo"; case 7: return "zjazd z ronda"; case 12: return "cel";
    case 13: return "trzymaj lewo"; case 14: return "trzymaj prawo"; case 15: return "prom";
    case 22: return "zjazd lewo"; case 23: return "zjazd prawo"; case 24: return "cel lewo"; case 25: return "cel prawo";
    case 47: return "ostro lewo"; case 48: return "ostro prawo"; case 49: return "lekko lewo"; case 50: return "lekko prawo";
    case 52: return "pas lewo"; case 53: return "pas prawo";
    default: return t >= 28 && t <= 46 ? "rondo zjazd" : "?";
    }
}

static void on_state(pb s)
{
    unsigned f, w, sf, sw, mf, mw, nt = 0, ex = 0, an = 0;
    int have = 0, t, j, side, a, has_a;
    pb step, man;
    while (!have && pb_tag(&s, &f, &w)) {
        if (!(f == 1u && w == 2u)) { pb_skip(&s, w); continue; }
        if (!pb_sub(&s, &step)) break;
        have = 1;
        while (pb_tag(&step, &sf, &sw)) {
            if (!(sf == 1u && sw == 2u)) { pb_skip(&step, sw); continue; }
            if (!pb_sub(&step, &man)) break;
            while (pb_tag(&man, &mf, &mw)) {
                if (mw != 0u) { pb_skip(&man, mw); continue; }
                if (mf == 1u) nt = (unsigned)pb_var(&man);
                else if (mf == 2u) ex = (unsigned)pb_var(&man);
                else if (mf == 3u) an = (unsigned)pb_var(&man);
                else (void)pb_var(&man);
            }
        }
    }
    if (!have) return;
    if (!pmcp_rg_map(nt, ex, an, &t, &j, &side, &a, &has_a)) {
        unsigned i;
        g_unknown++;
        for (i = 0; i < g_unk_n && g_unk[i] != nt; ++i) {}
        if (i == g_unk_n && g_unk_n < RG_UNK) g_unk[g_unk_n++] = nt;
        if (g_cur_t == -1 && g_index && g_unk_last == nt) return;     /* the same unknown step again */
        /* a new step without a manoeuvre: the route points at an index with no 0x5202, so the bridge shows no
         * arrow and the distance that follows is not attached to the previous one */
        g_cur_t = -1; g_unk_last = nt;
        g_index = g_index >= 65535u ? 1u : g_index + 1u;
        g_meters = -1;
        {
            unsigned k = g_last_n < RG_LAST ? g_last_n++ : (memmove(g_last, g_last[1], sizeof g_last[0] * (RG_LAST - 1u)), RG_LAST - 1u);
            snprintf(g_last[k], sizeof g_last[k], "t=%lus AA typ=%u zjazd=%u kat=%u -> nierozpoznany (bez strzalki)",
                     (unsigned long)((now_ms() - g_t0) / 1000u), nt, ex, an);
        }
        g_guiding = 1;
        if (!g_state_sent) { unsigned keep = g_index; g_index = 0; route_event(1); g_index = keep; }
        route_event(1);
        return;
    }
    g_known++;
    if (t == g_cur_t && j == g_cur_j && side == g_cur_side && a == g_cur_a && has_a == g_cur_has_a && g_index) return;
    g_cur_t = t; g_cur_j = j; g_cur_side = side; g_cur_a = a; g_cur_has_a = has_a;
    g_index = g_index >= 65535u ? 1u : g_index + 1u;
    g_meters = -1;                                    /* a new step: its distance comes with 0x8007 */
    {
        unsigned k = g_last_n < RG_LAST ? g_last_n++ : (memmove(g_last, g_last[1], sizeof g_last[0] * (RG_LAST - 1u)), RG_LAST - 1u);
        snprintf(g_last[k], sizeof g_last[k], "t=%lus AA typ=%u zjazd=%u kat=%u -> iAP2 %d %s%s",
                 (unsigned long)((now_ms() - g_t0) / 1000u), nt, ex, an, t, type_name(t), has_a ? " (kat)" : "");
    }
    g_guiding = 1;
    /* LiveModel.apply caches a 0x5202 only while the route state is active, and a state change from inactive clears
     * the cache: the state first, then the manoeuvre, then the route event that points at it */
    if (!g_state_sent) { unsigned keep = g_index; g_index = 0; route_event(1); g_index = keep; }
    maneuver_event();
    route_event(1);
}

static void on_position(pb s)
{
    unsigned f, w, df, dw, nf, nw;
    pb d, n;
    long m = -1;
    while (pb_tag(&s, &f, &w)) {
        if (!(f == 1u && w == 2u)) { pb_skip(&s, w); continue; }
        if (!pb_sub(&s, &d)) break;
        while (pb_tag(&d, &df, &dw)) {
            if (df == 1u && dw == 2u) {
                if (!pb_sub(&d, &n)) break;
                while (pb_tag(&n, &nf, &nw)) {
                    if (nf == 1u && nw == 0u) { uint64_t v = pb_var(&n); if (v <= 20000000u) m = (long)v; }
                    else pb_skip(&n, nw);
                }
            } else pb_skip(&d, dw);
        }
        break;
    }
    if (m < 0 || !g_guiding || !g_index) return;
    if (m == g_meters && now_ms() - g_route_ms < 2500u) return;
    g_meters = m;
    route_event(1);
}

static void on_status(pb s)
{
    unsigned f, w;
    while (pb_tag(&s, &f, &w)) {
        if (f == 1u && w == 0u) {
            unsigned v = (unsigned)pb_var(&s);
            if (v == 1u || v == 3u) { g_guiding = 1; }
            else if (g_guiding || g_index) {
                g_guiding = 0; g_index = 0; g_cur_t = -1; g_meters = -1; g_paused = 0;
                route_event(0);
            }
            return;
        }
        pb_skip(&s, w);
    }
}

/* ---- writer thread ---- */
static int write_file(const char *dir, const char *name, const uint8_t *a, size_t an, const uint8_t *b, size_t bn)
{
    char tmp[200], dst[200];
    int fd, bad = 0;
    snprintf(tmp, sizeof tmp, "%s/%s.tmp", dir, name);
    snprintf(dst, sizeof dst, "%s/%s", dir, name);
    fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return -1;
    if (an && write(fd, a, an) != (ssize_t)an) bad = 1;
    if (bn && write(fd, b, bn) != (ssize_t)bn) bad = 1;
    if (close(fd) != 0) bad = 1;
    if (bad) { unlink(tmp); return -1; }
    return rename(tmp, dst);
}

static uint8_t g_img[RG_SNAP + 32u];

/* Builds RGM1 + compacted RGI1 from the ring; caller holds g_m. Returns the size. */
static size_t build(void)
{
    uint8_t *h = g_img, *b = g_img + 32;
    uint32_t count = g_seq < RG_SLOTS ? g_seq : RG_SLOTS, i;
    size_t used = 64;
    memset(b, 0, 64);
    memcpy(b, "RGI1", 4); le32(b + 4, 1); le32(b + 8, RG_SNAP); le32(b + 12, 0);
    le32(b + 16, g_session); le32(b + 20, g_seq); le32(b + 24, count); le32(b + 28, 0); le32(b + 32, 0);
    le32(b + 36, 1); le32(b + 40, g_life_s); le32(b + 44, g_life_ns);
    for (i = 0; i < count; ++i) {
        uint32_t s = g_seq - count + 1u + i;
        const rg_ev *e = &g_ring[(s - 1u) & (RG_SLOTS - 1u)];
        uint8_t *p = b + used;
        le32(p, e->seq); le16(p + 4, e->id); le16(p + 6, e->len); le32(p + 8, g_session); le32(p + 12, 0);
        memcpy(p + 16, e->d, e->len);
        used += 16u + e->len;
    }
    memcpy(h, "RGM1", 4); le32(h + 4, 1); le32(h + 8, (uint32_t)(32u + used));
    le32(h + 12, ++g_serial); le32(h + 16, 1); le32(h + 20, 0);
    le32(h + 24, (uint32_t)g_nonce); le32(h + 28, (uint32_t)(g_nonce >> 32));
    return 32u + used;
}

static void write_status(void)
{
    char s[1024];
    int n;
    unsigned i;
    n = snprintf(s, sizeof s, "RG AA: komunikaty 0x8003=%lu 0x8006=%lu 0x8007=%lu prowadzenie=%s\n"
                 "manewry rozpoznane=%lu nierozpoznane=%lu", g_n3, g_n6, g_n7, g_guiding ? "tak" : "nie", g_known, g_unknown);
    if (g_unk_n) {
        n += snprintf(s + n, sizeof s - (size_t)n, " (typy AA:");
        for (i = 0; i < g_unk_n; ++i) n += snprintf(s + n, sizeof s - (size_t)n, " %u", g_unk[i]);
        n += snprintf(s + n, sizeof s - (size_t)n, ")");
    }
    n += snprintf(s + n, sizeof s - (size_t)n, "\nzapis: zdarzenia=%lu pliki=%lu bledy=%lu dystans=%ldm\n",
                  g_events, g_writes, g_werr, g_meters);
    n += snprintf(s + n, sizeof s - (size_t)n, "cisza telefonu: ostatnia nawigacja %lds temu, pauzy=%lu koniec_po_ciszy=%lu%s\n",
                  g_nav_ms ? (long)((now_ms() - g_nav_ms) / 1000u) : -1L, g_pauses, g_silent_ends, g_paused ? " (pauza)" : "");
    for (i = 0; i < g_last_n && n < (int)sizeof s - 100; ++i) n += snprintf(s + n, sizeof s - (size_t)n, "manewr %s\n", g_last[i]);
    {
        char tmp[200];
        FILE *f;
        snprintf(tmp, sizeof tmp, "%s.tmp", g_status);
        if ((f = fopen(tmp, "w")) == NULL) return;
        fputs(s, f);
        if (fclose(f) == 0) rename(tmp, g_status);
    }
}

static void *writer(void *arg)
{
    uint64_t last_write = 0, last_status = 0;
    (void)arg;
    pthread_mutex_lock(&g_m);
    for (;;) {
        struct timespec ts;
        uint64_t t;
        int need;
        clock_gettime(CLOCK_REALTIME, &ts);
        ts.tv_nsec += 250000000L;
        if (ts.tv_nsec >= 1000000000L) { ts.tv_sec++; ts.tv_nsec -= 1000000000L; }
        if (!g_dirty) pthread_cond_timedwait(&g_cv, &g_m, &ts);
        t = now_ms();
        /* the bridge needs a new accepted event within 5 s while guiding; only while the phone still navigates */
        if (g_guiding && g_index) {
            uint64_t quiet = t - g_nav_ms;
            if (quiet >= g_end_ms) {
                g_guiding = 0; g_index = 0; g_cur_t = -1; g_meters = -1; g_paused = 0;
                g_silent_ends++;
                route_event(0);
            } else if (quiet >= g_stale_ms) {
                if (!g_paused) { g_paused = 1; g_pauses++; }
            } else if (t - g_route_ms >= 2500u) route_event(1);
        }
        /* heartbeat 0.5 s: the bridge wants a new serial within 1.5 s (review m1: 1 s left ~150 ms margin) */
        need = g_dirty || t - last_write >= 500u;
        if (need) {
            size_t n = build();
            g_dirty = 0;
            if (write_file(g_dir, "latest.bin", g_img, n, NULL, 0) == 0) g_writes++; else g_werr++;
            last_write = t;
        }
        if (t - last_status >= 1000u) { write_status(); last_status = t; }
    }
    return NULL;
}

static int start(void)
{
    pthread_t th;
    pthread_attr_t at;
    struct timespec ts;
    const char *v = getenv("GAL_PMCP_RG");
    g_on = v != NULL && strcmp(v, "1") == 0;
    if (!g_on) return 0;
    v = getenv("GAL_PMCP_RG_DIR");
    snprintf(g_dir, sizeof g_dir, "%s", v && *v == '/' ? v : "/ramdisk/pmcp-aa-rg");
    v = getenv("GAL_PMCP_RG_STALE_MS");
    if (v) { unsigned long x = strtoul(v, NULL, 10); if (x >= 1000u && x <= 120000u) g_stale_ms = (unsigned)x; }
    v = getenv("GAL_PMCP_RG_END_MS");
    if (v) { unsigned long x = strtoul(v, NULL, 10); if (x >= 2000u && x <= 600000u) g_end_ms = (unsigned)x; }
    if (g_end_ms <= g_stale_ms) g_end_ms = g_stale_ms + 1000u;
    v = getenv("GAL_PMCP_RG_STATUS");
    snprintf(g_status, sizeof g_status, "%s", v && *v == '/' ? v : "/ramdisk/pmcp-aa-rg.txt");
    if (mkdir(g_dir, 0755) != 0 && errno != EEXIST) { g_on = 0; return 0; }
    clock_gettime(CLOCK_REALTIME, &ts);
    g_t0 = now_ms();
    g_life_s = (uint32_t)ts.tv_sec; g_life_ns = (uint32_t)ts.tv_nsec;
    g_nonce = ((uint64_t)(uint32_t)getpid() << 32) | (uint32_t)ts.tv_sec;   /* new per gal process: the bridge resets */
    g_session = ((uint32_t)getpid() & 0xffffu) | 0x10000u;
    g_dirty = 1;                                                             /* baseline: no events */
    pthread_attr_init(&at);
    pthread_attr_setdetachstate(&at, PTHREAD_CREATE_DETACHED);
    if (pthread_create(&th, &at, writer, NULL) != 0) g_on = 0;
    pthread_attr_destroy(&at);
    return g_on;
}

void pmcp_rg_message(const unsigned char *msg, unsigned len)
{
    unsigned id;
    pb s;
    if (msg == NULL || len < 2u) return;
    pthread_mutex_lock(&g_m);
    if (!g_started) { g_started = 1; start(); }
    if (!g_on) { pthread_mutex_unlock(&g_m); return; }
    id = ((unsigned)msg[0] << 8) | msg[1];
    s.p = msg + 2; s.e = msg + len;
    if (id == 0x8006u || id == 0x8007u) {
        g_nav_ms = now_ms();
        if (g_paused) {
            /* the phone navigates again: the current manoeuvre and the route event once more */
            g_paused = 0;
            if (g_guiding && g_index) { if (g_cur_t >= 0) maneuver_event(); route_event(1); }
        }
    }
    if (id == 0x8006u) { g_n6++; on_state(s); }
    else if (id == 0x8007u) { g_n7++; on_position(s); }
    else if (id == 0x8003u) { g_n3++; on_status(s); }
    if (g_dirty) pthread_cond_signal(&g_cv);
    pthread_mutex_unlock(&g_m);
}
