# -*- encoding: utf-8 -*-
import base64
import json
import random
import time

from flurl.sign_proto import EecryptParams
from flurl.xgorgon import encrypt_gorgon
from flurl.header import get_params_encrypturl, xssstub_hash_md5_hex, url_encode
from flurl.helios import encrypt_helios
from flurl.medusa import gen_medusa

def lowerHeader(header: dict):
    """
    将header的key统一转换成小写
    """
    new_header = {}
    for key, value in header.items():
        new_header[str(key).lower()] = value
    header.clear()
    header.update(new_header)
    return new_header


def core_sixgod(surl, params, devices, data:dict={},  common=None, header=None, lanusk="", log=False):
    if devices:
        for k, v in devices.items():
            if k in data:
                data[k] = v
    dataType = header.get("content-type", header.get("Content-Type"))
    xg_rand = int(random.randint(0, 0xFFFF))
    url, url_params, x_common = get_params_encrypturl(surl, params=params, devices=devices, common=common)

    khronos = int(time.time())
    params = EecryptParams()
    params.khronos = str(khronos)
    params.ladon = base64.b64encode(khronos.to_bytes(4, 'big')).decode()
    params.argus = base64.b64encode(khronos.to_bytes(4, 'little')).decode()
    params.gorgon = encrypt_gorgon(data, url_encode(url_params), khronos, xg_rand, dataType)
    params.helios = encrypt_helios(khronos, rand=0)
    params.medusa = gen_medusa(
        url,
        url_params,
        devices,
        data,
        khronos,
        lanusk,
        dataType=dataType
    )
    six = result(params, data, url,  common=x_common, dataType=dataType, log=log)

    headers = header.copy()
    lowerHeader(header=headers)
    headers.update(six.get("sign_header"))
    if devices:
        headers["x-tt-dt"] = devices.get("x_tt_dt", "")
        headers["user-agent"] = devices.get("ua", "")
    return headers, six.get("sign_url")



def result(params: EecryptParams, data, eurl,  common=None, sell=False, dataType=None, log=False):

    six = {
        'x-ladon': params.ladon,
        'x-khronos': params.khronos,
        'x-argus': params.argus,
        'x-gorgon': params.gorgon,
        'x-helios': params.helios,
        'x-medusa': params.medusa
    }
    if data:
        six["x-ss-stub"] = xssstub_hash_md5_hex(data=data, dataType=dataType)
    if sell:
        datas: dict = dict()
        datas["api"] = eurl
        datas["sign"] = six
        if common:
            datas["sign"]["x-common-params-v2"] = common
        return datas
    datas: dict = dict()
    datas["sign_url"] = eurl
    datas["sign_header"] = six
    if common:
        datas["sign_header"]["x-common-params-v2"] = common
    if log:
        print(json.dumps(datas, indent=4, ensure_ascii=False))
    return datas