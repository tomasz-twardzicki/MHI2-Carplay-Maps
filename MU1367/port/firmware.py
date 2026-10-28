"""Read-only MU1367 firmware extraction. Firmware bytes stay outside Git.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import ctypes
import ctypes.util
import hashlib
import re
import struct
import zlib

JXE_SHA = '09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a'
JXE_SIZE = 55840541


def sha(data):
    return hashlib.sha256(data).hexdigest()


def image_files(data):
    for match in re.finditer(b'imagefs', data):
        base = match.start()
        if base + 20 > len(data):
            continue
        size, end, pos = struct.unpack_from('<III', data, base + 8)
        if base + size == len(data) and 64 < pos < end < size:
            break
    else:
        raise ValueError('invalid imagefs bounds')
    result = {}
    while pos < end:
        n = struct.unpack_from('<H', data, base + pos)[0]
        if not n:
            break
        if n < 24 or pos + n > end:
            raise ValueError('invalid imagefs directory')
        mode = struct.unpack_from('<I', data, base + pos + 8)[0]
        if mode & 0o170000 == 0o100000:
            off, count = struct.unpack_from('<II', data, base + pos + 24)
            name = data[base + pos + 32:base + pos + n].split(b'\0')[0].decode()
            if off + count > size or name in result:
                raise ValueError('invalid imagefs file')
            result[name] = data[base + off:base + off + count]
        pos += n
    return result


def stage2(path):
    data = path.read_bytes()
    if data[:4] != b'LZOZ':
        raise ValueError('expected LZOZ wrapper')
    chunk = struct.unpack_from('<I', data, 4)[0]
    if not 1 <= chunk <= 4 * 1024 * 1024:
        raise ValueError('invalid LZO chunk')
    library = ctypes.util.find_library('lzo2')
    if not library:
        raise ValueError('liblzo2 required')
    lzo = ctypes.CDLL(library)
    sizes = []
    for pos in range(8, 0x800, 4):
        n = struct.unpack_from('<I', data, pos)[0]
        if not n:
            break
        sizes.append(n)
    else:
        raise ValueError('unterminated LZO table')
    output = bytearray()
    pos = 0x800
    for n in sizes:
        if pos + n > len(data) or len(output) + chunk > 256 * 1024 * 1024:
            raise ValueError('LZO bounds exceeded')
        buf = ctypes.create_string_buffer(chunk)
        count = ctypes.c_ulong(chunk)
        rc = lzo.lzo1z_decompress_safe(data[pos:pos+n], ctypes.c_ulong(n), buf, ctypes.byref(count), None)
        if rc or count.value > chunk:
            raise ValueError('LZO decompression failed')
        output.extend(buf.raw[:count.value])
        pos += n
        while pos < len(data) and data[pos] == 255:
            pos += 1
    return bytes(output)


def stage1(path):
    data = path.read_bytes()
    if data[:8] != bytes.fromhex('41ff44ff4fff44ff'):
        raise ValueError('unexpected stage1 wrapper')
    decoder = zlib.decompressobj()
    output = decoder.decompress(data[0x800:], 64 * 1024 * 1024 + 1)
    if not decoder.eof or len(output) > 64 * 1024 * 1024:
        raise ValueError('invalid stage1 stream')
    return output


def crc_be(data):
    value = 0
    for byte in data:
        value ^= byte << 24
        for _ in range(8):
            value = ((value << 1) ^ (0x04c11db7 if value & 0x80000000 else 0)) & 0xffffffff
    return value


class QNX6:
    """Bounded reader for standard little-endian Power-Safe images.

    On-disk field layout: Linux v6.12 include/linux/qnx6_fs.h and fs/qnx6.
    No mounting, writes, shell extraction or executable firmware code.
    """
    def __init__(self, path):
        self.file = path.open('rb')
        self.length = path.stat().st_size
        first = self.at(8192, 512)
        self.check_super(first)
        self.bs = struct.unpack_from('<I', first, 48)[0]
        self.blocks = struct.unpack_from('<I', first, 60)[0]
        if self.bs not in (512, 1024, 2048, 4096):
            raise ValueError('unsupported QNX6 block size')
        self.offset = 8192 + 4096
        second = self.at(self.offset + self.blocks * self.bs, 512)
        self.check_super(second)
        if first[48:64] != second[48:64]:
            raise ValueError('inconsistent QNX6 superblocks')
        sb = max((first, second), key=lambda b: struct.unpack_from('<Q', b, 8)[0])
        self.inodes = self.root(sb[72:152])
        self.longnames = self.root(sb[232:312])

    @staticmethod
    def check_super(data):
        if data[:4] != bytes.fromhex('22111968') or crc_be(data[8:512]) != struct.unpack_from('<I', data, 4)[0]:
            raise ValueError('QNX6 superblock signature/checksum mismatch')

    def at(self, offset, count):
        if offset < 0 or count < 0 or offset + count > self.length:
            raise ValueError('QNX6 read outside image')
        self.file.seek(offset)
        data = self.file.read(count)
        if len(data) != count:
            raise ValueError('QNX6 short read')
        return data

    @staticmethod
    def root(data):
        return struct.unpack_from('<Q', data)[0], struct.unpack_from('<16I', data, 8), data[72]

    def block(self, number):
        if not 0 <= number < self.blocks:
            raise ValueError('invalid QNX6 block pointer')
        return self.at(self.offset + number * self.bs, self.bs)

    def read(self, node, start=0, count=None):
        size, ptrs, depth = node
        count = size - start if count is None else count
        if depth > 5 or not 0 <= start <= start + count <= size or count > 128 * 1024 * 1024:
            raise ValueError('invalid/oversized QNX6 file read')
        output = bytearray()
        fanout = self.bs // 4
        for index in range(start // self.bs, (start + count + self.bs - 1) // self.bs):
            slot = index // fanout**depth
            if slot >= 16:
                raise ValueError('QNX6 file exceeds pointer tree')
            pointer = ptrs[slot]
            for level in range(depth - 1, -1, -1):
                pointer = struct.unpack_from('<I', self.block(pointer), ((index // fanout**level) % fanout) * 4)[0]
            output.extend(self.block(pointer))
        off = start % self.bs
        return bytes(output[off:off+count])

    def inode(self, number):
        if number < 1:
            raise ValueError('invalid QNX6 inode')
        raw = self.read(self.inodes, (number - 1) * 128, 128)
        return (struct.unpack_from('<Q', raw)[0], struct.unpack_from('<16I', raw, 36), raw[100]), struct.unpack_from('<H', raw, 32)[0]

    def entries(self, number):
        node, mode = self.inode(number)
        if mode & 0o170000 != 0o040000:
            raise ValueError('QNX6 path component is not a directory')
        data = self.read(node)
        entries = {}
        for pos in range(0, len(data), 32):
            ino = struct.unpack_from('<I', data, pos)[0]
            n = data[pos + 4]
            if not ino or not n:
                continue
            if n == 255:
                index = struct.unpack_from('<I', data, pos + 8)[0]
                raw = self.read(self.longnames, index * self.bs, 512)
                n = struct.unpack_from('<H', raw)[0]
                if not 1 <= n <= 510:
                    raise ValueError('invalid QNX6 long name')
                name = raw[2:2+n].decode()
            elif n <= 27:
                name = data[pos+5:pos+5+n].decode()
            else:
                raise ValueError('invalid QNX6 directory name')
            if name in entries or '/' in name:
                raise ValueError('invalid/duplicate QNX6 path')
            entries[name] = ino
        return entries

    def get(self, path):
        number = 1
        for part in path.split('/'):
            if part in ('', '.', '..'):
                raise ValueError('relative clean QNX6 path required')
            number = self.entries(number)[part]
        node, mode = self.inode(number)
        if mode & 0o170000 != 0o100000:
            raise ValueError('QNX6 target is not a regular file')
        return self.read(node)
