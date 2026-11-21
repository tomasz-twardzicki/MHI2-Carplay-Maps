"""Read-only F3S reader reused from the MU1367 firmware audit."""
import struct
import hashlib
sha=lambda data:hashlib.sha256(data).hexdigest()

def f3s_files(raw):
    power=struct.unpack_from('<H',raw,4)[0]; size=1<<power
    boot=raw.index(b'QSSL_F3S')-4
    assert raw[boot+2:boot+4]==b'\x03\0'
    align=struct.unpack_from('<H',raw,boot+18)[0]
    units={}
    for base in range(0,len(raw),size):
        if raw[base:base+3]!=b'\x10\0L':continue
        h=base+size-64
        if struct.unpack_from('<I',raw,h)[0]&0x70!=0x30:continue
        logoff=((raw[h+19]<<16)|struct.unpack_from('<H',raw,h+20)[0])<<align
        logical=struct.unpack_from('<H',raw,base+logoff+2)[0]
        if logical!=65535:
            assert logical not in units
            units[logical]=base
    def extent(ptr):
        u,i=ptr;base=units[u];h=base+size-32*(i+1)
        a,b,c=struct.unpack_from('<3I',raw,h);assert a==b==c and a&0x70==0x30 and not a&1 and a&4
        off=(raw[h+19]<<16)|struct.unpack_from('<H',raw,h+20)[0]
        off<<=align;n=struct.unpack_from('<H',raw,h+22)[0]
        assert off+n<=size-32*(i+1)
        nxt=struct.unpack_from('<HH',raw,h+24)
        return raw[base+off:base+off+n],None if a&2 else nxt,a
    files={}; metadata={}
    def visit(ptr,parent):
        visited=set()
        while ptr:
            assert ptr not in visited;visited.add(ptr)
            b,nxt,status=extent(ptr)
            assert status&0x300==0x200
            if not b:
                assert nxt is None
                return
            structsize,moves,length,firstu,firsti=struct.unpack_from('<HBBHH',b)
            assert structsize==8
            name=b[8:8+length].rstrip(b'\0').decode()
            statpos=(8+length+3)&~3
            statsize,mode=struct.unpack_from('<HH',b,statpos);assert statsize==20
            path=parent+'/'+name if parent else name
            first=None if (firstu,firsti)==(65535,65535) else (firstu,firsti)
            if mode&0o170000==0o040000:
                if first:visit(first,path)
            else:
                content=bytearray();extents=[];seen=set()
                while first:
                    assert first not in seen;seen.add(first)
                    part,after,st=extent(first);assert st&0x300==0x300
                    content.extend(part);extents.append(list(first));first=after
                files[path]=bytes(content);metadata[path]={'mode':oct(mode),'extents':extents,'size':len(content),'sha256':sha(content)}
            ptr=nxt
    visit((1,3),'')
    return files,metadata
