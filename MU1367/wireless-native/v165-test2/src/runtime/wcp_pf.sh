#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Runtime-only PF overlay; preserve the active OEM uplink/NAT selection.
# Serialize both startup/watch callers with a kernel lock, then generate a
# private complete file and validate it before applying. No OEM file is edited.
GUARD=/mnt/app/carplaymaps/wireless-tune
case "${1:-}" in on|off|check) ;; *) echo PF_ACTION_REQUIRED;exit 1;;esac
if [ "${CPMAP_WCP_PF_LOCKED:-}" != "$$" ];then
 [ -x "$GUARD" ] || { echo PF_GUARD_MISSING;exit 1; }
 exec "$GUARD" pf "$1"
fi
umask 077
PFCTL=/mnt/app/armle/sbin/pfctl
SRC=/etc/pf.conf
SRCF=/dev/shmem/wcp_pf.src
DST=/dev/shmem/wcp_pf.$$.conf
NAT=/dev/shmem/wcp_pf.$$.nat
READY=/ramdisk/wcp-pf.ready
PENDING=/ramdisk/wcp-pf.ready.$$
ANCHOR='block in quick on $wlan_if from any to ($wlan_if)'
trap 'rm -f "$DST" "$NAT" "$PENDING"' 0
trap 'exit 1' 1 2 15
for C in ifconfig grep cat rm mv;do
 command -v "$C" >/dev/null 2>&1 || { echo "PF_COMMAND_MISSING=$C";exit 1; }
done
[ -x "$PFCTL" ] || { echo PFCTL_MISSING;exit 1; }
detect() {
 i1=;i2=
 "$PFCTL" -s nat > "$NAT" 2>/dev/null || return 1
 while read -r w1 w2 w3 w4 w5 w6 w7 rest;do
  [ "$w1" = nat ] && [ "$w6" = tagged ] && [ "$w7" = WLAN ] || continue
  if [ -z "$i1" ];then i1=$w4;else i2=$w4;break;fi
 done < "$NAT"
 case "$i1,$i2" in
 mlan0,*) SRC=/etc/pf.mlan0.conf;;
 ecm0,*) SRC=/etc/pf.ecm0.conf;;
 ppp0,ecm0) SRC=/etc/pf.conf;;
 ppp0,en0) SRC=/etc/pf.ppp0.conf;;
 *) echo "PF_NAT_NOT_READY interfaces=$i1,$i2";return 1;;
 esac
 [ -f "$SRC" ] && [ ! -L "$SRC" ]
}
generate() {
 n=0
 : > "$DST" || return 1
 while IFS= read -r line;do
  if [ "$line" = "$ANCHOR" ];then
   echo 'pass in quick on $wlan_if proto tcp from ($wlan_if:network) to ($wlan_if) port { 5000, 5001, 6030, 6031 } keep state allow-opts' >> "$DST" || return 1
   echo 'pass in quick on $wlan_if proto udp from ($wlan_if:network) to ($wlan_if) port { 5020, 6000, 6003, 6004, 6011, 6020 } keep state allow-opts' >> "$DST" || return 1
   n=$((n+1))
  fi
  echo "$line" >> "$DST" || return 1
 done < "$SRC"
 [ "$n" = 1 ] || { echo PF_OEM_ANCHOR_MISMATCH;return 1; }
}
case "$1" in
on|check)
 if [ "$1" = on ];then rm -f "$READY";fi
 ifconfig uap0 2>/dev/null | grep -q RUNNING || { echo PF_AP_NOT_READY;exit 1; }
 ifconfig uap0 2>/dev/null | grep -q 'inet 10\.' || { echo PF_AP_ADDRESS_NOT_READY;exit 1; }
 detect && generate || exit 1
 "$PFCTL" -n -f "$DST" || { echo PF_SYNTAX_FAILED;exit 1; }
 if [ "$1" = check ];then echo "PF_SYNTAX_OK source=$SRC";exit 0;fi
 "$PFCTL" -f "$DST" || { echo PF_APPLY_FAILED;exit 1; }
 echo "$SRC" > "$SRCF" || exit 1
 T=$("$GUARD" monotonic) || exit 1
 { echo WCPPF1;echo "$$";echo "$T";echo "$SRC"; } > "$PENDING" || exit 1
 mv "$PENDING" "$READY" || exit 1
 echo "PF_READY t_us=$T pid=$$ source=$SRC" ;;
off)
 rm -f "$READY"
 if ! detect;then
  [ -f "$SRCF" ] && [ ! -L "$SRCF" ] || exit 1
  SRC=$(cat "$SRCF")
  case "$SRC" in /etc/pf.conf|/etc/pf.mlan0.conf|/etc/pf.ppp0.conf|/etc/pf.ecm0.conf) ;; *) echo PF_RESTORE_SOURCE_INVALID;exit 1;;esac
 fi
 "$PFCTL" -n -f "$SRC" && "$PFCTL" -f "$SRC" || exit 1
 rm -f "$SRCF"
 echo "PF_OEM_RESTORED source=$SRC" ;;
esac
