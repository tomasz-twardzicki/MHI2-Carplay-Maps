#!/usr/bin/env python3
"""Build the additive v1.6.0-e-test1 candidate over the exact v1.5.3 ZIP.

Host tool. OEM bytes are read only from the supplied firmware/stock inputs;
the package contains no extracted OEM replacement or MU1102 connection manager.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import zipfile
from diagnostics import add as add_wireless_diagnostics

HERE = Path(__file__).resolve().parent
VERSION = "1.6.0-e-test1"
sha = lambda b: hashlib.sha256(b).hexdigest()


def run(*args):
    subprocess.run(list(map(str, args)), check=True)


def replace(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def quote(value):
    return shlex.quote(str(value))


def deterministic_jar(path, entries):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in sorted(entries.items()):
            assert struct.unpack_from(">H", data, 6)[0] == 46, name
            item = zipfile.ZipInfo(name, (2026, 11, 17, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            z.writestr(item, data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline-zip", "baseline-source", "upstream-root", "toolchain", "python", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--clang", type=Path, default=Path("/Library/Developer/CommandLineTools/usr/bin/clang"))
    a = p.parse_args()
    pins = json.loads((HERE / "UPSTREAM.json").read_text())
    assert sha(a.baseline_zip.read_bytes()) == pins["baseline_zip_sha256"], "Exact published v1.5.3 ZIP required"
    source = a.baseline_source / "MU1367/integration"
    provenance = json.loads((HERE / "src/PROVENANCE.json").read_text())
    assert sha((a.baseline_source / provenance["source"]).read_bytes()) == provenance["baseline_sha256"]
    up = a.upstream_root / pins["payload_prefix"]
    for name, expected in pins["files_sha256"].items():
        assert sha((up / name).read_bytes()) == expected, name
    proof = json.loads((HERE / "FIRMWARE-VERIFICATION.json").read_text())
    for name, item in proof["native_linkage"]["payloads"].items():
        assert sha((up / "wireless" / name).read_bytes()) == item["sha256"], name
    for name, expected in proof["hmi"]["upstream_jars_sha256"].items():
        assert sha((up / name).read_bytes()) == expected, name
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sd = out / "sd-card"
    sd.mkdir()
    with zipfile.ZipFile(a.baseline_zip) as z:
        for item in z.infolist():
            assert not Path(item.filename).is_absolute() and ".." not in Path(item.filename).parts
        z.extractall(sd)
    custom = sd / "Custom"
    layer = custom / "carplay_mu1367_wireless_native"
    payload = layer / "payload"
    payload.mkdir(parents=True)
    shutil.copy2(custom / "carplay_mu1367/verify", layer / "verify")
    rows = []

    def add(name, target, data, mode="644", before="absent", kind="copy"):
        key = "k%02d" % len(rows)
        (payload / name).write_bytes(data)
        rows.append(dict(key=key, source=name, target=target, mode=mode, before=before, kind=kind, sha256=sha(data)))

    mappings = []
    for file_list in (up / "wireless/common-files.tsv", up / "wireless/profiles/AID12.3/files.tsv"):
        for line in file_list.read_text().splitlines():
            src, target, mode = line.split("\t")
            # Keep the v1.5.3 wired geometry/fps defaults and runtime.
            if target in ("/mnt/persist/altscreen.conf", "/mnt/persist/altscreen.geom"):
                continue
            data = (up / "wireless" / src).read_bytes()
            if src.endswith("wcp_autostart.sh"):
                data = replace(data.decode(), "/mnt/app/armle/sbin/pfctl -f /etc/pf.mlan0.conf >> $LOG 2>&1", "# Preserve the active OEM uplink/NAT policy; wcp_pf.sh detects it.").encode()
            if src.endswith("wcp_ctl.sh"):
                data = replace(data.decode(), "        cat $WCP_DATA/pk.txt 2>/dev/null | sed 's/^/pk(给 btwcp 0x4301 参数4)=/'", "        # Pairing identity remains in the per-unit store; do not print it.").encode()
            name = Path(src).name
            add(name, target, data, mode)
            mappings.append(dict(source=src, target=target, upstream_sha256=sha((up / "wireless" / src).read_bytes()), packaged_sha256=sha(data)))

    phone = {}
    with zipfile.ZipFile(up / "profiles/MU1367/791/VCMenu.jar") as z:
        for name in z.namelist():
            if name.startswith("org/omonob/phone/") and name.endswith(".class"):
                phone[name] = z.read(name)
    assert len(phone) == 15
    deterministic_jar(out / "MU1367WirelessPhone.jar", phone)
    add("MU1367WirelessPhone.jar", "/mnt/app/eso/hmi/lsd/jars/MU1367WirelessPhone.jar", (out / "MU1367WirelessPhone.jar").read_bytes())

    # Build only the supervisor: the published bridge/core/menu/wrapper stay intact.
    native = out / "native"
    runtime = native / "src/runtime"
    runtime.mkdir(parents=True)
    base_runtime = source / "src/runtime/vc-runtime/runtime"
    header_pins = {}
    for f in base_runtime.glob("*.h"):
        shutil.copy2(f, runtime / f.name)
        header_pins[f.name] = sha(f.read_bytes())
    (native / "src/mirror").mkdir()
    shutil.copy2(source / "src/runtime/vc-runtime/mirror/carplay_yuv_shm.h", native / "src/mirror/carplay_yuv_shm.h")
    shutil.copy2(HERE / "src/carplay_cluster_supervisor.c", runtime / "carplay_cluster_supervisor.c")
    shutil.copy2(HERE / "src/wireless_session.h", runtime / "wireless_session.h")
    qnx = a.toolchain.resolve() / "sdp/target/qnx6"
    flags = ["--target=armv7-none-eabi", "-D__QNXNTO__", "-D__QNX__", "-D__ARM__", "-D__LITTLEENDIAN__", "--sysroot=" + str(qnx), "-isystem", str(qnx / "usr/include"), "-march=armv7-a", "-mfloat-abi=softfp", "-mfpu=vfpv3-d16", "-mno-unaligned-access", "-fno-short-enums", "-fno-builtin", "-fno-stack-protector", "-std=gnu99", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-ffile-prefix-map=" + str(native) + "=."]
    docker = ["docker", "--context", "colima-cpmap-rgi"]
    sdk_id = subprocess.check_output(docker + ["image", "inspect", "cpmap-qnx65-sdp", "--format", "{{.Id}}"], text=True).strip()
    assert sdk_id == "sha256:93b565ff63ba51c470c1a1e70a6d16607d36df502dfb20ae63a69911f8529bea"
    lib = "/opt/qnx650/target/qnx6/armle-v7/lib"
    built = []
    for number in (1, 2):
        run(a.clang, *flags, "-c", runtime / "carplay_cluster_supervisor.c", "-o", native / ("supervisor%d.o" % number))
        cmd = "arm-unknown-nto-qnx6.5.0eabi-ld -m armnto -Qy --dynamic-linker /usr/lib/ldqnx.so.2 -L{0} {0}/crt1.o {0}/crti.o {0}/crtbegin.o /w/supervisor{1}.o -lc {0}/crtend.o {0}/crtn.o -o /w/supervisor{1}".format(lib, number)
        run(*docker, "run", "--rm", "--pull=never", "--network=none", "-v", str(native) + ":/w", "cpmap-qnx65-sdp", "sh", "-c", cmd)
        built.append((native / ("supervisor%d" % number)).read_bytes())
    assert built[0] == built[1], "Supervisor rebuild differs"
    supervisor_before = sha((custom / "carplay_mu1367_settings/carplay-cluster-supervisor").read_bytes())
    add("carplay-cluster-supervisor", "/mnt/app/carplaymaps/carplay-cluster-supervisor", built[0], "755", supervisor_before)

    merge = (up / "common/merge-wireless.sh").read_text()
    merge = replace(merge, 'prefix "WirelessMapsBootstrap.jar"', 'prefix "WirelessMapsBootstrap.jar:" prefix "MU1367WirelessPhone.jar"')
    merge = replace(merge, "|WirelessMapsBootstrap)\\.jar", "|WirelessMapsBootstrap|MU1367WirelessPhone)\\.jar")
    (layer / "merge-wireless.sh").write_text(merge)
    shutil.copy2(up / "wireless/config-patch", layer / "config-patch")
    # Fixed generated outputs are tracked in the same snapshot as every new file.
    stock = proof["factory_files"]["50"]
    for name, target, before, kind in [
        ("connectivity", "/mnt/system/etc/eso/production/connectivity.json", proof["production_configs"]["50"]["connectivity.json"]["sha256"], "connectivity"),
        ("si", "/mnt/system/etc/eso/production/smartphone_integrator.json", proof["production_configs"]["50"]["smartphone_integrator.json"]["sha256"], "si"),
        ("bundles", "/mnt/app/eso/hmi/lsd/config/bundles.properties", stock["eso/hmi/lsd/config/bundles.properties"]["sha256"], "bundles"),
    ]:
        add(name, target, b"", "644", before, kind)
    # Explicitly enabling wireless may remove an old off marker; preserve it for removal.
    add("off", "/mnt/persist/btwcp_off", b"", "644", "optional", "missing")
    add("boot", "/mnt/app/eso/hmi/lsd/lsd.sh", b"", "755", "boot", "lsd")

    baseline_checks = {
        "/mnt/app/eso/bin/apps/btstack": stock["eso/bin/apps/btstack"]["sha256"],
        "/mnt/app/eso/bin/apps/connectionmanager": stock["eso/bin/apps/connectionmanager"]["sha256"],
        "/mnt/app/carplaymaps/altscreen-most-bridge": sha((custom / "carplay_mu1367_guidance_v3/6/altscreen-most-bridge").read_bytes()),
        "/mnt/app/carplaymaps/dio_manager.wrapper.sh": sha((custom / "carplay_mu1367_settings/dio_manager.wrapper.sh").read_bytes()),
        "/mnt/app/eso/bin/apps/dio_manager": sha((custom / "carplay_mu1367_settings/dio_manager.wrapper.sh").read_bytes()),
        "/mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar": sha((custom / "carplay_mu1367_artwork/CarPlayMU1367Audio.jar").read_bytes()),
    }
    pairs = set()
    versions = set()
    for folder in ("carplay_mu1367_guidance_v3", "carplay_mu1367_v3_turn_cards"):
        for variant in ("6", "6-road", "7", "7-road"):
            base = custom / folder / variant
            pairs.add((sha((base / "core.so").read_bytes()), sha((base / "VCMenu.jar").read_bytes())))
            if folder == "carplay_mu1367_guidance_v3": versions.add((base / "VERSION").read_text().strip())
    table = "JXE_SHA=" + proof["hmi"]["fresh_jxe_sha256"] + "\n"
    table += "KEYS=" + quote(" ".join(r["key"] for r in rows)) + "\n"
    table += "REVERSE_KEYS=" + quote(" ".join(r["key"] for r in reversed(rows))) + "\n"
    for fn, field in (("target", "target"), ("mode", "mode")):
        table += fn + '(){ case "$1" in\n'
        for r in rows:
            value = "$M" + r[field] if fn == "target" else r[field]
            table += ' ' + r["key"] + ') echo "' + value + '";;\n'
        table += " *) return 1;;esac; }\n"
    table += 'before_ok(){ case "$1" in\n'
    for r in rows:
        before = r["before"]
        command = 'absent "$2"' if before == "absent" else 'regular "$2" || absent "$2"' if before == "optional" else 'regular "$2" && /bin/ksh -n "$2"' if before == "boot" else 'check "$2" ' + quote(before)
        table += ' ' + r["key"] + ') ' + command + ';;\n'
    table += ' *) return 1;;esac; }\n'
    table += 'stage_payload(){ case "$1" in\n'
    for r in rows:
        kind = r["kind"]
        if kind == "copy": command = 'cp "$P/payload/' + r["source"] + '" "$2" && check "$2" ' + r["sha256"]
        elif kind == "missing": command = 'return 0'
        elif kind in ("si", "connectivity"): command = '"$P/config-patch" ' + kind + ' "$(target "$1")" "$2"'
        else: command = '/bin/sh "$P/merge-wireless.sh" ' + kind + ' "$(target "$1")" "$2" && ' + ('/bin/ksh -n "$2"' if kind == "lsd" else 'regular "$2"')
        table += ' ' + r["key"] + ') ' + command + ';;\n'
    table += ' *) return 1;;esac; }\n'
    table += 'baseline_ok(){\n'
    for path, expected in baseline_checks.items(): table += ' check "$M' + path + '" ' + expected + ' || return 1\n'
    table += ' [ "$(cat "$APP/carplay-mu1367-guidance-v3/STATE" 2>/dev/null)" = installed ] || return 1\n'
    table += ' case "$(cat "$APP/carplay-mu1367-guidance-v3/VERSION" 2>/dev/null)" in ' + '|'.join(sorted(versions)) + ') ;; *) return 1;;esac\n'
    table += ' CORE=$(digest "$APP/carplaymaps/core.so") && MENU=$(digest "$APP/eso/hmi/lsd/jars/VCMenu.jar") || return 1\n'
    table += ' case "$CORE:$MENU" in ' + '|'.join(x + ':' + y for x,y in sorted(pairs)) + ') ;; *) return 1;;esac\n'
    table += ' return 0\n}\n'
    build = "MU1367-wireless-native-" + sha((json.dumps(rows, sort_keys=True) + table + (HERE / "control.sh").read_text()).encode())[:12]
    (layer / "control.sh").write_text((HERE / "control.sh").read_text().replace("@BUILD@", quote(build)).replace("@TABLE@", table))
    (layer / "VERSION").write_text(build + "\n")
    checks = []
    for f in sorted(layer.rglob("*")):
        if f.is_file(): checks.append('check "$P/' + str(f.relative_to(layer)) + '" ' + sha(f.read_bytes()) + ' || return 1')
    (layer / "payload-check.sh").write_text("# SPDX-License-Identifier: GPL-3.0-or-later\n" + "\n".join(checks) + "\n")

    gem = sd / "Toolbox/GEM/carplay-maps-vc-wireless.esd"
    text = 'screen Wireless-CarPlay-Test carplay-maps-vc\n\nkeyValue\n    value String sys 0x00000000 0\n    label "v1.6.0-e test1 - wireless connection and video"\n    poll 0\n'
    for action, label in [("install", "Enable wireless test layer (reboot)"), ("uninstall", "Remove wireless and restore v1.5.3 (reboot)"), ("recover", "Recover interrupted wireless install (reboot)"), ("status", "Wireless test layer status")]:
        text += '\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_wireless_' + action + '.sh"\n    label "' + label + '"\n'
        wrapper = (sd / "Toolbox/scripts/cpmap_suite_status.sh").read_text()
        wrapper = wrapper.replace("carplay_mu1367_guidance_v3", "carplay_mu1367_wireless_native").replace("actions.sh", "control.sh")
        wrapper = wrapper.replace('"$P/control.sh" status "$P"', '"$P/control.sh" ' + action + ' "$P"')
        (sd / ("Toolbox/scripts/cpmap_wireless_" + action + ".sh")).write_text(wrapper)
    gem.write_text(text)
    add_wireless_diagnostics(sd)
    # Existing update/tuning/reset actions must not invalidate the wireless snapshot.
    for script in (sd / "Toolbox/scripts").glob("cpmap_suite_*.sh"):
        s = script.read_text()
        if any(('"$P/actions.sh" ' + action + ' "$P"') in s for action in ("install", "uninstall", "recover", "restore-oem", "enable-cards", "disable-cards", "recover-cards")):
            guard = '\nW=${CPMAP_TEST_ROOT:-}\nif [ -z "$W" ] && [ ! -s /ifs/lsd.jxe ];then W=/net/mmx;fi\nif [ -s "$W/mnt/app/carplay-mu1367-wireless-native/STATE" ] && [ "$(cat "$W/mnt/app/carplay-mu1367-wireless-native/STATE")" != removed ];then\n echo REMOVE_OR_RECOVER_WIRELESS_LAYER_AND_REBOOT_FIRST\n exit 1\nfi\n'
            script.write_text(replace(s, "set -u\n", "set -u\n" + guard))
    notice = "Experimental wireless layer built from omonob's pinned Wireless CarPlay Maps V3.1 payload. Reuse/modification permission recorded in FEASIBILITY.md. Original licences/notices remain applicable to opaque dependencies.\n"
    (sd / "WIRELESS-NOTICE.txt").write_text(notice)
    shutil.copy2(a.upstream_root / "CREDITS.md", layer / "UPSTREAM-CREDITS.md")
    shutil.copy2(a.upstream_root / "LICENSE", layer / "UPSTREAM-LICENSE")
    shutil.copytree(HERE / "src", layer / "source")
    for f in ("control.sh", "build.py", "UPSTREAM.json", "FIRMWARE-VERIFICATION.json"):
        shutil.copy2(HERE / f, layer / "source" / f)
    manifest = dict(version=VERSION, build_id=build, baseline_zip_sha256=pins["baseline_zip_sha256"], upstream_commit=pins["commit"], rows=rows, baseline_checks=baseline_checks, baseline_core_menu_pairs=sorted(pairs), upstream_mapping=mappings, supervisor_reproducible=True, supervisor_sdk_image=sdk_id, baseline_header_sha256=header_pins, on_unit_validated=False, wireless_information_features_integrated=False, native_menu_switch_integrated=False, installation_tested=False)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (layer / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for f in layer.rglob("*"):
        if f.is_file(): f.chmod(0o755 if f.name in ("control.sh", "verify", "config-patch") else 0o644)
    print("Built staged candidate", out, build)


if __name__ == "__main__":
    main()
