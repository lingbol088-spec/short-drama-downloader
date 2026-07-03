import base64
import binascii
import json
import time
from flurl.utils import *
from flurl.request_params import generate_url_params, generate_url_common_params
from flurl.utils  import UUID, md5, generate_mac_address, generate_android_id, gzip_compress, printf, cookie_string, cookie_json, get_trace_id
from flurl.ttEncryptorUtil  import ttEncrypt
import requests
from flurl.core import core_sixgod

def get_post_data(dev_info):
    itime = round(time.time() * 1000)
    gtime = round(time.time() * 1000)
    postDataObj = {
        "magic_tag": "ss_app_log",
        "header":{
            "display_name":"抖音",
            "update_version_code": dev_info['app']['update_version_code'],
            "manifest_version_code": dev_info['app']['manifest_version_code'],
            # "app_version_minor": "",
            "aid": 8662,
            "channel": dev_info['app']['channel'],
            "package": "com.ss.android.ugc.aweme",
            "app_version": dev_info['app']['version_name'],
            "version_code": dev_info['app']['version_code'],
            "sdk_version": "3.7.3-rc.53-douyin-bugfix",
            "sdk_target_version": 29,
            # "git_hash": "600a6e8",
            "os": dev_info['device']['os'],
            "os_version": dev_info['device']['os_version'],
            "os_api": dev_info['device']['os_api'],
            "device_model": dev_info['device']['device_type'],
            "device_brand": dev_info['device']['device_brand'],
            "device_manufacturer": "Google",
            "device_category": "phone",
            "cpu_abi": "arm64-v8a",
            "release_build": f"{UUID()}",
            "density_dpi": dev_info['device']['dpi'],
            "display_density": "mdpi",
            "resolution": dev_info['device']['resolution'].replace('*','x'),
            "language": "zh",
            "mac": generate_mac_address(),
            "timezone": 8,
            "access": "wifi",
            "not_request_sender": 0,
            "carrier": "CHINA MOBILE",
            "mcc_mnc": "46007",
            "rom": dev_info['device']['rom'],
            "rom_version": dev_info['device']['rom_version'],
            # "cdid": dev_info['device']['cdid'],
            "sig_hash": md5(UUID()),
            "openudid": dev_info['device']['openudid'],
            # "udid": dev_info['device']['udid'],
            "clientudid": dev_info['device']['clientudid'],
            "sim_serial_number": [],
            # "ipv6_list": [],
            "region": "CN",
            "tz_name": "Asia/Shanghai",
            "tz_offset": 28800,
            "sim_region": "cn",
            # "oaid_may_support": False,
            # "req_id": UUID(),
            # "device_platform": dev_info['device']['device_platform'],
            # "custom": {
            #     "client_ipv4": "127.0.0.1"
            # },
            # "apk_first_install_time": itime,
            # "is_system_app": 0,
            # "sdk_flavor": "china",
            # "guest_mode": 0
        },
        "_gen_time": gtime
    }

    return gzip_compress(json.dumps(postDataObj).encode(encoding='utf-8'))

def get_headers(dev_info, md5Hash=""):
    extra = {
        "content-type": "application/octet-stream;tt-data=a",
        'X-SS-STUB': md5Hash,
    }
    headers = {
            "accept-encoding": "gzip",
            "log-encode-type": "gzip",
            "x-tt-request-tag": "t=0;n=1",
            "x-ss-req-ticket": str(round(time.time() * 1000)),
            "sdk-version": "2",
            "passport-sdk-version": "203316",
            "x-vc-bdturing-sdk-version": "3.7.4.cn",
            "user-agent": dev_info['extra']['userAgent'],
            "host": "log.snssdk.com",
            "connection": "Keep-Alive",
        }
    if md5Hash:
        return  headers | extra
    return headers

def post_device_register(dev_info, extra):
    """
    Send device register request
    """

    url = "https://log.snssdk.com/service/2/device_register/"

    params = generate_url_params(dev_info, extra)

    req_url = f"{url}?{urllib.parse.urlencode(params)}"

    print(params)

    dev = {}

    gzip_post_data = get_post_data(dev_info)
    post_data = ttEncrypt(gzip_post_data)

    # headers = get_headers(dev_info, md5(post_data))

    headers = {
        "content-type": "application/octet-stream;tt-data=a",
        "accept-encoding": "gzip",
        "user-agent": dev_info['extra']['userAgent'],
        "host": "log.snssdk.com",
        "connection": "Keep-Alive",
    }

    #sign_headers, sign_urls = core_sixgod(surl=url, params=params, data=post_data, devices=dev, header=headers, log=False)

    response = requests.post(
        url=req_url,
        #cookies=cookies,
        headers=headers,
        data=post_data,
        #proxies=proxys
    )

    print(response.text)

    obj = json.loads(response.text)
    dev_info['device']['deviceId'] = str(obj["device_id"])
    dev_info['device']['iid'] = str(obj["install_id"])

    time.sleep(2)
    if not response.cookies:
        pass
    else:
        cookies_dict = cookie_json(response)
        dev_info['extra']['cookies'] = json.loads(json.dumps(cookies_dict, indent=4))
        print(dev_info['extra']['cookies'])

    return response

def send_app_alert_check(dev_info):
    """
    Send app alert check
    """

    url = "https://ichannel.snssdk.com/service/2/app_alert_check/"

    extra = {
        'device_id': dev_info['device']['deviceId'],
        'iid': dev_info['device']['iid'],
        #"tt_info": ""
    }

    params = generate_url_params(dev_info, extra)

    dev = {}

    headers = get_headers(dev_info)

    sign_headers, sign_urls = core_sixgod(surl=url, params=params, devices=dev, header=headers, log=False)

    response = requests.get(
        sign_urls,
        headers=sign_headers,
        # proxies=proxies
    )
    print(response.text)

    obj = json.loads(response.text)
    if not response.cookies:
        pass
    else:
        cookies_dict = cookie_json(response)
        dev_info['extra']['cookies'] = json.loads(json.dumps(cookies_dict, indent=4))

    time.sleep(2)

def device_register():
    openudid = generate_android_id()
    uuid = UUID()
    cdid = UUID()
    clientudid = UUID()
    rom = f'EMUI-{rand_str(13)}'

    manifest_version_code = '320901'
    os_version = '10'

    device_type = 'MI 12'
    ttNet = "TTNetVersion:9ac8d95c 2024-11-25 QuicVersion:3f326df4 2024-11-14"

    dev_info = {
        'device':{
            'os': 'Android',
            'device_platform': 'android',
            'device_type': device_type,
            'device_brand': 'Xiaomi',
            'os_api': '29',
            'os_version': os_version,
            'openudid': openudid,
            'resolution': '1440*2392',
            'dpi': '560',
            'cdid': cdid,
            'uuid': uuid,
            'clientudid': clientudid,
            'rom': rom,
            'rom_version': rand_str(2),
        },
        'app': {
            'channel':'douyin-ls-sm-xz-and-20',
            'version_code': '320900',
            'version_name': '32.9.0',
            'manifest_version_code': manifest_version_code,
            'update_version_code': '32909900',
            'okhttp_version': '4.2.210.13-douyin',
        },
        'extra':{
            'userAgent': f'com.ss.android.ugc.aweme/{manifest_version_code} (Linux; U; Android {os_version}; zh_CN; {device_type}; '
                         f'Build/MMB29M; Cronet/{ttNet})',
            'cookies': '',
        }
    }

    extra = {
        # "iid": "2320429612036292",
        # "device_id": "",
    }

    post_device_register(dev_info,extra)
    send_app_alert_check(dev_info)


device_register()