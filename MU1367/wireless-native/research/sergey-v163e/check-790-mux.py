#!/usr/bin/env python3
"""Decode real High-profile 790 video after the exact retained bridge's muxer.

This checks software conversion/muxing only, without simulating MOST success.
The synthetic input is deliberately unrelated to a user's map or phone.
"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1] / 'v162-next'
BRIDGE = BASE / 'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c'
p = argparse.ArgumentParser()
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
ffmpeg, ffprobe = '/opt/homebrew/bin/ffmpeg', '/opt/homebrew/bin/ffprobe'
run = lambda *args: subprocess.run(list(map(str, args)), check=True, capture_output=True)
run(ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=1010x376:rate=30',
    '-frames:v', '60', '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-profile:v', 'high',
    '-level:v', '3.1', '-x264-params', 'bframes=0:ref=4:keyint=30:min-keyint=30:scenecut=0:aud=1',
    '-f', 'h264', out / 'input.h264')
units = [n for n in re.split(b'\x00\x00\x00\x01|\x00\x00\x01',
                             (out / 'input.h264').read_bytes()) if n]
sps = next(n for n in units if n[0] & 31 == 7)
pps = next(n for n in units if n[0] & 31 == 8)
assert sps[1] == 100
config = bytes([1, sps[1], sps[2], sps[3], 255, 225])
config += struct.pack('>H', len(sps)) + sps + b'\x01' + struct.pack('>H', len(pps)) + pps
frames = []
for n in units:
    kind = n[0] & 31
    if kind == 9:
        frames.append([])
    elif kind not in (7, 8):
        frames[-1].append(n)
assert len(frames) == 60 and all(frames)
with (out / 'input.avcc').open('wb') as f:
    f.write(struct.pack('<I', len(config)) + config)
    for frame in frames:
        data = b''.join(struct.pack('>I', len(n)) + n for n in frame)
        key = any(n[0] & 31 == 5 for n in frame)
        f.write(struct.pack('<II', len(data), key) + data)

source = r'''
#define ALTSCREEN_BRIDGE_FILE_OUTPUT 1
#define main bridge_main_unused
#include "@BRIDGE@"
#undef main
#include <assert.h>
static uint32_t word(FILE *f) {
    uint8_t b[4];assert(fread(b,1,4,f)==4);
    return b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);
}
int main(int argc,char **argv) {
    AvcConfig config;FILE *in,*out;uint8_t *b,*es,packet[188];
    uint32_t size,key;size_t es_size;unsigned i=0;
    assert(argc==3);in=fopen(argv[1],"rb");out=fopen(argv[2],"wb");assert(in&&out);
    memset(&config,0,sizeof(config));assert(!queue_init(&g_queue));
    size=word(in);assert(size<65536);b=malloc(size);assert(b&&fread(b,1,size,in)==size);
    assert(!parse_avcc_config(&config,b,size));free(b);
    while(!feof(in)) {
        int ch=fgetc(in);if(ch==EOF)break;assert(ungetc(ch,in)!=EOF);
        size=word(in);key=word(in);assert(size>0&&size<262144&&key<=1);
        b=malloc(size);assert(b&&fread(b,1,size,in)==size);
        assert(avcc_to_annexb(&config,b,size,key,&es,&es_size)==(int)key);
        assert(!make_pat_packet(packet)&&fwrite(packet,188,1,out)==1);
        assert(!make_pmt_packet(packet)&&fwrite(packet,188,1,out)==1);
        make_pcr_packet(packet,90000ULL+i*3000);
        assert(fwrite(packet,188,1,out)==1);
        assert(!enqueue_pes(es,es_size,144000ULL+i*3000,key));
        while(queue_pop(&g_queue,packet))assert(fwrite(packet,188,1,out)==1);
        free(b);free(es);i++;
    }
    assert(!ferror(in)&&i==60);assert(!fclose(in)&&!fclose(out));
    free_config(&config);queue_destroy(&g_queue);
    puts("BRIDGE_790_HIGH_PROFILE_MUX_PASS frames=60");return 0;
}
'''.replace('@BRIDGE@', str(BRIDGE))
(out / 'test.c').write_text(source)
run('/Library/Developer/CommandLineTools/usr/bin/clang',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk',
    '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
    '-Wno-misleading-indentation', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
    '-I' + str(BASE / 'src/native'), '-I' + str(BRIDGE.parent),
    out / 'test.c', '-o', out / 'test')
r = run(out / 'test', out / 'input.avcc', out / 'output.ts')
(out / 'bridge.log').write_bytes(r.stderr)
def probe(path):
    return json.loads(run(ffprobe, '-v', 'error', '-show_entries',
                          'stream=width,height,profile,level,pix_fmt', '-of', 'json', path).stdout)['streams'][0]
def frames_hash(path):
    r = run(ffmpeg, '-v', 'error', '-err_detect', 'explode', '-i', path, '-an',
            '-fps_mode', 'passthrough', '-f', 'framemd5', '-')
    assert not r.stderr, r.stderr.decode()
    # Container time bases/PTS differ; compare decoded frame bytes and sizes.
    return [tuple(x.strip() for x in line.split(',')[-2:])
            for line in r.stdout.decode().splitlines() if not line.startswith('#')]
before, after = frames_hash(out / 'input.h264'), frames_hash(out / 'output.ts')
assert len(before) == len(after) == 60 and before == after
expected = dict(profile='High', width=1010, height=376, pix_fmt='yuv420p', level=31)
assert probe(out / 'input.h264') == probe(out / 'output.ts') == expected
report = dict(passed=True, test=r.stdout.decode().strip(), stream=expected,
              decoded_frames=60, decoded_frames_byte_identical=True,
              sanitizers=['address', 'undefined'],
              bridge_source_sha256=hashlib.sha256(BRIDGE.read_bytes()).hexdigest(),
              scope='Actual bridge AVCC conversion and PES/TS builders; synthetic input. '
                    'No live receiver capture, writer scheduling, MOST hardware or cluster decoding.')
(out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
