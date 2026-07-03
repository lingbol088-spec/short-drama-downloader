# -*- encoding: utf-8 -*-
import hashlib
import json
import random
import time
from urllib.parse import urlencode, unquote



def extract_url_params(url) -> dict:
    """
        将urlencode类型的字符串转换成dict
    Args:
        url: str

    Returns: dict

    """
    params = {}
    parsed_url_list = url.split("?")[1].split("&") if "?" in url else url.split("&")
    for param in parsed_url_list:
        splited_param = param.split("=")
        params[splited_param[0]] = unquote(splited_param[1] if len(splited_param) == 2 else "")
    return params

def url_encode(data):
    param = urlencode(data)
    param = param.replace("+", "%20")
    param = param.replace("%2A", "*")
    return param


def get_params_encrypturl(url, params:dict=None, devices={}, common=None):
    x_common = {}
    if params:
        x_params = params.copy()
        if common:
            x_params.update(extract_url_params(common))
            x_common = extract_url_params(common)
        if devices:
            for k, v in devices.items():
                if k in x_params:
                    x_params[k] = v
                if k in x_common:
                    x_common[k] = v
                elif "did" in x_params and k == "device_id":
                    x_params["did"] = v
    else:
        x_params: dict = extract_url_params(url) if ("?" in url and len(url.split("?")) == 2 and url.split("?")[1]) else params
        if common:
            x_common = extract_url_params(common)
            x_params.update(x_common)
        if devices:
            for k, v in devices.items():
                if k in x_params:
                    x_params[k] = v
                if k in x_common:
                    x_common[k] = v
                elif "did" in x_params and k == "device_id":
                    x_params["did"] = v

    x_params["ts"] = int(time.time())
    x_params["_rticket"] = int(time.time() * 1e3)
    if x_common:
        x_common["ts"] = int(time.time())
        x_common["_rticket"] = int(time.time() * 1e3)
    eurl = url.split("?")[0] + "?" + url_encode(x_params) if "?" in url else url + "?" + url_encode(x_params)
    url_params: dict = x_params

    return eurl, url_params, url_encode(x_common)

def xssstub_hash_md5_hex(data, dataType:str=None):
    if not data:
        return str()
    if dataType == "md5":
        return data
    md5 = hashlib.md5()
    if isinstance(data, str):
        md5.update(data.encode('utf-8'))
    elif isinstance(data, bytes):
        md5.update(data)
    else:
        if dataType == "application/json; charset=UTF-8":
            md5.update(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        else:
            md5.update(urlencode(data).encode('utf-8'))
    xt = md5.hexdigest()
    return xt.upper()