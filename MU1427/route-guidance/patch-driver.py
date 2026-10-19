#!/usr/bin/env python3
"""Build a fingerprinted MU1427 B2 driver. Never modifies the input.

Uses clang's ARM assembler (no QNX SDK or runtime dependency). pyelftools is
only a host build dependency. The added RX PT_LOAD replaces the GNU build-id
PT_NOTE; QNX's own note and all original load mappings/relocations stay intact.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
STOCK_SHA = "0ac13f43d3fb259eee328c272fa1211bb558b6e2cd97c6e38ef38e4e71469d51"
STOCK_SIZE = 739925
INJECT = 0xB5000  # page aligned, above the original RW/BSS end (0xaf0bc)
NATIVE = {
    "packet_addparam_blob": 0x1E2C4,
    "link_send_raw_message": 0x113A8,
    "driver_log": 0x4C4C,
    "driver_hexdump": 0x4D30,
    "stock_link_handle_reply": 0x11A2C,
    "ident_resume": 0xE13C,
    "ident_cleanup": 0xE11C,
}
HOOKS = {
    0xE138: (0xE1A00006, "ident_hook", False),
    0x63F0: (0xE1A00005, "start_hook", True),
    0x133A0: (0xEBFFF9A1, "receive_hook", True),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def branch(at, target, link=False, condition=14):
    delta = target - at - 8
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise ValueError("ARM branch out of range/alignment")
    return (condition << 28) | (0xB000000 if link else 0xA000000) | ((delta >> 2) & 0xFFFFFF)


def assemble(clang="clang"):
    with tempfile.TemporaryDirectory(prefix="mu1427-rgi-") as work:
        obj = Path(work) / "hooks.o"
        subprocess.run([clang, "--target=armv7-none-eabi", "-c", str(HERE / "driver-hooks.S"), "-o", str(obj)], check=True)
        elf = ELFFile(io.BytesIO(obj.read_bytes()))
        code = bytearray(elf.get_section_by_name(".text").data())
        symbols = elf.get_section_by_name(".symtab")
        local = {s.name: INJECT + s["st_value"] for s in symbols.iter_symbols() if s["st_shndx"] == elf.get_section_index(".text")}
        rel = elf.get_section_by_name(".rel.text")
        for reloc in rel.iter_relocations() if rel else []:
            at = reloc["r_offset"]
            name = symbols.get_symbol(reloc["r_info_sym"]).name
            target = {**NATIVE, **local}[name]
            word = struct.unpack_from("<I", code, at)[0]
            if reloc["r_info_type"] not in (28, 29):  # R_ARM_CALL / R_ARM_JUMP24
                raise ValueError(f"unexpected relocation for {name}: {reloc.entry}")
            # Clang emits a branch with addend -8 for these external labels.
            if word & 0xFFFFFF != 0xFFFFFE:
                raise ValueError(f"unexpected branch addend for {name}")
            struct.pack_into("<I", code, at, branch(INJECT + at, target, bool(word & 0x1000000), word >> 28))
        return bytes(code), local


def build(stock, clang="clang"):
    if len(stock) != STOCK_SIZE or sha(stock) != STOCK_SHA:
        raise ValueError(f"not the factory MU1427 iAP2 driver: size={len(stock)}, sha256={sha(stock)}")
    elf = ELFFile(io.BytesIO(stock))
    if elf.elfclass != 32 or not elf.little_endian or elf["e_machine"] != "EM_ARM":
        raise ValueError("expected ARM ELF32 little endian")
    code, symbols = assemble(clang)
    data = bytearray(stock)
    for at, (expected, name, link) in HOOKS.items():
        if struct.unpack_from("<I", data, at)[0] != expected:
            raise ValueError(f"hook fingerprint mismatch at {at:#x}")
        struct.pack_into("<I", data, at, branch(at, symbols[name], link))
    # Retain QNX's PT_NOTE. The first PT_NOTE describes only .note.gnu.build-id.
    notes = [(i, p) for i, p in enumerate(elf.iter_segments()) if p["p_type"] == "PT_NOTE"]
    index, note = notes[0]
    if (index, note["p_offset"], note["p_filesz"]) != (3, 0xAE0A0, 32):
        raise ValueError("unexpected GNU build-id program header")
    for p in elf.iter_segments():
        if p["p_type"] == "PT_LOAD" and p["p_vaddr"] + p["p_memsz"] > INJECT:
            raise ValueError("injection overlaps an original mapping")
    header = elf["e_phoff"] + index * elf["e_phentsize"]
    struct.pack_into("<8I", data, header, 1, INJECT, INJECT, INJECT, len(code), len(code), 5, 4096)
    data.extend(bytes(INJECT - len(data)))
    data.extend(code)
    manifest = {
        "build": "MU1427-iAP2-RGI-B2",
        "stock_sha256": STOCK_SHA,
        "patched_sha256": sha(data),
        "patched_size": len(data),
        "payload_sha256": sha(code),
        "source_sha256": sha((HERE / "driver-hooks.S").read_bytes()),
        "injection_vaddr": hex(INJECT),
        "symbols": {k: hex(v) for k, v in symbols.items() if not k.startswith("$")},
        "hooks": {hex(k): name for k, (_, name, _) in HOOKS.items()},
    }
    return bytes(data), manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--clang", default="clang")
    args = parser.parse_args()
    if args.stock.resolve() == args.output.resolve():
        parser.error("output must differ from input")
    try:
        data, manifest = build(args.stock.read_bytes(), args.clang)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(data)
        args.output.with_suffix(args.output.suffix + ".json").write_text(json.dumps(manifest, indent=2) + "\n")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"patch refused: {exc}\n")
    print(f"{manifest['build']} {len(data)} bytes sha256={sha(data)}")


if __name__ == "__main__":
    main()
