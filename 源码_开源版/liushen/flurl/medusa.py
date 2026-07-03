import base64
import random
import time

from flurl.sign_proto import (
    Medusa,
    Report,
    Device,
    MedushaAlgorithmCount,
    Env
)
from flurl.extra import (
    rl8,
    SM3,
    hash_f13,
    md5sum,
    get_key_hash,
    AES_V3
)
from flurl.header import xssstub_hash_md5_hex


def xmxor(data, key):
    data = xmxor_two(data, key)

    last_flag = data[-1] ^ data[-2]
    data0 = data[0]
    data[0] = (~last_flag + data[0]) & 0xff
    data[1] = ((data[0] ^ data[-1] ^ 254) + data[1]) & 0xff
    data[2] = (data[2] + ((last_flag - data0) ^ rl8(data[1], 3) ^ 2)) & 0xff

    for i in range(len(data) - 4):
        temp = (rl8(data[i + 2], 3)) ^ data[i + 1] ^ (i + 3)
        data[i + 3] = (~temp + data[i + 3]) & 0xff

    data[-1] ^= data[-2]

    sum = 0
    for i in range(len(data) - 1):
        sum += int(data[i + 1])

    data[0] = ((data[0] ^ data[1]) + sum) & 0xff
    return data


def xmxor_two(data, key):
    enc_data = bytearray(len(data))
    for i in range(len(data)):
        index = (i * 4) & 28
        d0 = key[index]
        d1 = key[index + 1]

        d2 = (rl8(data[i], 4) + d0) ^ d1
        d2 = ~d2
        d2 = (rl8(d2 & 0xff, 3)) & 0xff
        d2 += d1
        d2 = (d2 & 0xff) ^ d0
        enc_data[-i - 1] = ~d2 & 0xff
    return enc_data

def gen_medusa(url, url_params, devices, data:dict, khronos:int=None, lanusk=None, hash_rand=0, xm_rand=0, dataType=None):
    config = {
        'fix': bytes([0x35]),
        'aes_key': b'\xf1Y3vvn\xa9\x8d4\xf3\x1b\x05z\x9d[\xe4',
        'aes_iv': b'\x1f\xe1\t\xa4\x12R\x83\xf4\x18\xde\x9e\x05\x1a\x96\x9e\x12',
        'signKey': b'\x8e\xbd\xfa8\x06\xec\xc5\xce\xe7\x94#\xe6\x02\x9e\xd8%@\xbc"\x18\xbb~\xae\xf7\x1c\xb6\x91\xf7\xaa\x8a\xa2\xf5',
    }
    data, query_sm3, body_sm3 = gen_medusa_proto(url, url_params, devices, data, khronos, lanusk, dataType)

    hash_rand = hash_rand or int(random.randint(0, 0xFFFFFFFF))
    xm_rand = xm_rand or int(random.randint(0, 0xFFFFFFFF))
    key, seed = get_key_hash(config['signKey'], hash_rand)
    data = xmxor(data, key)
    xg_seed = 320
    data = xg_seed.to_bytes(8, "little") + data
    data = bytearray(data[::-1])
    for i in range(0, len(data)):
        data[i] = data[i] ^ seed[~i & 3]

    hash_rand_bytes = hash_rand.to_bytes(4, "little")
    check_bit = (query_sm3[0] & 63) << 14
    check_bit |= 0x18000001
    check_bit |= (body_sm3[0] & 63) << 8
    data = config['fix'] + xm_rand.to_bytes(4, 'little') + check_bit.to_bytes(4, 'little') + data + hash_rand_bytes[2:]
    data = AES_V3(config['aes_key'], khronos).encrypt(data, config['aes_iv'])
    version_or = bytes()
    version = bytes.fromhex("03 00 00 00 f7 e8 5f fa d7 d7 dc 3b d6 2a c8 70 57 cf 61 18 ")
    for i in range(0, 20, 4):
        d = int.from_bytes(version[i:i + 4], "little")
        d ^= khronos
        version_or += d.to_bytes(4, "little")

    data = version_or + hash_rand_bytes[:2] + int(256).to_bytes(2, "little") + data

    return base64.b64encode(data).decode()

