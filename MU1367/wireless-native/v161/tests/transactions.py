#!/usr/bin/env python3
"""Run candidate transactions and session predicates with firmware utilities.

The transaction fixture seeds installed-file bytes from published v1.5.4.
Only its fake JXE hash and the corresponding SD-controller hash are changed.
No firmware-only command is supplied by the SDK to make the controller pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
WIRELESS = HERE.parents[1]
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "MU1367/port"))
from firmware import QNX6, image_files, stage1, stage2
sha = lambda b: hashlib.sha256(b).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "firmware", "setup", "toolchain", "h264-fixture", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--commit-keys",default="")
    a = p.parse_args()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sd = a.build.resolve() / "sd-card"
    layer = sd / "Custom/carplay_mu1367_wireless_native"
    manifest = json.loads((a.build / "manifest.json").read_text())
    rows = manifest["rows"]
    by_target = {r["target"]:r for r in rows}
    keys=a.commit_keys.split(",") if a.commit_keys else [r["key"] for r in rows]
    assert keys and len(keys)==len(set(keys)) and set(keys)<={r["key"] for r in rows}
    first = image_files(stage1(a.firmware / "MMX2/mifs-stage1/50/default/mifs-stage1.img"))
    second = image_files(stage2(a.firmware / "MMX2/mifs-stage2/50/default/mifs-stage2.img"))
    files = dict(first); files.update(second)
    app = QNX6(a.firmware / "MMX2/app/50/default/app.img")
    for name in ("c4-smoke", "devc-serdebug", "libstartup.a", "startup-virt", "u-boot.bin", "procnto-smp", "pipe"):
        shutil.copy2(a.setup / name, out / name)
    # SDK boot helper only; the upstream ring itself is larger than 16 MiB.
    helper=out/'c4-smoke';data=helper.read_bytes()
    assert data.count(b'capacity=32768,nodinit')==1
    helper.write_bytes(data.replace(b'capacity=32768,nodinit',b'capacity=65536,nodinit'))
    for name in ("libc.so.3", "libsocket.so.3", "libm.so.2", "libcam.so.2", "mkqnx6fs", "mount", "devb-ram", "io-blk.so", "fs-qnx6.so", "cam-disk.so"):
        hits = [b for n,b in files.items() if Path(n).name == name]
        assert hits, name
        (out / name).write_bytes(hits[0])
    (out / "libblkcache.so.2").write_bytes(app.get("armle/usr/lib/libblkcache.so.2"))
    utilities = ("ksh", "cat", "cp", "mv", "rm", "mkdir", "chmod", "sync", "ls", "grep")
    for name in utilities:
        hits = [b for n,b in files.items() if Path(n).name == name]
        assert hits, name
        (out / ("factory-" + name)).write_bytes(hits[-1])
    (out / "factory-awk").write_bytes(app.get("armle/usr/bin/gawk"))
    (out / "stock-btstack").write_bytes(app.get("eso/bin/apps/btstack"))
    (out / "stock-cm").write_bytes(app.get("eso/bin/apps/connectionmanager"))
    (out / "stock-boot").write_bytes(app.get("eso/hmi/lsd/lsd.sh"))
    (out / "stock-bundles").write_bytes(app.get("eso/hmi/lsd/config/bundles.properties"))
    app.file.close()
    # Production configs already extracted/read through F3S by the target audit.
    for name in ("connectivity.json", "smartphone_integrator.json"):
        source = a.setup / name
        expected = json.loads((WIRELESS / "FIRMWARE-VERIFICATION.json").read_text())["production_configs"]["50"][name]["sha256"]
        assert sha(source.read_bytes()) == expected
        shutil.copy2(source, out / name)
    fake = b"isolated wireless transaction firmware gate\n"
    (out / "fixture-jxe").write_bytes(fake)
    fake_sha = sha(fake)
    controller = (layer / "control.sh").read_text()
    test_controller = controller.replace("09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a", fake_sha)
    check = (layer / "payload-check.sh").read_text().replace(sha(controller.encode()), sha(test_controller.encode()))
    test_sd = out / "payload"
    shutil.copytree(layer, test_sd)
    (test_sd / "control.sh").write_text(test_controller)
    (test_sd / "payload-check.sh").write_text(check)

    seeds = {
        "/mnt/app/carplay-mu1367-wireless-native/STATE": b"removed\n",
        "/mnt/app/carplay-mu1367-wireless-native-v161/STATE": b"removed\n",
        "/mnt/app/carplay-mu1367-wireless-native-v161/retained-v161-snapshot": b"v161 recovery preserved\n",
        "/mnt/app/carplay-mu1367-wireless-native/retained-test1-snapshot": b"test1 recovery preserved\n",
        "/mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar": (sd / "Custom/carplay_mu1367_guidance_v3/6/CarPlayMU1367Guidance.jar").read_bytes(),
        "/mnt/app/carplaymaps/PROFILE": b"MU1367/791\n",
        "/mnt/app/carplay-mu1367-guidance-v3/STATE": b"installed\n",
        "/mnt/app/carplay-mu1367-guidance-v3/VERSION": (sd / "Custom/carplay_mu1367_guidance_v3/6/VERSION").read_bytes(),
        "/mnt/app/carplaymaps/core.so": (sd / "Custom/carplay_mu1367_guidance_v3/6/core.so").read_bytes(),
        "/mnt/app/eso/hmi/lsd/jars/VCMenu.jar": (sd / "Custom/carplay_mu1367_guidance_v3/6/VCMenu.jar").read_bytes(),
        "/mnt/app/carplaymaps/carplay-cluster-supervisor": (sd / "Custom/carplay_mu1367_settings/carplay-cluster-supervisor").read_bytes(),
        "/mnt/app/carplaymaps/altscreen-most-bridge": (sd / "Custom/carplay_mu1367_guidance_v3/6/altscreen-most-bridge").read_bytes(),
        "/mnt/app/carplaymaps/dio_manager.wrapper.sh": (sd / "Custom/carplay_mu1367_settings/dio_manager.wrapper.sh").read_bytes(),
        "/mnt/app/eso/bin/apps/dio_manager": (sd / "Custom/carplay_mu1367_settings/dio_manager.wrapper.sh").read_bytes(),
        "/mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar": (sd / "Custom/carplay_mu1367_artwork/CarPlayMU1367Audio.jar").read_bytes(),
        "/mnt/system/etc/eso/production/connectivity.json": (out / "connectivity.json").read_bytes(),
        "/mnt/system/etc/eso/production/smartphone_integrator.json": (out / "smartphone_integrator.json").read_bytes(),
        "/mnt/app/eso/hmi/lsd/config/bundles.properties": (out / "stock-bundles").read_bytes(),
        "/mnt/app/eso/hmi/lsd/lsd.sh": (out / "stock-boot").read_bytes(),
        "/mnt/app/eso/bin/apps/btstack": (out / "stock-btstack").read_bytes(),
        "/mnt/app/eso/bin/apps/connectionmanager": (out / "stock-cm").read_bytes(),
        "/ifs/lsd.jxe": fake,
        "/mnt/persist/btwcp_off": b"old-off-marker\n",
        "/mnt/persist/wcp/keep-pairing": b"per-unit data stays here\n",
        "/mnt/app/carplay-mu1367-oem-reset/retained-snapshot": b"existing recovery snapshot\n",
    }
    script = '''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
export CPMAP_TEST_ROOT=/ramdisk/unit
P=/ramdisk/payload
R=$CPMAP_TEST_ROOT/mnt/app/carplay-mu1367-wireless-native-v161t2
V=/proc/boot/verify
mkdir -p "$CPMAP_TEST_ROOT/mnt/ota" "$CPMAP_TEST_ROOT/dev/shmem" "$CPMAP_TEST_ROOT/ramdisk"
cp -R /test/payload "$P"
'''
    for i,(target,data) in enumerate(seeds.items()):
        (out / ("seed%d" % i)).write_bytes(data)
        script += 'mkdir -p "$CPMAP_TEST_ROOT' + str(Path(target).parent) + '"\ncp /proc/boot/seed' + str(i) + ' "$CPMAP_TEST_ROOT' + target + '"\n'
    script += '''chmod 755 "$CPMAP_TEST_ROOT/mnt/app/carplaymaps/carplay-cluster-supervisor" "$CPMAP_TEST_ROOT/mnt/app/eso/hmi/lsd/lsd.sh"
baseline(){
'''
    for target,data in seeds.items(): script += ' "$V" "$CPMAP_TEST_ROOT' + target + '" ' + sha(data) + ' || exit 70\n'
    script += '''}
baseline
echo @@WIRELESS-TRANSACTIONS-BEGIN@@
# Wrong baseline is rejected before creating a recovery directory.
echo x >> "$CPMAP_TEST_ROOT/mnt/app/carplaymaps/altscreen-most-bridge"
if /bin/ksh "$P/control.sh" install "$P";then exit 71;fi
test ! -e "$R"
'''
    bridge_index = list(seeds).index("/mnt/app/carplaymaps/altscreen-most-bridge")
    script += 'cp /proc/boot/seed' + str(bridge_index) + ' "$CPMAP_TEST_ROOT/mnt/app/carplaymaps/altscreen-most-bridge"\n'
    script += '''# A symlink target must remain untouched.
echo protected > /ramdisk/protected
ln -s /ramdisk/protected "$CPMAP_TEST_ROOT/mnt/ota/wcp_receiver"
if /bin/ksh "$P/control.sh" install "$P";then exit 72;fi
grep '^protected$' /ramdisk/protected
test ! -e "$R"
rm "$CPMAP_TEST_ROOT/mnt/ota/wcp_receiver"
# SD corruption must not create snapshots or change any baseline target.
echo corruption >> "$P/payload/wcp_receiver"
if /bin/ksh "$P/control.sh" install "$P";then exit 73;fi
test ! -e "$R"
cp /test/payload/payload/wcp_receiver "$P/payload/wcp_receiver"
baseline
# An installed old layer must be removed before the v154 baseline is altered.
echo installed > "$CPMAP_TEST_ROOT/mnt/app/carplay-mu1367-wireless-native/STATE"
if /bin/ksh "$P/control.sh" install "$P";then exit 79;fi
test ! -e "$R"
echo removed > "$CPMAP_TEST_ROOT/mnt/app/carplay-mu1367-wireless-native/STATE"
echo installed > "$CPMAP_TEST_ROOT/mnt/app/carplay-mu1367-wireless-native-v161/STATE"
if /bin/ksh "$P/control.sh" install "$P";then exit 79;fi
test ! -e "$R"
echo removed > "$CPMAP_TEST_ROOT/mnt/app/carplay-mu1367-wireless-native-v161/STATE"
/bin/ksh "$P/control.sh" install "$P"
test "$(cat "$R/STATE")" = installed
'''
    # Every installed target must equal its staged payload or generated receipt.
    script += '/bin/ksh "$P/control.sh" install "$P"\n'
    script += '''# Unknown runtime drift is preserved by both uninstall and recover.
echo drift >> "$CPMAP_TEST_ROOT/mnt/ota/wcp_receiver"
if /bin/ksh "$R/control.sh" uninstall;then exit 74;fi
if /bin/ksh "$R/control.sh" recover;then exit 74;fi
cp /test/payload/payload/wcp_receiver "$CPMAP_TEST_ROOT/mnt/ota/wcp_receiver"
/bin/ksh "$R/control.sh" uninstall
baseline
test "$(cat "$R/STATE")" = removed
echo WIRELESS_INSTALL_REPEAT_REMOVE_PASS
'''
    # Fail and simulated power loss at each commit site, then exact recovery.
    script += 'for K in ' + ' '.join(keys) + ';do\n'
    script += ''' export CPMAP_TEST_FAIL_AFTER_KEY=$K
 if /bin/ksh "$P/control.sh" install "$P";then exit 75;fi
 unset CPMAP_TEST_FAIL_AFTER_KEY
 baseline
 test "$(cat "$R/STATE")" = removed
 echo "WIRELESS_ROLLBACK_PASS=$K"
 export CPMAP_TEST_INTERRUPT_AFTER_KEY=$K
 if /bin/ksh "$P/control.sh" install "$P";then exit 76;fi
 unset CPMAP_TEST_INTERRUPT_AFTER_KEY
 test "$(cat "$R/STATE")" = installing
 /bin/ksh "$R/control.sh" recover
 baseline
 test "$(cat "$R/STATE")" = removed
 echo "WIRELESS_RESUME_PASS=$K"
done
# Reinstall after all recoveries, reject corrupt backup before touching targets.
/bin/ksh "$P/control.sh" install "$P"
'''
    supervisor = by_target['/mnt/app/carplaymaps/carplay-cluster-supervisor']['key']
    script += 'cp "$R/backup/' + supervisor + '" /ramdisk/saved-supervisor\necho damage >> "$R/backup/' + supervisor + '"\n'
    script += '''if /bin/ksh "$R/control.sh" uninstall;then exit 77;fi
test "$(cat "$R/STATE")" = installed
'''
    script += 'cp /ramdisk/saved-supervisor "$R/backup/' + supervisor + '"\n'
    script += '''/bin/ksh "$R/control.sh" uninstall
baseline
echo WIRELESS_TRANSACTIONS_PASS
mkdir -p /ramdisk/session-unit/ramdisk/.v75-native-0123456789abcdef0123456789abcdef /ramdisk/session-unit/dev/shmem /ramdisk/session-unit/mnt/persist
/proc/boot/session-test
echo @@WIRELESS-TRANSACTIONS-END@@
'''
    (out / 'suite.sh').write_text(script)
    # ln is supplied by the target image too, not from the SDK.
    assert 'bin/ln' in files
    (out / 'factory-ln').write_bytes(files['bin/ln'])
    shutil.copy2(layer / 'verify', out / 'verify')
    shutil.copy2(layer / 'payload/wireless-entry', out / 'wireless-entry')
    shutil.copy2(a.h264_fixture, out / 'input.h264')
    script = (out / 'suite.sh').read_text().replace('echo @@WIRELESS-TRANSACTIONS-END@@', '/proc/boot/wireless-entry --selftest /ramdisk/input-test /proc/boot/input.h264\necho @@WIRELESS-TRANSACTIONS-END@@')
    (out / 'suite.sh').write_text(script)
    qnx = a.toolchain.resolve() / 'sdp/target/qnx6'
    run = lambda cmd: subprocess.run(cmd, check=True)
    run(['/Library/Developer/CommandLineTools/usr/bin/clang', '--target=armv7-none-eabi', '-D__QNXNTO__', '-D__QNX__', '-D__ARM__', '-D__LITTLEENDIAN__', '--sysroot='+str(qnx), '-isystem', str(qnx/'usr/include'), '-I', str(WIRELESS/'src'), '-DCPMAP_ROOT_PREFIX="/ramdisk/session-unit"', '-march=armv7-a', '-mfloat-abi=softfp', '-mno-unaligned-access', '-fno-short-enums', '-fno-builtin', '-fno-stack-protector', '-std=gnu99', '-O2', '-Wall', '-Wextra', '-Werror', str(WIRELESS/'tests/session.c'), '-c', '-o', str(out/'session.o')])
    template = (a.setup / 'test.build').read_text()
    # Retain its established boot block/filesystem harness, replace only the test files.
    start = template.index('[type=link] /usr/lib/ldqnx.so.2=')
    template = template[:start].replace('/bin/ksh /proc/boot/review.sh', '/bin/ksh /proc/boot/suite.sh').replace('procnto-smp -vvv', 'procnto-smp')
    template += '''[type=link] /usr/lib/ldqnx.so.2=/proc/boot/libc.so.3
[type=link] /bin/ksh=/proc/boot/ksh
[type=link] /bin/sh=/proc/boot/ksh
[type=link] /lib/dll/io-blk.so=/proc/boot/io-blk.so
[type=link] /lib/dll/fs-qnx6.so=/proc/boot/fs-qnx6.so
[type=link] /lib/dll/cam-disk.so=/proc/boot/cam-disk.so
[type=link] /lib/libcam.so.2=/proc/boot/libcam.so.2
[type=link] /usr/lib/libblkcache.so.2=/proc/boot/libblkcache.so.2
[type=dir] /ramdisk
[type=file]
[data=copy]
[perms=+r,+x]
libc.so.3
libsocket.so.3
libm.so.2
procnto-smp
devc-serdebug
pipe
c4-smoke
devb-ram
mkqnx6fs
mount
libcam.so.2
io-blk.so
fs-qnx6.so
cam-disk.so
libblkcache.so.2
[+raw]
'''
    for name in (*utilities, 'awk', 'ln'): template += name+'=factory-'+name+'\n'
    template += 'verify\nsuite.sh\nsession-test\nwireless-entry\ninput.h264\n'
    for i in range(len(seeds)):template += 'seed%d\n' % i
    for f in sorted(test_sd.rglob('*')):
        if f.is_file():template += '/test/payload/'+str(f.relative_to(test_sd))+'=payload/'+str(f.relative_to(test_sd))+'\n'
    (out/'test.build').write_text(template)
    lib='/opt/qnx650/target/qnx6/armle-v7/lib'
    (out/'prepare.sh').write_text('''#!/bin/sh
set -eu
arm-unknown-nto-qnx6.5.0eabi-ld -m armnto -Qy --dynamic-linker /usr/lib/ldqnx.so.2 -L{0} {0}/crt1.o {0}/crti.o {0}/crtbegin.o /w/session.o -lc {0}/crtend.o {0}/crtn.o -o /w/session-test
export MKIFS_PATH=/w:{0}/../boot/sys:{0}/../bin:{0}/../sbin:{0}:{0}/dll:{0}/../usr/lib
mkifs test.build ifs.bin
mkdir -p fat
mv ifs.bin fat/
'''.format(lib))
    docker=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-i','-v',str(out)+':/w','-w','/w']
    with (out/'prepare.log').open('w') as log:subprocess.run(docker+['cpmap-qnx65-sdp','sh','/w/prepare.sh'],stdout=log,stderr=subprocess.STDOUT,check=True)
    with (out/'qemu.log').open('wb') as log:
        proc=subprocess.Popen(docker+['cpmap-qemu-arm','timeout','1200','qemu-system-arm','-M','virt','-m','1024','-cpu','cortex-a15','-bios','/w/u-boot.bin','-drive','file=fat:rw:/w/fat,format=raw,media=disk','-nic','none','-display','none','-serial','stdio'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
        def expect(token,offset=0,seconds=30):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline and proc.poll() is None:
                pos=(out/'qemu.log').read_bytes().find(token,offset)
                if pos>=0:return pos+len(token)
                time.sleep(.1)
            raise RuntimeError('Missing QNX marker '+repr(token))
        def send(b):proc.stdin.write(b);proc.stdin.flush()
        try:
            at=expect(b'Hit any key to stop autoboot:');send(b'\n');at=expect(b'=> ',at)
            for cmd in (b'virtio scan\n',b'fatload virtio 0:1 0x40200000 ifs.bin\n'):
                send(cmd);at=expect(b'=> ',at)
            send(b'go 0x40200000\n');expect(b'@@HARNESS-FINISHED@@',at,1180)
        finally:
            proc.stdin.close();proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    text=(out/'qemu.log').read_text(errors='replace')
    rollbacks=len(re.findall(r'WIRELESS_ROLLBACK_PASS=',text));resumes=len(re.findall(r'WIRELESS_RESUME_PASS=',text))
    input_pass='OMONOB_791_ENTRY_SELFTEST_PASS' in text
    passed='WIRELESS_TRANSACTIONS_PASS' in text and 'WIRELESS_SESSION_PASS checks=17' in text and rollbacks==resumes==len(keys) and input_pass
    result=dict(passed=passed,build_id=manifest['build_id'],commit_sites=len(rows),tested_keys=keys,rollback_cases=rollbacks,resume_cases=resumes,session_checks=17,wireless_input_selftest=input_pass,h264_fixture_sha256=sha(a.h264_fixture.read_bytes()),firmware_utilities=True,fake_firmware_gate_in_fixture=True,baseline_seed='Published v1.5.4 final payload files; old installer not rerun in this fixture.',qemu_log_sha256=sha((out/'qemu.log').read_bytes()),on_unit_validated=False)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if not passed:raise RuntimeError('QNX suite failed; inspect qemu.log')


if __name__=='__main__':main()
