#!/bin/sh
# Wireless CarPlay Maps. Maintainer: omonob. Source date: 2026-08-29.
# Project maintainer: omonob
# Publication label: 2026-08-29
# wcp_autostart.sh -- boot-time autostart for the self-built wireless-CarPlay receiver.
#
# Launched DETACHED from /etc/eso/production/btstack_wrap.sh (armed branch) so it never
# delays btstack (the wrapper backgrounds it with '&' then exec's btstack immediately).
# Gated by the flag file /mnt/persist/wcp_autostart (present = autostart on; absent = do
# nothing). Idempotent, bounded, fail-safe: if the flag or any binary is missing, or if
# uap0 never comes up, it just exits -- it never hangs boot and never touches the WLAN
# driver, the SSID, or internet-sharing.
#
# Persistent home of the binaries/scripts: /mnt/ota (same FS as libbtwcp.so). They are
# copied into /dev/shmem (tmpfs, wiped each boot) and started there, exactly like the
# known-good manual bench procedure (fs_03_start.sh).
#
# Rollback (HMI-independent, serial-recoverable):
#   rm /mnt/persist/wcp_autostart            # disable autostart (helper exits at once)
#   (and/or) cp /mnt/persist/btstack_wrap.sh.bak-preauto /etc/eso/production/btstack_wrap.sh
#   then reboot.
LOG=/dev/shmem/wcp_autostart.log
FLAG=/mnt/persist/wcp_autostart
SRC=/mnt/ota
DST=/dev/shmem
log() { echo "[wcp-auto] $*" >> $LOG; }

# Belt-and-suspenders: never run the receiver/video under the btstack interposer.
unset LD_PRELOAD

: > $LOG
log "start pid=$$ preload=[${LD_PRELOAD:-none}]"
[ -f $FLAG ] || { log "flag $FLAG absent -> do nothing"; exit 0; }
# 用户开关(App-Connect 菜单"无线 CarPlay",cpm_sync 落盘):存在 = 关
[ -f /mnt/persist/btwcp_off ] && { log "switched off in App-Connect (/mnt/persist/btwcp_off) -> do nothing"; exit 0; }

# Authorized local bench build: application ID binding omitted.
# --- channel-sync watcher (background, starts IMMEDIATELY) ---------------------
# uap0 is single-radio and follows the uplink (mlan0), so its real channel often differs
# from the static Channel in /tmp/uaputl.cfg (e.g. AP on 9 while cfg says 11). btwcp reads
# that Channel at CarPlayStart(0x4301) time and hands the phone the WRONG channel, so the
# phone scans the wrong channel, never joins the hotspot, and wireless CarPlay stalls right
# after 0x4301 (no DHCP lease, no AirPlay on :5000). The watcher keeps the FILE in sync with
# the real channel; it is file-only -- never runs uaputl, never touches the WLAN driver, and
# never reads the hotspot password aloud. Started before everything else to win the race
# against an early phone handshake.
if [ -r $SRC/wcp_chansync.sh ]; then
    cp -f $SRC/wcp_chansync.sh $DST/wcp_chansync.sh 2>/dev/null
    chmod 755 $DST/wcp_chansync.sh 2>/dev/null
    WCP_CHANSYNC_LOG=$LOG sh $DST/wcp_chansync.sh watch &
    log "chansync watcher started pid=$!"
else
    log "chansync script missing at $SRC -> channel will not be auto-corrected"
fi

# --- pf 放行规则守护(background, starts IMMEDIATELY, also on the early-exit path below) ---
# 原厂连接管理器在 WLAN 状态变化时会重载 /etc/pf*.conf,冲掉 wcp_pf.sh 插入的 5000/5001/6030 等放行规则
# -> 手机 SYN 被丢、无线 CarPlay 起不来(11-10 根因)。守护循环每 3s 检查,丢了就补;已有连接状态不受影响。
# 关闭:touch /mnt/persist/wcp_pfwatch_off。
if [ -r $SRC/wcp_pfwatch.sh ]; then
    cp -f $SRC/wcp_pfwatch.sh $DST/wcp_pfwatch.sh 2>/dev/null
    chmod 755 $DST/wcp_pfwatch.sh 2>/dev/null
    WCP_PFWATCH_LOG=$LOG sh $DST/wcp_pfwatch.sh >/dev/null 2>&1 &
    log "pfwatch started pid=$!"
else
    log "pfwatch script missing at $SRC -> pf rules will not be re-applied after stock reloads"
fi

# idempotent: if the receiver is already up, leave it alone
if [ -f $DST/wcp_receiver.pid ]; then
    P=`cat $DST/wcp_receiver.pid 2>/dev/null`
    if [ -n "$P" ] && kill -0 $P 2>/dev/null; then log "receiver already running pid=$P -> exit"; exit 0; fi
fi

# fail-safe: all four artifacts must be present in the persistent home
for f in wcp_receiver wcp_video wcp_ctl.sh wcp_pf.sh; do
    [ -r $SRC/$f ] || { log "missing $SRC/$f -> fail-safe exit"; exit 0; }
done