def gen_medusa_proto(url, url_params, devices, data:dict, khronos:int=None, lanusk=None, dataType=None):
    xg_seed = 320
    body_md5 = xssstub_hash_md5_hex(data=data, dataType=dataType).lower() if data else ""
    if body_md5 != '':
        body_md5_bytes = bytes.fromhex(body_md5)
    else:
        body_md5_bytes = bytes(16)
    ts_bytes = khronos.to_bytes(4, "little")
    query_sm3 = SM3(url.split('?')[1]).digest()
    if len(lanusk) > 0:
        lanusk_sm3 = SM3(bytes.fromhex(lanusk) + ts_bytes).digest()
        lanusk_hash = md5sum(
            lanusk_sm3 + body_md5_bytes + bytes.fromhex("84 96 77 9d db 6d bc b6 d4 15 0b f8 80 01 00 00"))

        lanusk_hash = lanusk_hash
        psk_version = "1"
        query_body_hash_sm3 = SM3(url.split('?')[1].encode() + body_md5_bytes + b"1").digest()
    else:
        lanusk_hash = b''
        psk_version = 'none'
        query_body_hash_sm3 = SM3(url.split('?')[1].encode() + body_md5_bytes + b"none").digest()

    proto_data = Medusa(
        magic=bytearray(b'\xf7\xe8_\xfa\xd7\xd7\xdc;\xd6*\xc8pW\xcfa\x18'),
        version=3,
        rand=int(random.randint(0, 0xFFFFFFFF)),
        ms_app_id='8662',
        device_id=str(devices.get("device_id", url_params.get("device_id", url_params.get("did", "")))),
        license_id='1588093228',
        app_version=devices.get("version_name", url_params.get("version_name")),
        sdk_version_str='v04.06.04-ml-android',
        sdk_version=67503104,
        xg_seed_bytes=xg_seed.to_bytes(8, "little"),
        time=khronos,
        query_body_ts_hash=hash_f13(query_sm3, body_md5_bytes, ts_bytes, khronos),
        query_sm3=bytearray(query_sm3[:6]),
        request=MedushaAlgorithmCount(sign_count=111, report_count=10, setting_count=694367, unknown4=0, unknown5=586952199),
        sec_device_token='AXYQOS6n2m60x1fVZHIrH3iol',
        time2=khronos,
        lanusk_hash=lanusk_hash,
        query_body_hash_sm3=query_body_hash_sm3,
        psk_version=psk_version,
        call_type=312,
        env=Env(
            launch_time=random.randint(100, 120),
            unknown2=146331399,
            unknown3=146331396,
            unknown5=7,
            version='v04.06.04.03-bugfix',
            pid=random.randint(10001, 12000),
            device=Device(
                d1=1,
                collect_stat=2,
                aid='8662',
                device_id=str(devices.get("device_id", url_params.get("device_id", url_params.get("did", "")))),
                sec_device_token='Ai6svO3PyrwDOUSmO6ZcResxu',
                app_version='!noperm!',
                battery=-888888,
                battery2=-888888,
                battery_health=3,
                battery_changed=-888888,
                network='!notset!',
                tz='Asia/Shanghai,8',
                lan='zh_CN',
                cpu=4,
                sdcard=255.24993896484375,
                sdcard_used=35.58599090576172,
                memory=3.467449188232422,
                memory2=3.467449188232422,
                data=255.1754913330078,
                data_used=42.17544174194336,
                os_version=devices.get("os_version", url_params.get("os_version")),
                brightness=41,
                volume=36,
                ts=1728388016635,
                ts2=1728388016635,
                ts3=1728388016635,
                ts4=1728388016637,
                usb=-1,
                hw_version=devices.get("device_model", url_params.get("device_type")),
                brand=devices.get("device_brand", url_params.get("device_brand")),
                board=devices.get("device_model", url_params.get("device_type")),
                product_name=devices.get("device_model", url_params.get("device_type")),
                product_device=devices.get("device_manufacturer", devices.get("device_brand", url_params.get("device_brand"))),
                product_manufacturer=devices.get("device_brand", url_params.get("device_brand")),
                hardware=devices.get("device_brand", url_params.get("device_brand")),
                unknown38=31
            ),
            report=Report(
                time=devices.get("report_time", int(time.time())),
                state=-2,
                code=200,
                times=0,
                unknown6=0
            ),
            app_version=devices.get("version_name", url_params.get("version_name"))
        ),
        unknown24='{"cmr":16777216,"cmr2":16777216,"un_h":1879194040,"vpn":0,"kd":0,"fkd":3672518972,"pd":-1872573247,"dyn":"","do":0,"tk":true}'
    )

    return bytes(proto_data), query_sm3, proto_data.query_body_ts_hash


