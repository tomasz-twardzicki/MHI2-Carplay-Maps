#!/bin/sh
# Wireless CarPlay Maps. Maintainer: omonob. Source date: 2026-08-29.
# CarPlay Wireless - btstack injection wrapper.
# Recover from the green menu: Customization -> CarPlay-Wireless -> RESTORE BT/WiFi.
#
# Inert unless /mnt/persist/btwcp_enable exists AND the lib is readable. When it is not
# armed (or the lib is gone) this just execs the stock btstack, so Bluetooth/WiFi behave
# exactly as factory. BTWCP_PRESENT alone does nothing until /dev/shmem/btwcp.present is
# written, and /dev/shmem is wiped on every reboot (self-healing).
#
# Hotspot credentials: NONE here, by design. libbtwcp.so reads the live SSID/PSK/channel
# from the car's own /tmp/uaputl.cfg at the moment it builds 0x4301/0x5703 (WiFi is long up
# and uaputl.cfg is ready by the time the phone connects). Never bake a password into this
# file. Optionally export BTWCP_SSID / BTWCP_CHAN (NOT secret) as a fallback only; never
# BTWCP_PASS.
REAL=/eso/bin/apps/btstack
LIB=/mnt/ota/libbtwcp.so
# Authorized local bench build: no application FAZIT license gate.
# User switch (2026-08-29): App-Connect "Wireless CarPlay" off = /mnt/persist/btwcp_off (cpm_sync persists it).
if [ -f /mnt/persist/btwcp_enable ] && [ ! -f /mnt/persist/btwcp_off ] && [ -r "$LIB" ]; then
    GUARD=/mnt/app/carplaymaps/libcpmap-bt-session.so
    if ! LD_PRELOAD= /mnt/app/carplaymaps/wireless-receiver-exec --bt-guard-status >/dev/null 2>&1;then
        echo 'CPMAP_BT_GUARD_HASH_FAILED_USING_OEM_BT' >&2
        exec "$REAL" "$@"
    fi
    # Boot-time autostart of the self-built wireless-CarPlay receiver. Kicked HERE, BEFORE
    # LD_PRELOAD is set and with LD_PRELOAD explicitly empty, so the helper (and the
    # wcp_receiver/wcp_video it starts) NEVER inherit libbtwcp.so -- that lib is a
    # btstack-only interposer and SIGSEGVs any other process. Launched detached via 'on -d'
    # with absolute /bin paths so it never delays btstack and does not depend on PATH.
    # Double-gated: only when btwcp is armed (this branch) AND /mnt/persist/wcp_autostart
    # exists. Disable without editing this file: rm /mnt/persist/wcp_autostart.
    if [ -f /mnt/persist/wcp_autostart ] && [ -r /mnt/ota/wcp_autostart.sh ]; then
        LD_PRELOAD= /bin/on -d /bin/sh /mnt/ota/wcp_autostart.sh >/dev/null 2>&1 &
    fi
    LD_PRELOAD="$LIB"
    # Only our exact, hash-checked compatibility shim may override the two
    # custom USB-priority probes after an explicit wireless-card selection.
    # OEM drivers and all other programs continue seeing the physical USB.
    TRANSPORT=/mnt/app/carplaymaps/libv75-transport.so
    if [ -r "$TRANSPORT" ] && /mnt/app/carplaymaps/wireless-receiver-exec --transport-status >/dev/null 2>&1; then
        LD_PRELOAD="$TRANSPORT:$LIB"
        V75_WCP_TRANSPORT=1
        export V75_WCP_TRANSPORT
    fi
    LD_PRELOAD="$GUARD:$LD_PRELOAD"
    CPMAP_BT_GUARD=1
    export CPMAP_BT_GUARD
    BTWCP_PRESENT=1
    export LD_PRELOAD BTWCP_PRESENT
fi
exec "$REAL" "$@"
