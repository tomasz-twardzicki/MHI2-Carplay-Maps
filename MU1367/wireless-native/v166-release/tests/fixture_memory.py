"""Size the SDK virtual-board RAM declaration; never changes a unit payload."""
import hashlib,struct

def configure_startup_ram(path):
    data=path.read_bytes()
    # SDK init_raminfo: add_ram(0x40000000, 0x10000000). The QEMU machine
    # already provides 1 GiB, but this startup object exposed only 256 MiB.
    # Repeated copy/rollback plus the RAM filesystem exhausted that fixture.
    before=struct.pack('<III',0xe3a01201,0xe3a00101,0xeafffffe)
    after=struct.pack('<III',0xe3a01202,0xe3a00101,0xeafffffe)
    assert data.startswith(b'\x7fELF') and data.count(before)==1
    changed=data.replace(before,after)
    path.write_bytes(changed)
    return dict(sdk_virtual_board_only=True,startup_ram_mib=512,
                original_startup_sha256=hashlib.sha256(data).hexdigest(),
                fixture_startup_sha256=hashlib.sha256(changed).hexdigest())
