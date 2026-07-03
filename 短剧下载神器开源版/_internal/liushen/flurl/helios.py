# -*- encoding: utf-8 -*-
import base64
import hashlib
import random

from Crypto.Util.Padding import pad

def ror(value, count):
    count %= 64
    low = value << (64 - count)
    value >>= count
    value |= low
    value &= 0xFFFFFFFFFFFFFFFF
    return value


HexTable = b"0123456789abcdef"


def bytes2matrix(text):
    return [int.from_bytes(list(text[i:i + 8]), 'little') for i in range(0, len(text), 8)]


def encrypt_helios_input(hash_table, in_data):
    data0 = int.from_bytes(in_data[:8], 'little')
    data1 = int.from_bytes(in_data[8:], 'little')
    for i in range(0, 0x22):
        hash1 = hash_table[i]
        data1 = hash1 ^ (data0 + ror(data1, 8))
        data1 &= 0xFFFFFFFFFFFFFFFF
        data0 = data1 ^ ror(data0, 61)
        data0 &= 0xFFFFFFFFFFFFFFFF

    return data0.to_bytes(8, 'little') + data1.to_bytes(8, 'little')


def encrypt_helios(khronos, rand=0):
    rand = rand or int(random.randint(0, 0xFFFFFFFF))
    data = rand.to_bytes(4, "little")
    data += str(8662).encode()
    key_sum = hashlib.md5(data).digest()

    keys = bytearray(32)
    for i in range(16):
        v1 = key_sum[i]
        keys[2 * i] = HexTable[v1 >> 4]
        keys[2 * i + 1] = HexTable[v1 & 15]

    hash_table = []
    hash_table.append(int.from_bytes(keys[:8], "little"))

    keys = bytes2matrix(keys)
    buffer_b0 = keys[0]
    buffer_b8 = keys[1]
    keys.pop(0)
    keys.pop(0)

    for i in range(0, 0x22):
        x9 = buffer_b0
        x8 = buffer_b8

        x8 = ror(x8, 8)
        x8 = x8 + x9
        x8 = (x8 ^ i) & 0xFFFFFFFFFFFFFFFF
        keys.append(x8)

        x8 = x8 ^ ror(x9, 61)
        x8 &= 0xFFFFFFFFFFFFFFFF

        # hash_table[index] = x8
        hash_table.append(x8)
        buffer_b0 = x8
        buffer_b8 = keys[0]
        keys.pop(0)

    in_data = pad(bytes(f"{khronos}-1588093228-8662", 'utf-8'), 16)
    out = bytearray()
    for i in range(len(in_data) // 16):
        out += encrypt_helios_input(hash_table, in_data[i * 16:i * 16 + 16])

    out = data[:4] + out
    return base64.b64encode(out).decode()