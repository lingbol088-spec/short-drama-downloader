from flurl.utils import *

def generate_url_params(dev_info, extra={}):
    rticket = round(time.time() * 1000)
    first_ts = round(time.time())
    ts = round(time.time())
    url_params = {
        'tt_data': 'a',
        'os_api': dev_info['device']['os_api'],
        'device_type': dev_info['device']['device_type'],
        'ssmix': 'a',
        'manifest_version_code': dev_info['app']['manifest_version_code'],
        'dpi': dev_info['device']['dpi'],
        'version_name': dev_info['app']['version_name'],
        'ts': ts,
        'cpu_support64': 'true',
        'app_type': 'normal',
        'appTheme': 'light',
        'ac': 'wifi',
        'host_abi': 'arm64-v8a',
        'update_version_code': dev_info['app']['update_version_code'],
        'channel': dev_info['app']['channel'],
        '_rticket': rticket,
        'device_platform': 'android',
        'version_code': dev_info['app']['version_code'],
        'cdid': dev_info['device']['cdid'],
        'os': 'android',
        'is_android_pad': '0',
        'openudid': dev_info['device']['openudid'],
        'package': 'com.ss.android.ugc.aweme',
        'resolution': dev_info['device']['resolution'],
        'os_version': dev_info['device']['os_version'],
        'language': 'zh',
        'device_brand': dev_info['device']['device_brand'],
        'need_personal_recommend': '1',
        'aid': '8662',
        'minor_status': '0',
        'app_name': 'aweme',
        'mcc_mnc':'46007',

        # 'is_guest_mode': '0',
        # 'first_launch_timestamp': first_ts,
        # 'last_deeplink_update_version_code': '0',
        # 'is_preinstall': '0',
        # 'is_android_fold': '0',
        # 'md': '0',
        # 'okhttp_version': dev_info['app']['okhttp_version'],
        # 'use_store_region_cookie': '1'
    }
    merged_params = url_params | extra
    return merged_params

def generate_url_common_params(dev_info, extra={}):
    url_params = generate_url_params(dev_info,extra)
    return urllib.parse.urlencode(url_params)
