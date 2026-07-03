import hashlib

from flurl.header import xssstub_hash_md5_hex


def rc4_xg(data, key):
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i] = S[j]
    i = j = 0

    result = bytearray(len(data))
    for k, v in enumerate(data):
        i += 1
        x = S[i]
        j += x
        y = S[j & 0xff]
        S[i] = y
        result[k] = v ^ S[(y + y) & 0xff]

    return result


def reverse_bits(num):
    bin_num = bin(num)[2:].zfill(8)
    rev_bin_num = bin_num[::-1]
    rev_num = int(rev_bin_num, 2)

    return rev_num


gorgon_84 = bytes([0x4a, 0x16, 0x47, 0x6c, 0x84, 0x04])

def encrypt_gorgon(body, query, khronos, xg_rand, dataType):
    xg_seed = 320
    body_md5 = xssstub_hash_md5_hex(data=body, dataType=dataType).lower() if body else ""

    data = hashlib.md5(query.encode()).digest()[:4]

    if len(body_md5) > 0:
        body_md5 = bytes.fromhex(body_md5)
        data += body_md5[:4]
    else:
        data += bytearray([0, 0, 0, 0])
    data += bytearray([0, 0, 0, 0])
    mssdkVersionInt = 67503104
    data += mssdkVersionInt.to_bytes(4, "little")
    data += khronos.to_bytes(4, "big")
    key = bytes([
        gorgon_84[0],
        320 & 0xff,
        gorgon_84[1],
        (xg_rand >> 8) & 0xff,
        gorgon_84[2],
        gorgon_84[3],
        (320 >> 8) & 0xff,
        xg_rand & 0xff,
    ])

    out = rc4_xg(data, key)
    for i in range(len(out)):
        a = out[i]
        out[i] = (a >> 4 | (a << 4)) & 0xFF
        a = out[0]
        if i + 1 < len(out):
            a = out[i + 1]
        a ^= out[i]
        a = reverse_bits(a)
        out[i] = (~(a ^ 20)) & 0xFF

    ret = gorgon_84[-2:]
    ret += xg_rand.to_bytes(2, "little")
    ret += xg_seed.to_bytes(2, "little")
    ret += out

    return ret.hex()

