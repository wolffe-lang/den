"""Original RFC-format fixture builder, not a production codec.
Python zlib is consulted only as a black-box oracle. No codec source read.
"""
import random
import zlib


class Bits:
    def __init__(self):
        self.bits = []

    def put(self, value, width):
        self.bits.extend((value >> n) & 1 for n in range(width))

    def code(self, value, width):
        self.bits.extend((value >> n) & 1 for n in reversed(range(width)))

    def data(self):
        return bytes(sum(self.bits[i+j] << j for j in range(min(8, len(self.bits)-i)))
                     for i in range(0, len(self.bits), 8))


def fixed(b, s):
    if s < 144: b.code(48+s, 8)
    elif s < 256: b.code(400+s-144, 9)
    elif s < 280: b.code(s-256, 7)
    else: b.code(192+s-280, 8)


def stream(data, level=1, strategy=zlib.Z_DEFAULT_STRATEGY, raw=False):
    c = zlib.compressobj(level, zlib.DEFLATED, -15 if raw else 15, 8, strategy)
    return c.compress(data)+c.flush()


def wrap(raw, data):
    return b'\x78\x01'+raw+zlib.adler32(data).to_bytes(4, 'big')


def dynamic_header(lengths, nl=257, nd=1):
    b = Bits(); b.put(5,3); b.put(nl-257,5); b.put(nd-1,5); b.put(15,4)
    order = [16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15]
    for i in order: b.put(lengths[i],3)
    return b


def vectors():
    rows=[]
    def ok(name, encoded, decoded, raw=False):
        d=zlib.decompressobj(-15 if raw else 15); result=d.decompress(encoded); result+=d.flush()
        assert d.eof and result==decoded, name
        rows.append(dict(name=name, encoded=encoded, decoded=decoded, raw=raw,
                         consumed=len(encoded)-len(d.unused_data)))
    def bad(name, encoded, error, cap=100000, raw=False):
        rows.append(dict(name=name, encoded=encoded, error=error, cap=cap, raw=raw))
    ok('empty',stream(b''),b'')
    ok('stored',stream(b'abc',0),b'abc')
    ok('fixed',stream(b'abcabcabc',1,zlib.Z_FIXED),b'abcabcabc')
    data=b''.join(bytes([i])*i for i in range(16))
    enc=stream(data,6); assert (enc[2]>>1)&3==2
    ok('dynamic',enc,data)
    ok('concat',stream(b'a')+stream(b'b'),b'a')
    ok('trailing',stream(b'abc')+b'\xffgarbage',b'abc')
    for n in range(8):
        b=Bits();b.put(3,3)
        for _ in range(n): fixed(b,200)
        fixed(b,256)
        ok('padding-'+str(n),wrap(b.data(),bytes([200])*n),bytes([200])*n)
    # Multiple fixed blocks share history; explicit maximal overlapping copy.
    b=Bits(); b.put(2,3); fixed(b,65);fixed(b,256);b.put(3,3);fixed(b,285);b.code(0,5);fixed(b,256)
    ok('cross-block-overlap',wrap(b.data(),b'A'*259),b'A'*259)
    # Incomplete one-bit literal tree (only EOB), empty distance tree.
    lens=[0]*19;lens[0]=lens[1]=1;b=dynamic_header(lens)
    for _ in range(256):b.code(0,1)
    b.code(1,1);b.code(0,1);b.code(0,1)
    ok('single-eob-empty-distance',b.data(),b'',True)
    # Complete code-length tree containing repeats; repeat runs cross alphabets.
    lens=[0]*19;lens[0]=lens[1]=lens[16]=lens[18]=2
    # Invalid header/tree families are hand-encoded, not zlib-generated.
    bad('negative-limit',stream(b''),'invalid',-1)
    for n in range(2):bad('header-truncated-'+str(n),b'\x78\x01'[:n],'truncated')
    bad('method',b'\x79\x18','bad_header');bad('window',b'\x88\x1c','bad_header')
    bad('fcheck',b'\x78\x00','bad_header');bad('dictionary',b'\x78\x20','dictionary')
    bad('checksum',stream(b'abc')[:-1]+b'\x00','checksum')
    for n in range(4):bad('checksum-short-'+str(n),stream(b'abc')[:-(n+1)],'truncated')
    bad('reserved',b'\x07','invalid',raw=True)
    bad('stored-short',b'\x01\x03','truncated',raw=True)
    bad('stored-inverse',b'\x01\x03\x00\xfd\xffabc','invalid',raw=True)
    bad('stored-payload-short',b'\x01\x03\x00\xfc\xffab','truncated',raw=True)
    bad('limit-stored',stream(b'abc',0),'limit',2)
    bad('limit-literal',stream(b'abc',1,zlib.Z_FIXED),'limit',2)
    bad('limit-overlap',stream(b'A'*259),'limit',258)
    for s in [286,287]:
        b=Bits();b.put(3,3);fixed(b,s);bad('reserved-length-'+str(s),b.data(),'invalid',raw=True)
    for s in [30,31]:
        b=Bits();b.put(3,3);fixed(b,257);b.code(s,5);bad('reserved-distance-'+str(s),b.data(),'invalid',raw=True)
    b=Bits();b.put(3,3);fixed(b,257);b.code(0,5);bad('distance-before-start',b.data(),'invalid',raw=True)
    b=Bits();b.put(5,3);b.put(31,5);b.put(0,5);b.put(0,4);bad('hlit-reserved',b.data(),'invalid',raw=True)
    lens=[0]*19;b=dynamic_header(lens);bad('empty-code-tree',b.data(),'invalid',raw=True)
    lens[0]=2;b=dynamic_header(lens);bad('incomplete-code-tree',b.data(),'invalid',raw=True)
    lens[0]=lens[1]=lens[2]=1;b=dynamic_header(lens);bad('oversubscribed-code-tree',b.data(),'invalid',raw=True)
    lens=[0]*19;lens[0]=lens[16]=1;b=dynamic_header(lens);b.code(1,1);bad('repeat-without-previous',b.data(),'invalid',raw=True)
    lens=[0]*19;lens[0]=lens[18]=1;b=dynamic_header(lens);b.code(1,1);b.put(127,7);b.code(1,1);b.put(127,7)
    bad('repeat-overflow',b.data(),'invalid',raw=True)
    lens=[0]*19;lens[0]=lens[1]=1;b=dynamic_header(lens)
    for _ in range(258):b.code(0,1)
    bad('missing-eob',b.data(),'invalid',raw=True)
    b=dynamic_header(lens)
    for i in range(258):b.code(1 if i in [0,1,256] else 0,1)
    bad('oversubscribed-literal-tree',b.data(),'invalid',raw=True)
    lens=[0]*19;lens[0]=lens[2]=1;b=dynamic_header(lens)
    for i in range(258):b.code(1 if i==256 else 0,1)
    bad('incomplete-literal-tree',b.data(),'invalid',raw=True)
    lens=[0]*19;lens[0]=lens[1]=1;b=dynamic_header(lens,nd=3)
    for i in range(260):b.code(1 if i>=256 else 0,1)
    bad('oversubscribed-distance-tree',b.data(),'invalid',raw=True)
    lens=[0]*19;lens[0]=1;lens[1]=lens[2]=2;b=dynamic_header(lens)
    for _ in range(256):b.code(0,1)
    b.code(2,2);b.code(3,2)
    bad('incomplete-distance-tree',b.data(),'invalid',raw=True)
    # A literal/length tree containing EOB and length 257, no distance codes.
    lens=[0]*19;lens[0]=lens[1]=1;b=dynamic_header(lens,nl=258)
    for _ in range(256):b.code(0,1)
    b.code(1,1);b.code(1,1);b.code(0,1);b.code(1,1)
    bad('empty-distance-used',b.data(),'invalid',raw=True)
    return rows


