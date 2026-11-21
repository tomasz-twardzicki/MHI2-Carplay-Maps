#!/bin/sh
# Wireless CarPlay Maps. Maintainer: omonob. Source date: 2026-08-29.
# wcp_pfwatch.sh -- keep the wireless-CarPlay pf pass rules loaded.
#
# Why: wcp_pf.sh inserts "pass in quick on uap0 ... port {5000,5001,6030}" (+UDP) before the stock
# "block in quick on $wlan_if from any to ($wlan_if)". The connection manager later RELOADS the stock
# /etc/pf*.conf whenever WLAN state changes (uplink associates, hotspot client joins ...), silently
# wiping our rules. Then the phone's SYN to 10.173.189.1:5000 is dropped and wireless CarPlay never
# starts (11-10 bench: phone SYN x10, no SYNACK; re-applying the rules -> full session at once).
#
# This loop checks every 3s and re-runs "wcp_pf.sh on" (re-detecting which stock file is active) when
# our rule is missing. pfctl -f keeps existing states, so a running session is not cut.
# Single instance (pidfile in /dev/shmem). Disable: touch /mnt/persist/wcp_pfwatch_off (checked each loop).
PFCTL=/mnt/app/armle/sbin/pfctl
PFSH=/dev/shmem/wcp_pf.sh
[ -r $PFSH ] || PFSH=/mnt/ota/wcp_pf.sh          # autostart 提前退出时 /dev/shmem 里可能还没有
PID=/dev/shmem/wcp_pfwatch.pid
LOG=${WCP_PFWATCH_LOG:-/dev/shmem/wcp_pfwatch.log}
OFF=/mnt/persist/wcp_pfwatch_off
MARK='from (uap0:network) to (uap0) port = 5000'

if [ -f $PID ]; then
    P=`cat $PID 2>/dev/null`
    if [ -n "$P" ] && kill -0 $P 2>/dev/null; then echo "[pfwatch] already running pid=$P"; exit 0; fi
fi
echo $$ > $PID
echo "[pfwatch] start pid=$$" >> $LOG
n=0
while :; do
    [ -f $OFF ] && { echo "[pfwatch] off flag -> exit" >> $LOG; rm -f $PID; exit 0; }
    c=`$PFCTL -s rules 2>/dev/null | grep -c "$MARK"`
    if [ "$c" = 0 ] && [ -r $PFSH ]; then
        n=$((n+1))
        rm -f /ramdisk/wcp-pf.ready
        # Source detection and all shared receipts are serialized by the
        # PF script. Never mutate its source receipt outside that lock.
        r=`sh $PFSH on 2>&1 | tail -1`
        # 前 20 次逐条记;之后每 100 次记一次(开机早期 NAT 还没起来时会连续失败,别刷爆日志)
        if [ $n -le 20 ] || [ $((n % 100)) = 0 ]; then
            echo "[pfwatch] our rules missing -> re-apply #$n: $r" >> $LOG
        fi
    fi
    sleep 3
done