# bounded wait for the AP (uap0) to be up AND addressed; fail-safe if it never comes.
# NOTE: wait for the interface itself (UP+RUNNING + its 10.x address), NOT for
# "status: active" -- the AP reports "active" only once a phone associates, but the
# receiver must be LISTENing on 5000 BEFORE the phone dials, so we start while the AP
# is still clientless ("status: no network").
#
# Auto hotspot (2026-08-29, real-car report: wireless CarPlay never connects when the owner
# has not ticked the stock "WLAN hotspot" box). The main path lives in the HMI: WcpHotspot
# (CarPlayWireless-CP jar) reads the stock WLAN state itself and ticks the stock hotspot
# checkbox for the user when it is off -- needed because uap0 can look UP/RUNNING/addressed
# even while the stock hotspot is off (bench 11-11). This is only the fallback: if uap0 is
# still down after 40s we drop /dev/shmem/wcp_hs_req. The stock state machine +
# connectionmanager do the rest and persist it. Never touches the WLAN driver; only acts if
# the stock checkbox really is off. Opt out: /mnt/persist/wcp_hs_off.
# The wait is therefore 240s instead of 120s (the HMI may still be booting at 40s).
_i=0
_hsreq=0
while [ $_i -lt 120 ]; do
    if ifconfig uap0 2>/dev/null | grep -q RUNNING && ifconfig uap0 2>/dev/null | grep -q 'inet 10\.'; then
        log "uap0 up+addressed after $((_i*2))s"
        break
    fi
    if [ $_i -eq 20 ] || [ $_i -eq 70 ]; then
        if [ -f /mnt/persist/wcp_hs_off ]; then
            [ $_hsreq -eq 0 ] && log "uap0 not up after $((_i*2))s; auto-hotspot off (/mnt/persist/wcp_hs_off)"
        else
            echo on > /dev/shmem/wcp_hs_req
            log "uap0 not up after $((_i*2))s -> asked HMI to turn the hotspot on (wcp_hs_req)"
        fi
        _hsreq=1
    fi
    sleep 2
    _i=$((_i+1))
done
if [ $_i -ge 120 ]; then log "uap0 not up after 240s -> fail-safe exit"; exit 0; fi
[ $_hsreq -eq 1 ] && log "hotspot came up after the auto-hotspot request"

# omonob display request; 2026-08-29
WCP_FPS=40
WCP_VIDEO_FPS=40
export WCP_FPS WCP_VIDEO_FPS
# Selected once by V7.5 from the actual cluster, never by phone/brand guess.
[ -r /mnt/persist/v75-wireless-display.conf ] || exit 1
. /mnt/persist/v75-wireless-display.conf
case "$WCP_ALT_W:$WCP_ALT_H" in 800:480|1010:376) ;; *) exit 1;; esac
WCP_ALT_FEED_PORT=9997
WCP_ALT_NO_SHOWUI=1
export WCP_ALT_W WCP_ALT_H WCP_ALT_FEED_PORT WCP_ALT_NO_SHOWUI

# stage the binaries/scripts into tmpfs and start (mirrors fs_03_start.sh)
for f in wcp_receiver wcp_video wcp_ctl.sh wcp_pf.sh; do
    cp -f $SRC/$f $DST/$f 2>/dev/null
    chmod 755 $DST/$f 2>/dev/null
done
log "staged `ls -ln $DST/wcp_receiver $DST/wcp_video 2>/dev/null | sed 's/   */ /g'`"

cd $DST
# wcp_video 是否自己切主屏显示上下文(WCP_VIDEO_DMDT):
#   CP 补丁 S3 接管时,HMI 自己进/出原厂 CarPlay 上下文(71 = HMI 透明画布 + displayable 59),我们的视频层
#   本就挂在 59 上,原厂会自然显示;wcp_video 再强切到自建上下文 95 会抢掉 HMI 的上下文,HMI 1~2s 后退出
#   画布 -> 主菜单"Apple CarPlay"进去黑屏(11-10 台架实测;关掉后各入口都正常)。所以此时 DMDT=0。
#   没有 CP / 已关闭(wcp_cp_off)/ 非 S3:HMI 不会切过去,保留旧的自动切换 DMDT=1。
VDMDT=1
_st=`cat /mnt/persist/wcp_cp_stage 2>/dev/null`
case "$_st" in 3*|S3*|s3*) ;; *) _st= ;; esac
if [ -n "$_st" ] && [ ! -f /mnt/persist/wcp_cp_off ] && ls /eso/hmi/lsd/jars/CarPlayWireless-CP-*.jar >/dev/null 2>&1; then
    VDMDT=0
fi
log "wcp_video DMDT=$VDMDT (cp stage='$_st')"

# Existing CarPlay 791 input/player is started independently by lsd.sh.

_pf_try=0
while [ $_pf_try -lt 15 ];do
    if WCP_WIDTH=1264 WCP_HEIGHT=640 WCP_WIDTH_MM=210 WCP_HEIGHT_MM=106 WCP_VIDEO_DMDT=$VDMDT sh $DST/wcp_ctl.sh start >> $LOG 2>&1;then
        break
    fi
    _pf_try=$((_pf_try+1))
    log "receiver not ready; retry=$_pf_try/15"
    sleep 2
done
[ $_pf_try -lt 15 ] || { log "PF/receiver readiness timeout; receiver remains unavailable";exit 1; }
# internet-sharing:台架上网走路由器 mlan0,系统却常把 /etc/pf.conf(只 NAT ppp0/ecm0)装上,
# 手机连热点没网 -> iOS 走不支持的现代 companion-link、不拨 5000。强制装带 mlan0 NAT 的
# pf.mlan0.conf,再让 wcp_pf.sh 基于它插入 5000 放行(detect 会认出 mlan0)。见 wcp_pf.sh。
# Preserve the active OEM uplink/NAT policy; wcp_pf.sh detects it.
# wcp_ctl completed PF readiness before receiver launch; the watcher preserves
# it across later OEM connectionmanager reloads.
log "5000 `netstat -an 2>/dev/null | grep '\.5000 ' | head -3`"
log "done"
exit 0
