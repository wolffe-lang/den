"""R-vc03-1 / R-vc03-3: prove each canonicalized stat word against own lstat.
Git gitformat-index(5), Index entry. No implementation source consulted.
Only identity/time words differ between fixture copies; all other bytes stay exact.
"""
import hashlib
import os
import pathlib
import stat
import struct


def entries(raw):
    if len(raw) < 32 or raw[:4] != b'DIRC':
        raise ValueError('index header')
    end = len(raw) - 20
    if hashlib.sha1(raw[:end]).digest() != raw[end:]:
        raise ValueError('index checksum')
    version, count = struct.unpack_from('>II', raw, 4)
    if version not in (2, 3, 4) or count > (end - 12) // 64:
        raise ValueError('index version/count')
    pos = 12
    previous = b''
    result = []
    for _ in range(count):
        start = pos
        if end - pos < 63:
            raise ValueError('index entry truncated')
        words = struct.unpack_from('>10I', raw, pos)
        flags = struct.unpack_from('>H', raw, pos+60)[0]
        pos += 62
        extended = 0
        if flags & 0x4000:
            if version == 2 or end-pos < 3:
                raise ValueError('index extended flags')
            extended = struct.unpack_from('>H', raw, pos)[0]
            pos += 2
            if extended & ~0x6000:
                raise ValueError('index unknown extended bit')
        remove = 0
        if version == 4:
            while True:
                if pos >= end or remove > len(previous):
                    raise ValueError('index prefix overflow')
                octet = raw[pos]
                pos += 1
                remove = remove * 128 + (octet & 127)
                if octet < 128:
                    break
                remove += 1
            if remove > len(previous):
                raise ValueError('index invalid prefix')
        stop = raw.find(b'\0', pos, end)
        if stop < 0:
            raise ValueError('index path terminator')
        name = (previous[:len(previous)-remove] if version == 4 else b'') + raw[pos:stop]
        if not name or any(c in (b'', b'.', b'..', b'.git') for c in name.split(b'/')):
            raise ValueError('index path')
        if (flags & 0xfff) != min(len(name), 0xfff):
            raise ValueError('index path length')
        pos = stop + 1
        if version != 4:
            padded = start + ((pos-start+7)//8)*8
            if padded > end or any(raw[pos:padded]):
                raise ValueError('index padding')
            pos = padded
        key = (name, (flags >> 12) & 3)
        if result and key <= result[-1]['key']:
            raise ValueError('index ordering')
        result.append(dict(offset=start, name=name, key=key, words=list(words), extended=extended))
        previous = name
    while pos < end:
        if end-pos < 8:
            raise ValueError('index extension header')
        size = struct.unpack_from('>I', raw, pos+4)[0]
        pos += 8
        if size > end-pos:
            raise ValueError('index extension size')
        pos += size
    return result


def proof(repo, raw):
    rows = []
    for entry in entries(raw):
        path = os.path.join(os.fsencode(repo), entry['name'])
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            observed = None
            raw_mode = None
        else:
            raw_mode = st.st_mode & 0xffffffff
            mode = 0o120000 if stat.S_ISLNK(st.st_mode) else (0o100755 if st.st_mode & 0o100 else 0o100644)
            observed = [st.st_ctime_ns//10**9, st.st_ctime_ns%10**9,
                        st.st_mtime_ns//10**9, st.st_mtime_ns%10**9,
                        st.st_dev, st.st_ino, mode, st.st_uid, st.st_gid, st.st_size]
            observed = [x & 0xffffffff for x in observed]
        rows.append(dict(path_hex=entry['name'].hex(), stage=entry['key'][1],
                         index_stat=entry['words'], own_worktree_stat=observed,
                         own_lstat_mode=raw_mode,
                         own_stat_equal=entry['words'] == observed,
                         proven=observed is not None and entry['words'][:6] == observed[:6]))
    return rows


def canonical_pair(left, right, left_rows, right_rows):
    """No normalization unless BOTH sides prove all six differing timing/identity words.
    Unchanged cached entries retain original bytes and require no fresh stat.
    Mode/uid/gid/size are never normalized, per adopted R-vc03-3 A.
    """
    aa, bb = entries(left), entries(right)
    if len(aa) != len(bb) or len(aa) != len(left_rows) or len(bb) != len(right_rows):
        raise ValueError('index proof count')
    a, b = bytearray(left), bytearray(right)
    proven = 0
    for x, y, px, py in zip(aa, bb, left_rows, right_rows):
        if x['key'] != y['key']:
            return left, right, 0
        for entry, row in ((x, px), (y, py)):
            if (row['path_hex'] != entry['name'].hex() or row['stage'] != entry['key'][1]
                    or row['index_stat'] != entry['words']):
                raise ValueError('index proof binding')
        if x['words'] == y['words']:
            continue
        for entry, row in ((x, px), (y, py)):
            if row['proven'] is not True or row['own_worktree_stat'] is None or row['own_worktree_stat'][:6] != entry['words'][:6]:
                raise ValueError('unproven index stat '+entry['name'].hex())
        # Only the six timing/device/inode u32 words vary in cloned fixtures.
        a[x['offset']:x['offset']+24] = b'\0'*24
        b[y['offset']:y['offset']+24] = b'\0'*24
        proven += 2
    a[-20:] = hashlib.sha1(a[:-20]).digest()
    b[-20:] = hashlib.sha1(b[:-20]).digest()
    return bytes(a), bytes(b), proven
