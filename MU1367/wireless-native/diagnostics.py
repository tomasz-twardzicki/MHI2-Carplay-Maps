"""Include the wireless diagnostic collector and its Green Menu action."""
import hashlib
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent


def add(sd):
    sd=Path(sd)
    wrapper='Toolbox/scripts/cpmap_wireless_collect.sh'
    collector='Toolbox/scripts/cpmap_wireless_collect_data.sh'
    menu='Toolbox/GEM/carplay-maps-vc-wireless.esd'
    label='Collect wireless diagnostics to SD (no reboot)'
    for source,target in [('gem-collect-wireless.sh',wrapper),('collect-wireless.sh',collector),('collect-wireless.sh','collect-wireless.sh')]:
        shutil.copy2(HERE/source,sd/target)
        (sd/target).chmod(0o755)
    probe_wrapper='Toolbox/scripts/cpmap_wireless_alt_probe.sh'
    probe_data='Toolbox/scripts/cpmap_wireless_alt_probe_data.sh'
    (sd/probe_wrapper).write_text((HERE/'gem-collect-wireless.sh').read_text().replace('cpmap_wireless_collect_data.sh','cpmap_wireless_alt_probe_data.sh').replace('WIRELESS_DIAG','WIRELESS_ALT_PROBE'))
    shutil.copy2(HERE/'enable-alt-probe.sh',sd/probe_data)
    for name in (probe_wrapper,probe_data):(sd/name).chmod(0o755)
    text=(sd/menu).read_text()
    assert text.startswith('screen Wireless-CarPlay-Test carplay-maps-vc\n')
    command='/eso/hmi/engdefs/scripts/mqb/cpmap_wireless_collect.sh'
    if command not in text:
        text+='\nscript\n    value sys 1 0x0100 "'+command+'"\n    label "'+label+'"\n'
    assert text.count(command)==text.count(label)==1
    probe_command='/eso/hmi/engdefs/scripts/mqb/cpmap_wireless_alt_probe.sh'
    probe_label='Enable AID display probe (until reboot)'
    if probe_command not in text:
        text+='\nscript\n    value sys 1 0x0100 "'+probe_command+'"\n    label "'+probe_label+'"\n'
    assert text.count(probe_command)==text.count(probe_label)==1
    (sd/menu).write_text(text)
    for name in (wrapper,collector):
        assert (sd/name).is_file()
    return dict(menu=menu,label=label,wrapper=wrapper,collector=collector,alternate_display_probe=dict(label=probe_label,wrapper=probe_wrapper,script=probe_data,scope='RAM flag only; explicit off flags respected; full reboot clears it.'),sha256={n:hashlib.sha256((sd/n).read_bytes()).hexdigest() for n in (menu,wrapper,collector,'collect-wireless.sh',probe_wrapper,probe_data)},output='SD:/Log/wireless-diag-<number>',requires_runtime_reinstall=False)
