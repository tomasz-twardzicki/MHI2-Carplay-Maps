#!/usr/bin/env python3
"""Build B3 from the exact factory driver plus the reproducible B2 baseline.

Adds a bounded virtual-file handoff without imports, new ELF mappings, global
writable memory, threads, or producer I/O. B2 source/output remain unchanged.
"""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("b2", HERE / "patch-driver.py")
b2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b2)
POOL_SIZE = 0x8140
NATIVE = {
    "native_clock_gettime": 0x48F8,
    "native_calloc": 0x4A3C, "native_realloc": 0x4B14,
    "native_malloc": 0x49B8, "native_free": 0x4D48,
    "native_memcpy": 0x4988, "native_memset": 0x4B80,
    "native_attr_init": 0x494C, "native_read_verify": 0x4BB0,
    "native_reply": 0x4CF4, "stock_fsys_init_return": 0x90A0,
    "stock_fsys_read_resume": 0x9264, "stock_link_destroy_resume": 0x10BAC,
}
HOOKS = {
    0x909C: (0xE28DD00C, "publication_init_hook"),
    0x9260: (0xE92D4DF0, "publication_read_hook"),
    0x10BA8: (0xE92D4010, "publication_destroy_hook"),
}


def assemble(base, targets, clang="clang", source=None):
    with tempfile.TemporaryDirectory(prefix="mu1427-publication-") as work:
        obj = Path(work) / "publication.o"
        subprocess.run([clang, "--target=armv7-none-eabi", "-c",
                        str(source or HERE / "publication-hooks.S"), "-o", str(obj)], check=True)
        elf = ELFFile(io.BytesIO(obj.read_bytes()))
        code = bytearray(elf.get_section_by_name(".text").data())
        symbols = elf.get_section_by_name(".symtab")
        local = {s.name: base + s["st_value"] for s in symbols.iter_symbols()
                 if s["st_shndx"] == elf.get_section_index(".text")}
        rel = elf.get_section_by_name(".rel.text")
        for r in rel.iter_relocations() if rel else ():
            name = symbols.get_symbol(r["r_info_sym"]).name
            word = struct.unpack_from("<I", code, r["r_offset"])[0]
            if r["r_info_type"] not in (28, 29) or word & 0xFFFFFF != 0xFFFFFE:
                raise ValueError("unexpected publication relocation")
            target = {**targets, **local}[name]
            struct.pack_into("<I", code, r["r_offset"], b2.branch(
                base + r["r_offset"], target, bool(word & 0x1000000), word >> 28))
        return bytes(code), local


def build(stock, clang="clang"):
    baseline, old = b2.build(stock, clang)
    if b2.sha(baseline) != "0763b7aa448837651ca59ce8d3e219c0b157df05204c9a2037f895001b1655b6":
        raise ValueError("B2 baseline changed")
    old_symbols = {k: int(v, 16) for k, v in old["symbols"].items()}
    targets = {**NATIVE, "b2_ident_hook": old_symbols["ident_hook"],
               "b2_receive_resume": old_symbols["receive_guidance"] + 4}
    base = (len(baseline) + 15) & ~15
    code, symbols = assemble(base, targets, clang)
    data = bytearray(baseline)
    hooks = dict(HOOKS)
    hooks[0xE138] = (struct.unpack_from("<I", baseline, 0xE138)[0], "publication_ident_hook")
    # Inside B2's already-validated guidance path. No new interpretation of
    # packet pointers or changes to unknown-ID fallback/recycling.
    gate = old_symbols["receive_guidance"]
    hooks[gate] = (0xE2828C52, "publication_receive_hook")
    for at, (expected, name) in hooks.items():
        if struct.unpack_from("<I", data, at)[0] != expected:
            raise ValueError(f"publication hook fingerprint mismatch at {at:#x}")
        struct.pack_into("<I", data, at, b2.branch(at, symbols[name]))
    # Same-width log revision markers, leaving protocol bytes intact.
    for name, before, after in (("start_log", b"CPMAP_RGI_START B2", b"CPMAP_RGI_START B3"),
                                ("receive_log", b"CPMAP_RGI_RX B2", b"CPMAP_RGI_RX B3")):
        at = old_symbols[name]
        if data[at:at + len(before)] != before:
            raise ValueError("unexpected B2 log string")
        data[at:at + len(before)] = after
    data.extend(bytes(base - len(data)))
    data.extend(code)
    elf = ELFFile(io.BytesIO(baseline))
    header = elf["e_phoff"] + 3 * elf["e_phentsize"]
    size = len(data) - b2.INJECT
    struct.pack_into("<II", data, header + 16, size, size)
    manifest = {
        "build": "MU1427-iAP2-RGI-B3", "stock_sha256": b2.STOCK_SHA,
        "b2_sha256": b2.sha(baseline), "patched_sha256": b2.sha(data),
        "patched_size": len(data), "publication_base": hex(base),
        "publication_source_sha256": b2.sha((HERE / "publication-hooks.S").read_bytes()),
        "b2_source_sha256": old["source_sha256"],
        "symbols": {**old["symbols"], **{k: hex(v) for k, v in symbols.items() if not k.startswith("$")}},
        "publication_hooks": {hex(k): name for k, (_, name) in hooks.items()},
        "virtual_file": "/dev/ipod0/rgi-events", "snapshot_bytes": POOL_SIZE,
        "slots": 16, "maximum_payload_bytes": 2048,
    }
    return bytes(data), manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stock", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    if args.stock.resolve() == args.output.resolve(): p.error("output must differ from input")
    data, manifest = build(args.stock.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    args.output.with_suffix(args.output.suffix + ".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{manifest['build']} {len(data)} bytes sha256={manifest['patched_sha256']}")


if __name__ == "__main__":
    main()
