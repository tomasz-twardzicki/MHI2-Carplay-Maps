"""Recognize dormant upstream menu leftovers without bypassing snapshot recovery.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'MU1367/port'))
from firmware import sha

# Official MU1367 / 791 artifacts. No jar bytes are embedded here.
LEGACY_MENUS = {
    'toolbox-plaintext-v2.0.0': 'f4fbb455aee272f3fa15b05c70345e59fd1e84b725ed55a99ce091b62261ed4a',
    'toolbox-plaintext-v2.0.1': 'fb0840e1d7f753ba8d3f5b37b79090b1129262e8afc767c5ea15e01a0393e91d',
}
CHANGED_CUSTOM = {
    'Custom/carplay_mu1367_settings/control.sh',
    'Custom/carplay_mu1367_settings/VERSION',
    'Custom/carplay_mu1367_settings/manifest.json',
    'Custom/carplay_mu1367_lanes/control.sh',
    'Custom/carplay_mu1367_lanes/VERSION',
    'Custom/carplay_mu1367_lanes/manifest.json',
}


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Published controller seam changed: ' + old)
    return text.replace(old, new)


def apply(stage):
    settings = stage / 'Custom/carplay_mu1367_settings'
    lanes = stage / 'Custom/carplay_mu1367_lanes'
    file = settings / 'control.sh'
    text = file.read_text()
    old_build = (settings / 'VERSION').read_text().strip()
    # The original controller subsequently rejects all competing boot tokens,
    # validates and hashes the entire snapshot, then commits boot last. Reuse
    # those transactions for the recognized dormant file rather than deleting it.
    alternatives = ' || '.join('check "$2" ' + digest for digest in LEGACY_MENUS.values())
    text = replace_once(text, ' menu) absent "$2" ;;', ' menu) absent "$2" || ' + alternatives + ' ;;')
    text = replace_once(text, 'else before "$K" "$T" || fail "UNEXPECTED_BASE_$K";fi', '''else
            if ! before "$K" "$T";then
                echo "MU1367_SETTINGS_UNEXPECTED_TARGET=$T"
                if regular "$T";then echo "MU1367_SETTINGS_ACTUAL_SHA256=$(digest "$T")";fi
                fail "UNEXPECTED_BASE_$K"
            fi
        fi''')
    build = 'MU1367-P4521-settings-' + sha(text.encode())[:12]
    text = replace_once(text, 'BUILD=' + old_build, 'BUILD=' + build)
    file.write_text(text)
    (settings / 'VERSION').write_text(build + '\n')
    info = json.loads((settings / 'manifest.json').read_text())
    info.update(build_id=build, previous_build_id=old_build,
                dormant_upstream_menu_sha256=LEGACY_MENUS, unknown_menu_refused=True,
                runtime_payloads_unchanged=True, controller_sha256=sha(text.encode()))
    (settings / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    # Re-render the exact parent expectations for step 4. Relaxing its old hash
    # check would hide an incompatible settings controller and break recovery.
    spec = importlib.util.spec_from_file_location('p4521_lane_package', HERE.parent / 'MU1367/lanes/package.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lane_build, controller, before = module.render(lanes, stage)
    (lanes / 'control.sh').write_text(controller)
    (lanes / 'VERSION').write_text(lane_build + '\n')
    info = json.loads((lanes / 'manifest.json').read_text())
    info.update(previous_build_id=info['build_id'], build_id=lane_build, before=before,
                p4521_settings_build=build, controller_sha256=sha(controller.encode()),
                runtime_payloads_unchanged=True)
    (lanes / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    return {'known_dormant_menu_sha256': LEGACY_MENUS, 'settings_build': build,
            'lanes_build': lane_build, 'changed_baseline_custom_files': sorted(CHANGED_CUSTOM)}
