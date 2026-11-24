#!/usr/bin/env python3
"""Host-only audit of the pinned 791 receiver; never edits or runs a payload.

This checks the reviewed startup site and direct ARM branches, not arbitrary
control flow, successful QNX loading, MFi authentication or vehicle acceptance.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import zipfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def executable_segments(data):
    require(data[:7] == b"\x7fELF\x01\x01\x01", "Expected ELF32 little-endian")
    require(struct.unpack_from("<H", data, 18)[0] == 40, "Expected ARM")
    offset = struct.unpack_from("<I", data, 28)[0]
    entry_size, count = struct.unpack_from("<HH", data, 42)
    require(entry_size == 32, "Unexpected program-header size")
    segments = []
    for index in range(count):
        kind, file_offset, address, _, size, _, flags, _ = struct.unpack_from(
            "<8I", data, offset + index * entry_size
        )
        require(file_offset + size <= len(data), "Truncated ELF segment")
        if kind == 1 and flags & 1:
            segments.append((file_offset, address, size))
    require(segments, "No executable LOAD segments")
    return segments


def audit(upstream_root, baseline_zip):
    pins = json.loads(Path(__file__).with_name("UPSTREAM.json").read_text())
    payload = upstream_root / pins["payload_prefix"]
    files = {}
    for name, expected in pins["files_sha256"].items():
        data = (payload / name).read_bytes()
        require(sha256(data) == expected, "Unreviewed upstream file: " + name)
        files[name] = data
    require(sha256(baseline_zip.read_bytes()) == pins["baseline_zip_sha256"],
            "Expected published v1.5.3 ZIP")

    receiver = files["wireless/profiles/AID12.3/wcp_receiver"]
    segments = executable_segments(receiver)
    # Upstream's reviewed former startup call now supplies success (mov r0, #0).
    # Keep the following cmp/branch in the signature to bind this to its context.
    site, helper = 0xE1CA8, 0xEC348
    expected = bytes.fromhex("0000a0e30470a0e3000050e3b5ffff1a")
    matching_sites = [receiver[off + site - va:off + site - va + len(expected)]
                      for off, va, size in segments
                      if va <= site and site + len(expected) <= va + size]
    require(matching_sites == [expected], "Startup licence site changed")
    callers = []
    for off, va, size in segments:
        for position in range(0, size - 3, 4):
            word = struct.unpack_from("<I", receiver, off + position)[0]
            # ARM B/BL only; excludes BLX immediate and Thumb decoding.
            if word & 0x0E000000 != 0x0A000000 or word >> 28 == 15:
                continue
            immediate = word & 0xFFFFFF
            if immediate & 0x800000:
                immediate -= 0x1000000
            if va + position + 8 + immediate * 4 == helper:
                callers.append(hex(va + position))
    require(not callers, "Direct ARM branch to retained licence helper")
    require(b"/dev/i2c8\0" in receiver, "Expected MFi device reference")
    require(b"/mnt/persist/carplay_mirror.lic\0" in receiver,
            "Expected retained licence code/data")

    launcher = files["wireless/profiles/AID12.3/wireless-receiver-exec"]
    for name in ("wireless/profiles/AID12.3/wcp_receiver",
                 "wireless/profiles/AID12.3/libomonob-wireless-maps.so",
                 "wireless/common/runtime/libv75-transport.so"):
        require(pins["files_sha256"][name].encode() + b"\0" in launcher,
                "Launcher hash contract changed: " + name)

    with zipfile.ZipFile(io.BytesIO(files["profiles/MU1367/791/VCMenu.jar"])) as menu:
        phone_classes = sorted(n for n in menu.namelist()
                               if n.startswith("org/omonob/phone/") and n.endswith(".class"))
    require(len(phone_classes) == 15, "Phone closure changed")
    collisions = []
    jar_count = 0
    with zipfile.ZipFile(baseline_zip) as baseline:
        for name in baseline.namelist():
            if not name.endswith(".jar"):
                continue
            jar_count += 1
            with zipfile.ZipFile(io.BytesIO(baseline.read(name))) as jar:
                for member in jar.namelist():
                    if member.endswith(".class") and member.startswith((
                        "org/omonob/phone/", "wcp", "org/omonob/cpmap/wireless/", "system/input/"
                    )):
                        collisions.append(name + ":" + member)
    require(not collisions, "v1.5.3 class collisions: " + repr(collisions))
    return {
        "status": "offline-audit-pass",
        "upstream_commit": pins["commit"],
        "profile": pins["profile"],
        "pinned_files_checked": len(files),
        "baseline_zip_sha256": pins["baseline_zip_sha256"],
        "baseline_jars_scanned": jar_count,
        "baseline_class_collisions": collisions,
        "phone_classes_to_package_separately": phone_classes,
        "startup_licence_site": hex(site),
        "startup_licence_site_supplies_success": True,
        "retained_licence_helper": hex(helper),
        "direct_arm_branches_to_licence_helper": callers,
        "launcher_embedded_hashes_match": True,
        "mfi_device_reference": "/dev/i2c8",
        "qnx_execution_tested": False,
        "vehicle_tested": False,
        "scope": "Pinned inputs and static startup-site audit only; not a full release audit."
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--baseline-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.upstream_root, args.baseline_zip)
    except (OSError, ValueError, struct.error, zipfile.BadZipFile) as error:
        print("WIRELESS_UPSTREAM_AUDIT_FAIL: " + str(error), file=sys.stderr)
        return 1
    report = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(report)
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
