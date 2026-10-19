#!/usr/bin/env python3
"""Build a diagnostics-only full-toolbox SD layout. No experimental driver.

Capture C2 replaces the hanging research collector. The route-guidance restore/status
entries remain available; there is no B1 install entry or driver payload.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TOOLBOX = REPO / "releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "build-capture-C2")
    args = parser.parse_args()
    out = args.output.resolve()
    stage = out / "sd-card"
    if stage.exists(): parser.error("choose a fresh output directory")
    shutil.copytree(TOOLBOX, stage)
    scripts = stage / "Toolbox/scripts"
    shutil.copy2(HERE / "capture-rgi.sh", scripts / "cpmap_navrecon.sh")
    shutil.copy2(HERE / "rg-b1.sh", scripts / "cpmap_rgi_b1.sh")
    menu = stage / "Toolbox/GEM/carplay-maps-vc.esd"
    data = menu.read_bytes().replace(b"Collect navigation research data to SD (Log/cpmap-navrecon-*)", b"Capture route-guidance data to SD (C2, no driver changes)")
    for action, label in (("status", "Route guidance B1 status"), ("restore", "Restore factory iAP2 driver and config (B1)")):
        script = scripts / f"cpmap_rgi_{action}.sh"
        script.write_text(f'''#!/bin/ksh
S=/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_b1.sh
[ -f "$S" ] || S=/net/mmx/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_b1.sh
/bin/ksh "$S" {action}
''')
        script.chmod(0o755)
        data += f'\r\nscript\r\n    value   sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_{action}.sh"\r\n    label   "{label}"\r\n'.encode()
    menu.write_bytes(data)
    source = stage / "Custom/route_guidance_capture/source"
    source.mkdir(parents=True)
    for name in ("capture-rgi.sh", "build-capture-package.py", "test-capture.py", "rg-b1.sh", "B1-RESULTS.md"):
        shutil.copy2(HERE / name, source / name)
    shutil.copy2(REPO / "LICENSE", source / "LICENSE")
    archive = out / "MU1427-route-guidance-C2-diagnostics-toolbox.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob("*")):
            if p.is_file(): z.write(p, p.relative_to(stage))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n")
    print(archive)
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
