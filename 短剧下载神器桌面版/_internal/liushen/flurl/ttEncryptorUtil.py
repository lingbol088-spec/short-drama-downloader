import secrets
import hashlib
from Crypto.Cipher import AES  # pip install pycryptodome
from Crypto.Util.Padding import pad, unpad


def generate_rand_number():
    return secrets.token_bytes(32)


def decrypt_seeds():
    key1 = [0x52, 0x09, 0x6A, 0xD5, 0x30, 0x36, 0xA5, 0x38, 0xBF, 0x40, 0xA3, 0x9E, 0x81, 0xF3, 0xD7, 0xFB]
    key1 += [0x7C, 0xE3, 0x39, 0x82, 0x9B, 0x2F, 0xFF, 0x87, 0x34, 0x8E, 0x43, 0x44, 0xC4, 0xDE, 0xE9, 0xCB]
    key1 += [0x54, 0x7B, 0x94, 0x32, 0xA6, 0xC2, 0x23, 0x3D, 0xEE, 0x4C, 0x95, 0x0B, 0x42, 0xFA, 0xC3, 0x4E]
    key1 += [0x08, 0x2E, 0xA1, 0x66, 0x28, 0xD9, 0x24, 0xB2, 0x76, 0x5B, 0xA2, 0x49, 0x6D, 0x8B, 0xD1, 0x25]

    key2 = [0x1F, 0xDD, 0xA8, 0x33, 0x88, 0x07, 0xC7, 0x31, 0xB1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xEC, 0x5F]
    key2 += [0x60, 0x51, 0x7F, 0xA9, 0x19, 0xB5, 0x4A, 0x0D, 0x2D, 0xE5, 0x7A, 0x9F, 0x93, 0xC9, 0x9C, 0xEF]
    key2 += [0xA0, 0xE0, 0x3B, 0x4D, 0xAE, 0x2A, 0xF5, 0xB0, 0xC8, 0xEB, 0xBB, 0x3C, 0x83, 0x53, 0x99, 0x61]
    key2 += [0x17, 0x2B, 0x04, 0x7E, 0xBA, 0x77, 0xD6, 0x26, 0xE1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0C, 0x7D]

    results = bytearray()
    for i in range(len(key1)):
        results.append(key1[i] ^ key2[i])
    return results


def sha512(buff):
    sha512_hash = hashlib.sha512()
    sha512_hash.update(buff)
    return sha512_hash.digest()


def get_aes_key_iv(rand_num):
    rand_num_hash = sha512(rand_num)
    seeds = decrypt_seeds()
    data = rand_num_hash + seeds
    key_iv_hash = sha512(data)

    # print(f"rand_num:              {rand_num.hex()}")
    # print(f"rand_num_hash:         {rand_num_hash.hex()}")
    # print(f"seeds:                 {seeds.hex()}")
    # print(f"rand_num_hash + seeds: {data.hex()}")
    # print(f"key_iv_hash:           {key_iv_hash.hex()}")
    # print(f"aes key:               {key_iv_hash[0:0x10].hex()}")
    # print(f"aes iv:                {key_iv_hash[0x10:0x20].hex()}")
    return key_iv_hash[0:0x10], key_iv_hash[0x10:0x20]


def aes_128_cbc_encrypt(plaintext, key, iv):
    # 创建一个 AES 加密器对象
    cipher = AES.new(key, AES.MODE_CBC, iv)

    # 添加填充并加密数据
    padded_data = pad(plaintext, AES.block_size)
    ciphertext = cipher.encrypt(padded_data)
    return ciphertext


def get_magic():
    return b"\x74\x63\x05\x10\x00\x00"


def ttEncrypt(buff):
    magic = get_magic()
    rand_number = generate_rand_number()
    aes_key, aes_iv = get_aes_key_iv(rand_number)
    buff_hash = sha512(buff)
    aes_plaintext = buff_hash + buff
    aes_ciphertext = aes_128_cbc_encrypt(aes_plaintext, aes_key, aes_iv)

    #print(f"plaintext:     {buff.hex()}")
    #print(f"rand_number:   {rand_number.hex()}")
    #print(f"buff hash:     {buff_hash.hex()}")
    #print(f"aes_plaintext: {aes_plaintext.hex()}")
    #print(f"ciphertext:    {aes_ciphertext.hex()}")

    return magic + rand_number + aes_ciphertext


def main():
    buff = b'aabbccddeeffgg'
    result = ttEncrypt(buff)
    # print(f"ttEncrypt: {result.hex()}")


def test_aes():
    buff = b"\x61\x02\xbe\x54\xa6\x2a\x73\xe7\x65\xba\x38\xc9\x87\x34\x09\xbd" + \
           b"\xeb\xb6\xb0\xd3\x7e\xa0\x60\x40\x3d\x0c\x26\xfe\xa5\xeb\xb6\xba" + \
           b"\x5a\x0c\x7f\x36\xec\xb7\x58\xc7\x7e\x19\x37\x50\x5f\xa8\x5b\x4e" + \
           b"\x77\xce\x82\x7a\x70\x09\xd2\x2b\x2f\xaf\xc4\x68\x00\xd7\xa9\xff" + \
           b"\x62\x69\x61\x6e\x66\x65\x6e\x67"
    aes_key = b"\xe8\xaf\x6e\x91\xde\x99\x7e\xf0\xfa\xfb\xcd\xbe\x97\x73\xb2\xc5"
    aes_iv = b"\x03\x7e\xed\x97\x4e\x1e\xc5\x19\xdc\xc2\xb4\x35\x5b\x26\xf0\x1b"
    ciphertext = aes_128_cbc_encrypt(buff, aes_key, aes_iv)
    print(f"ciphertext: {ciphertext.hex()}")


if __name__ == "__main__":
    main()
    # test_aes()
