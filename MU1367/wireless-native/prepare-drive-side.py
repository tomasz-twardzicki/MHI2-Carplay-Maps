#!/usr/bin/env python3
"""Prepare a receiver driving-side plist offline without touching a head unit.

Preserve existing plist properties when --input is supplied. Use --new only
for a confirmed absent config. Output is binary plist, supported by the pinned
receiver's actual CF parser. No installation or service restart is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib


def prepare(original,driver_side):
    if driver_side not in (1,2):
        raise ValueError('OEM driver side must be 1 (LHD) or 2 (RHD)')
    config={} if original is None else plistlib.loads(original)
    if not isinstance(config,dict):
        raise ValueError('Receiver config must have a dictionary root')
    expected=dict(config)
    expected['rightHandDrive']=driver_side==2
    result=plistlib.dumps(expected,fmt=plistlib.FMT_BINARY,sort_keys=True)
    restored=plistlib.loads(result)
    assert restored==expected and type(restored['rightHandDrive']) is bool
    assert all(restored[k]==v for k,v in config.items() if k!='rightHandDrive')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--input',type=Path,help='Existing per-unit airplay.conf plist; preserve its other properties')
    source.add_argument('--new',action='store_true',help='Prepare a new config for a confirmed absent file')
    p.add_argument('--driver-side',type=int,choices=(1,2),required=True,help='OEM getDriverSide value: 1=LHD, 2=RHD')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    original=None if a.input is None else a.input.read_bytes()
    result=prepare(original,a.driver_side)
    # Never replace an input, an earlier candidate or a symbolic link.
    with a.output.open('xb') as f:f.write(result)
    print(json.dumps(dict(output=str(a.output),sha256=hashlib.sha256(result).hexdigest(),rightHandDrive=a.driver_side==2,other_properties_preserved=True,installed=False)))


if __name__=='__main__':main()
