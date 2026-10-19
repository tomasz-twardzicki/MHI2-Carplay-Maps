#!/usr/bin/env python3
"""Build a PRIVATE full-toolbox B2 test ZIP from the exact local factory files.

Generated files are ignored by git. No raw logs, credentials or GPS are read.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TOOLBOX = REPO / "releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4"
PACKAGE_NAME = "MU1427-route-guidance-B2-toolbox"
SPEC = importlib.util.spec_from_file_location("patch", HERE / "patch-driver.py")
patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock_driver", type=Path)
    parser.add_argument("stock_config", type=Path)
    parser.add_argument("--output", type=Path, default=HERE / "build")
    args = parser.parse_args()
    config = args.stock_config.read_bytes()
    if patch.sha(config) != "ce05524385ccae1167966d45c52ff60ac0c70fe0f46ac98d77a75f109a6bfa6c":
        parser.error("expected exact Phase A / factory MU1427 iap2.cfg")
    if b"[ident]" in config:
        parser.error("stock config already has an [ident] section")
    patched, manifest = patch.build(args.stock_driver.read_bytes())
    out = args.output.resolve()
    stage = out / "sd-card"
    if stage.exists():
        parser.error(f"{stage} already exists; choose a fresh --output directory")
    shutil.copytree(TOOLBOX, stage)
    payload = stage / "Custom/route_guidance_b1"
    payload.mkdir()
    (payload / "ipod-drvr-iap2.so").write_bytes(patched)
    (payload / "iap2.cfg").write_bytes(config.rstrip(b"\n") + b"\n\n# Experimental MU1427 route guidance B1\n[ident]\nsendmsgs=0x5200,0x5203\nrecvmsgs=0x5201,0x5202,0x5204\n")
    (payload / "VERSION").write_text(f"{manifest['build']}-{manifest['patched_sha256'][:8]}\n")
    # Match the fixed sizes and build ID accepted by the on-unit script.
    if len(patched) != 741944 or manifest['patched_sha256'] != "0763b7aa448837651ca59ce8d3e219c0b157df05204c9a2037f895001b1655b6":
        parser.error("driver changed; update the installer's build ID and sizes before packaging")
    if (payload / "iap2.cfg").stat().st_size != 6006:
        parser.error("config changed; update the installer's expected size before packaging")
    manifest["config_stock_sha256"] = patch.sha(config)
    manifest["config_patched_sha256"] = patch.sha((payload / "iap2.cfg").read_bytes())
    manifest["installer_revision"] = "B2-install-r1"
    (payload / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    scripts = stage / "Toolbox/scripts"
    shutil.copy2(HERE / "rg-b1.sh", scripts / "cpmap_rgi_b1.sh")
    for action in ("install", "restore", "status"):
        wrapper = scripts / f"cpmap_rgi_{action}.sh"
        # Installed scripts also work on RCC (/net/mmx). Restore needs no SD.
        wrapper.write_text('''#!/bin/ksh
S=/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_b1.sh
[ -f "$S" ] || S=/net/mmx/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_b1.sh
''' + ('''for V in /net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0; do
    P=$V/Custom/route_guidance_b1
    if [ -s "$P/VERSION" ]; then /bin/ksh "$S" install "$P"; exit $?; fi
done
echo "CPMAP_RGI_FAIL=SD_PAYLOAD_NOT_FOUND"
exit 1
''' if action == "install" else f'/bin/ksh "$S" {action}\n'))
        wrapper.chmod(0o755)
    menu = stage / "Toolbox/GEM/carplay-maps-vc.esd"
    with menu.open("ab") as f:
        for action, label in (("install", "EXPERIMENTAL MU1427: install route guidance B1"), ("status", "Route guidance B1 status"), ("restore", "Restore factory iAP2 driver and config (B1)")):
            f.write(f'\r\nscript\r\n    value   sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_{action}.sh"\r\n    label   "{label}"\r\n'.encode())
    # Replace the old mount/PPS research scan; C2 captures the live log first.
    shutil.copy2(HERE / "capture-rgi.sh", scripts / "cpmap_navrecon.sh")
    menu.write_bytes(menu.read_bytes().replace(b"install route guidance B1", b"install route guidance B2").replace(b"Route guidance B1 status", b"Route guidance B2 status").replace(b"(B1)", b"(B1/B2)").replace(b"Collect navigation research data to SD (Log/cpmap-navrecon-*)", b"Capture route-guidance data to SD (C2)"))
    # Include corresponding source and the test instructions with the private ZIP.
    source = payload / "source"
    source.mkdir()
    for name in ("driver-hooks.S", "patch-driver.py", "rg-b1.sh", "build-test-package.py", "test-driver.py", "test-install.py", "capture-rgi.sh", "test-capture.py", "rgi_decode.py", "test-rgi-decode.py", "DECODER.md", "TEST-B2.md", "B1-RESULTS.md", "B2-RESULTS.md", "README.md"):
        shutil.copy2(HERE / name, source / name)
    shutil.copy2(REPO / "LICENSE", source / "LICENSE")
    archive = out / f"{PACKAGE_NAME}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(stage))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n")
    print(archive)
    print(f"sha256={digest}")
    print(f"Driver: {manifest['patched_sha256']}")


if __name__ == "__main__":
    main()
