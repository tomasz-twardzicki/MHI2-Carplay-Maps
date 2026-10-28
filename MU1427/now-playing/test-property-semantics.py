#!/usr/bin/env python3
"""Verify the stock property return semantics behind N1's diagnostic counters.
Host-only; does not rebuild or modify the installed N1 candidate.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path, required=True)
    parser.add_argument('--stock-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('factory_builder', HERE.parent / 'route-guidance/build-live-bridge.py')
    factory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(factory)
    if factory.stock_content(args.stock_jar) != factory.STOCK_CONTENT_SHA:
        parser.error('exact converted MU1427 factory classes required')
    source = HERE / 'research/PropertySemantics.java'
    with tempfile.TemporaryDirectory(prefix='mu1427-property-semantics-') as work:
        subprocess.run([str(args.java_home / 'bin/javac'), '-cp', str(args.stock_jar.resolve()),
                        '-d', work, str(source)], check=True, capture_output=True, timeout=60)
        output = subprocess.check_output([str(args.java_home / 'bin/java'), '-Xverify:all',
            '-cp', work + ':' + str(args.stock_jar.resolve()),
            'com.cpmap.audio.research.PropertySemantics'], timeout=60)
        checks = json.loads(output)
    names = ('common/api/adapter/AbstractBAPDataPool',
             'common/api/adapter/AbstractBAPDataPool$SendbufferFunctionRegistryListenerAdapter',
             'common/api/adapter/BAPDataPoolValueAdapter',
             'common/marshalling/FunctionRegistryListenerAdapter',
             'audiosd/functions/CurrentStationInfo')
    with zipfile.ZipFile(args.stock_jar) as archive:
        classes = {'de/vw/mib/bap/mqbab2/' + n + '.class':
                   sha(archive.read('de/vw/mib/bap/mqbab2/' + n + '.class')) for n in names}
    result = {'passed': True, 'scope': 'exact-factory host semantics; no transport or AID runtime',
              'stock_content_sha256': factory.STOCK_CONTENT_SHA,
              'source_sha256': sha(source.read_bytes()),
              'runner_sha256': sha(Path(__file__).read_bytes()),
              'classes_sha256': classes, 'checks': checks}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(checks))


if __name__ == '__main__':
    main()
