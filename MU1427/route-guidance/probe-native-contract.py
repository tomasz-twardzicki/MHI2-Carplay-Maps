#!/usr/bin/env python3
"""Read selected native navigation interfaces from the exact factory JXE.

SPDX-License-Identifier: GPL-3.0-or-later
Writes metadata only. Firmware/classes remain outside version control.
Requires the pinned jxe2jar ROM parser and the same liblzo2 used by the
existing MU1427 extraction tools; no Java runtime is required for this probe.
"""
import argparse
import contextlib
import ctypes
import ctypes.util
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys

JXE_SHA = 'f46290b4a33b98d957170f6207073ad329316902a87cd4c27da4168548ad911a'
PARSER_COMMIT = '9eeb45bbf14bf8afe3452c7be96a4d1f0206a286'
ROOT = 'de/vw/mib/bap/mqbab2/'
CLASSES = [
    'org/dsi/ifc/navigation/BapManeuverDescriptor',
    'org/dsi/ifc/komonavinfo/DSIKOMONavInfo',
    ROOT + 'generated/navsd/serializer/ManeuverDescriptor_Status',
    ROOT + 'generated/navsd/serializer/ManeuverDescriptor_Status$Maneuver_1',
    ROOT + 'generated/navsd/serializer/DistanceToNextManeuver_Status$DistanceToNextManeuver',
    ROOT + 'generated/navsd/serializer/DistanceToNextManeuver_Status$ValidityInformation',
    ROOT + 'generated/navsd/serializer/RG_Status_Status',
    ROOT + 'generated/navsd/serializer/ManeuverState_Status',
    ROOT + 'common/api/navigation/NavigationService',
    ROOT + 'common/api/APIFactory',
    ROOT + 'common/api/APIFactoryInterface',
    ROOT + 'common/api/smartphoneintegration/SmartphoneIntegrationService',
    ROOT + 'common/api/smartphoneintegration/SmartphoneIntegrationASLDataAdapter',
    'generated/de/vw/mib/asl/internal/smartphoneintegration/ASLSmartPhoneIntegrationPropertyManager',
    'generated/de/vw/mib/asl/internal/navigation/bap/ASLNavigationBapPropertyManager',
    ROOT + 'common/api/navigation/NavigationASLDataAdapter',
    ROOT + 'common/api/navigation/datatypes/iterator/elements/NavigationManeuverDescriptorElement',
    ROOT + 'common/api/navigation/datatypes/NavigationDistanceToNextManeuver',
    ROOT + 'navsd/functions/ManeuverDescriptor',
    ROOT + 'navsd/functions/DistanceToNextManeuver',
    ROOT + 'navsd/functions/RGStatus',
    'de/vw/mib/bap/mqbpq/navsd/functions/ManeuverDescriptor',
]

GETTERS = {'getRouteGuidanceState', 'getNavigationStatus', 'getKombiMapStatus',
           'getManeuverDescriptor', 'getDistanceToNextManeuver', 'getCurrentPositionInfo',
           'getTurnToInfo', 'getDistanceToDestination', 'getTimeToDestination',
           'addNavigationServiceListener', 'removeNavigationServiceListener'}


def relevant_field(cls, name):
    if cls.endswith('/ASLSmartPhoneIntegrationPropertyManager'):
        return name.startswith('CURRENT_ACTIVE_CONNECTION_METHOD')
    if cls.endswith('/ASLNavigationBapPropertyManager'):
        return name.startswith(('ROUTE_GUIDANCE_STATE', 'NAVIGATION_STATUS'))
    if cls.endswith('/APIFactory'): return name == 'navigationService'
    if 'smartphoneintegration/' in cls or cls.endswith('/APIFactoryInterface'): return False
    if cls.endswith('/NavigationASLDataAdapter') or cls.endswith('/NavigationService'): return False
    if cls.endswith('/DSIKOMONavInfo'):
        return name.startswith(('DISTANCEUNIT_', 'RGMODE_', 'TIMEFORMAT_'))
    if '/functions/' in cls:
        return name in ('MANEUVER_DIRECTION_LEFT', 'MANEUVER_DIRECTION_RIGHT')
    return True


def relevant_method(cls, name):
    if cls.endswith(('/APIFactory', '/APIFactoryInterface')):
        return name in ('getNavigationService', 'getSmartphoneIntegrationService')
    if 'smartphoneintegration/' in cls: return name == 'getSmarphoneIntegrationActiveConnectionType'
    if cls.endswith(('/NavigationASLDataAdapter', '/NavigationService')): return name in GETTERS
    if cls.endswith('/DSIKOMONavInfo'):
        return name in ('setDistanceToNextManeuver', 'setCurrentStreet', 'setTurnToStreet',
                        'setDistanceToDestination', 'setETA', 'setRTT', 'setRgSelect')
    if '/functions/' in cls:
        return name in ('<init>', 'getFunctionId', 'mapToBAPMainElement', 'validateManeuverData',
                        'fillManeuverDescriptor', 'sendManeuverDescriptor', 'process',
                        'updateNavigationData', 'showDistanceToNextManeuver',
                        'setRouteGuidanceStatus',
                        'setDistanceToNextManeuverStatusData', 'computeDistanceAndDistanceUnit')
    return name in ('<init>', 'serialize', 'bitSize', 'functionId', 'getFunctionId') or name.startswith('get')


