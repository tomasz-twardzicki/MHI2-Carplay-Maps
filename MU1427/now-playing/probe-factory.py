#!/usr/bin/env python3
"""Extract a metadata-only audio contract from the exact MU1427 factory JXE.

SPDX-License-Identifier: GPL-3.0-or-later
Firmware and converted classes must remain outside version control.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'navigation_contract', HERE.parent / 'route-guidance/probe-native-contract.py')
factory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(factory)

# Whole method bytecodes are fingerprinted, never exported.
SELECTION = {
    'org/dsi/ifc/carplay/DSICarplay': None,
    'org/dsi/ifc/carplay/DSICarplayListener': None,
    'org/dsi/ifc/carplay/TrackData': None,
    'org/dsi/ifc/carplay/PlaybackInfo': None,
    'org/dsi/ifc/global/ResourceLocator': None,
    'org/dsi/ifc/base/DSIListener': None,
    'org/dsi/ifc/kombipictureserver/DSIKombiPictureServer': {'responseCoverArt'},
    'de/vw/mib/asl/internal/carplay/target/HsmTarget': {
        '<init>', 'initializeDSI', 'deInitializeDSI', 'getDSICarPlay'},
    'de/vw/mib/bap/mqbab2/audiosd/functions/CurrentStationInfo': {
        'getFunctionId', 'setStationInfoForMirrorLink', 'setStationInfoStatus',
        'setArtistAndAlbum', 'computeCurrentStationInfoStatus', 'process'},
    'de/vw/mib/bap/mqbab2/audiosd/functions/CurrentStationHandle': {
        'getFunctionId', 'computeCurrentStationHandleStatus'},
    'de/vw/mib/bap/mqbab2/audiosd/functions/ActiveSource': {
        'getFunctionId', 'computeActiveSourceStatus'},
    'de/vw/mib/bap/mqbab2/generated/audiosd/serializer/CurrentStationInfo_Status': None,
    'de/vw/mib/asl/internal/kombipictureserver/usecaces/CoverArt': {
        '_isActiveSourceSupportsCoverArt', '_transmitCoverArt',
        'indicationCoverArt', '_updateCoverArt', 'updateBapAudioSd'},
}


def probe(firmware, parser):
    revision = subprocess.check_output(
        ['git', '-C', str(parser), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != factory.PARSER_COMMIT:
        raise ValueError('pinned jxe2jar parser required')
    if subprocess.check_output(
            ['git', '-C', str(parser), 'status', '--porcelain', '--', 'src'], text=True):
        raise ValueError('ROM parser sources must be unchanged')
    data = factory.extract_jxe(firmware)
    sys.path.insert(0, str(parser / 'src'))
    from jxe import JXE, ReaderStream
    with contextlib.redirect_stdout(io.StringIO()):
        rom = JXE.read(ReaderStream(io.BytesIO(data)))
    classes = {}
    for cls in rom.image.classes:
        if cls.class_name not in SELECTION:
            continue
        names = SELECTION[cls.class_name]
        classes[cls.class_name] = {
            'superclass': cls.superclass_name,
            'fields': {f.name: {
                'descriptor': f.signature,
                **({'value': f.const_value} if f.signature == 'I'
                   and f.const_value is not None else {})}
                for f in cls.fields if f.signature == 'I' or names is None},
            'methods': {m.name + m.signature: {
                'access': m.modifier & 0xffff,
                'rom_code_sha256': hashlib.sha256(bytes(m.bytecode)).hexdigest()}
                for m in cls.methods if names is None or m.name in names},
            # Explicitly records whether the factory HMI has audio handlers.
            'audio_callback_methods': sorted(m.name + m.signature for m in cls.methods
                if any(word in m.name.lower() for word in
                       ('nowplaying', 'playbackstate', 'coverarturl', 'playposition'))),
        }
    if set(classes) != set(SELECTION):
        raise ValueError('required factory classes missing')
    return {'firmware': 'MHI2_ER_VWG11_K3342_MU1427', 'cluster_target': '791 AID 12.3',
            'jxe_bytes': len(data), 'jxe_sha256': factory.JXE_SHA,
            'rom_parser_commit': revision, 'scope': 'selected_fields_and_methods',
            'hardware_validated': False, 'classes': classes}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware', type=Path)
    p.add_argument('--jxe2jar', type=Path, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--check', type=Path)
    a = p.parse_args()
    result = probe(a.firmware, a.jxe2jar)
    if a.check and result != json.loads(a.check.read_text()):
        p.error('factory audio contract differs')
    if a.output:
        a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'classes': len(result['classes']), 'matches': bool(a.check),
                      'jxe_sha256': result['jxe_sha256']}))


if __name__ == '__main__':
    main()