def payloads():
    rng=random.Random(0x19501951)
    for n in [0,1,2,3,55,56,63,64,65,257,258,259,32767,32768,32769,65535,65536]:
        yield 'random-'+str(n),rng.randbytes(n)
        yield 'zero-'+str(n),bytes(n)
        yield 'alphabet-'+str(n),(bytes(range(256))*((n+255)//256))[:n]
    yield 'long-distance', rng.randbytes(32768)*2
    yield 'text',b'The quick brown wolf keeps its history in the den.\n'*2000


def bounds():
    # Independent RFC fixed codes exercise every length and each distance range.
    bases=[3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258]
    def match(length,distance):
        b=Bits();b.put(3,3)
        lc=max(i for i,x in enumerate(bases) if x<=length)
        fixed(b,257+lc);extra=0 if lc<8 or lc==28 else (lc-4)//4
        b.put(length-bases[lc],extra)
        dc=max(i for i in range(30) if (i+1 if i<4 else (2+i%2)*(1<<(i//2-1))+1)<=distance)
        base=dc+1 if dc<4 else (2+dc%2)*(1<<(dc//2-1))+1
        b.code(dc,5);b.put(distance-base,0 if dc<4 else dc//2-1);fixed(b,256)
        prefix=bytes(i%256 for i in range(distance))
        stored=b'\x00'+len(prefix).to_bytes(2,'little')+(65535-len(prefix)).to_bytes(2,'little')+prefix
        out=prefix+bytes(prefix[i%distance] for i in range(length))
        return stored+b.data(),out
    for n in range(3,259):yield 'length-'+str(n),*match(n,1)
    for dc in range(30):
        base=dc+1 if dc<4 else (2+dc%2)*(1<<(dc//2-1))+1
        extra=0 if dc<4 else dc//2-1
        for distance in sorted({base,base+(1<<extra)-1}):yield 'distance-'+str(distance),*match(258,distance)