def extract_jxe(firmware):
    image = (firmware / 'MMX2/mifs-stage2/50/default/mifs-stage2.img').read_bytes()
    if image[:4] != b'LZOZ': raise ValueError('factory stage2 wrapper mismatch')
    chunk = struct.unpack_from('<I', image, 4)[0]
    if not 1 <= chunk <= 4 * 1024 * 1024: raise ValueError('invalid stage2 chunk bound')
    library = ctypes.util.find_library('lzo2')
    if not library: raise ValueError('liblzo2 required for factory extraction')
    lzo = ctypes.CDLL(library)
    sizes = []
    for pos in range(8, min(0x800, len(image)), 4):
        size = struct.unpack_from('<I', image, pos)[0]
        if not size: break
        sizes.append(size)
    else: raise ValueError('unterminated stage2 block table')
    pos = 0x800
    data = bytearray()
    for size in sizes:
        if pos + size > len(image) or len(data) + chunk > 256 * 1024 * 1024:
            raise ValueError('stage2 bounds exceeded')
        source = image[pos:pos + size]
        output = ctypes.create_string_buffer(chunk)
        length = ctypes.c_ulong(chunk)
        rc = lzo.lzo1z_decompress_safe(source, ctypes.c_ulong(size), output, ctypes.byref(length), None)
        if rc or length.value > chunk: raise ValueError('stage2 decompression failed')
        data.extend(output.raw[:length.value])
        pos += size
        while pos < len(image) and image[pos] == 255: pos += 1
    if data[:7] != b'imagefs': raise ValueError('factory stage2 imagefs missing')
    size, end, pos = struct.unpack_from('<III', data, 8)
    if size != len(data) or not 64 < pos < end < size:
        raise ValueError('invalid stage2 imagefs bounds')
    while pos < end:
        length = struct.unpack_from('<H', data, pos)[0]
        if not length: break
        if length < 24 or pos + length > end: raise ValueError('invalid imagefs entry')
        mode = struct.unpack_from('<I', data, pos + 8)[0]
        if mode & 0o170000 == 0o100000:
            if length < 33: raise ValueError('short imagefs file entry')
            offset, count = struct.unpack_from('<II', data, pos + 24)
            name = data[pos + 32:pos + length].split(b'\0')[0]
            if name == b'ifs/lsd.jxe':
                result = bytes(data[offset:offset + count])
                if len(result) != 52751492 or hashlib.sha256(result).hexdigest() != JXE_SHA:
                    raise ValueError('exact MU1427 factory JXE required')
                return result
        pos += length
    raise ValueError('factory JXE missing')


def probe(firmware, parser, export_jxe=None):
    revision = subprocess.run(['git', '-C', str(parser), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, check=True).stdout.strip()
    if revision != PARSER_COMMIT: raise ValueError('pinned ROM parser required')
    if subprocess.run(['git', '-C', str(parser), 'status', '--porcelain', '--', 'src'],
                      capture_output=True, text=True, check=True).stdout:
        raise ValueError('ROM parser sources must be unchanged')
    data = extract_jxe(firmware)
    if export_jxe is not None:
        with export_jxe.open('xb') as output: output.write(data)
    sys.path.insert(0, str(parser / 'src'))
    from jxe import JXE, ReaderStream
    with contextlib.redirect_stdout(io.StringIO()):
        rom = JXE.read(ReaderStream(io.BytesIO(data)))
    selected = {}
    for cls in rom.image.classes:
        if cls.class_name not in CLASSES: continue
        fields = {field.name: {'descriptor': field.signature,
                              'access': field.access_flag & 0xffff,
                              **({'value': field.const_value} if field.signature == 'I'
                                 and field.const_value is not None else {})}
                  for field in cls.fields if relevant_field(cls.class_name, field.name)}
        methods = {method.name + method.signature:
                   {'access': method.modifier & 0xffff,
                    'rom_code_sha256': hashlib.sha256(bytes(method.bytecode)).hexdigest()}
                   for method in cls.methods if relevant_method(cls.class_name, method.name)}
        selected[cls.class_name] = {'fields': fields, 'methods': methods,
                                    'access': cls.access_flags & 0xffff,
                                    'superclass': cls.superclass_name}
    if set(selected) != set(CLASSES): raise ValueError('required factory interfaces missing')
    return {'firmware': 'MHI2_ER_VWG11_K3342_MU1427', 'jxe_bytes': len(data),
            'jxe_sha256': JXE_SHA, 'rom_parser_commit': revision,
            'scope': 'selected_fields_and_methods', 'classes': selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware', type=Path)
    parser.add_argument('--jxe2jar', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', type=Path)
    parser.add_argument('--export-jxe', type=Path, help='also export the verified JXE to a new private file')
    args = parser.parse_args()
    result = probe(args.firmware, args.jxe2jar, args.export_jxe)
    if args.check and result != json.loads(args.check.read_text()):
        parser.error('native contract differs from verified MU1427 metadata')
    if args.output: args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'verified_classes': len(result['classes']), 'jxe_sha256': result['jxe_sha256'],
                      'contract_matches': bool(args.check)}))


if __name__ == '__main__': main()
