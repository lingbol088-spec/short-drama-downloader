# -*- encoding: utf-8 -*-
import time

import requests
from flurl.core import core_sixgod
from slider.slider import call_sliderV2

def call_slider(vdata):
    call_sliderV2(vdata)
    time.sleep(1)


def py_account_password(val: str, pwd=False) -> dict:
    """
    账号密码加密
    """
    if pwd:
        bytes_val = bytes(val, encoding='utf-8')
    else:
        if val[0] == '1' and len(val) == 11:
            bytes_val = bytes('+86 ' + val, encoding='utf-8')
        else:
            print(val)
            bytes_val = bytes('+852 ' + val, encoding='utf-8')
    new_val = ""
    for i in bytes_val:
        new_val += hex(i ^ 5)[2:]
    return new_val


def query_account(dev={}, mobile="", proxys=None):
    headers = {
        "Host": "api.amemv.com",
        "x-ss-stub": "15F6713C40BF83ADA974D66645ADE387",
        "x-tt-dt": "AAA3KGA2HHCKK5SOIOFNRELPMBBIYIUAZ4LZAUWQKNBKB6PZZ4ITNOT26Z5K6PXXJB2W5GS3N6FJ2Z5UFRMIFBKQGY6ODKGLTBIDM7TTHHHLKYICGQVFTOR7LEAJE",
        "activity_now_client": "1723656096723",
        "bd-ticket-guard-tee-status": "0",
        "sdk-version": "2",
        # "bd-ticket-guard-ree-public-key": "BHEjkgyNrTohBgKPUN8aq6cqF1hXGgZkWvCqwU0FN37XYsigKe8NEkmPpCzTYfnPQwfx73HGgw3pVAWMLzZr7zs=",
        "bd-ticket-guard-version": "3",
        "bd-ticket-guard-iteration-version": "2",
        # "bd-ticket-guard-client-csr": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURSBSRVFVRVNULS0tLS0KTUlJQkdEQ0J2d0lCQURBN01SZ3dGZ1lEVlFRRERBOWlaQzEwYVdOclpYUXRaM1ZoY21ReENUQUhCZ05WQkFzTQpBREVKTUFjR0ExVUVDZ3dBTVFrd0J3WURWUVFHRXdBd1dUQVRCZ2NxaGtqT1BRSUJCZ2dxaGtqT1BRTUJCd05DCkFBUnJxWWRzdTluUngxV3VwYW5HclhudGdOOGY0U2hhb2RBS0R3R1R1QjNqbHJ0MWx1ektkcXVFeWV0RWtyRTkKYlRsMStwUXVwbjJGRDdkeENYU1U1VWszb0NJd0lBWUpLb1pJaHZjTkFRa09NUk13RVRBUEJnTlZIUk1CQWY4RQpCVEFEQVFIL01Bb0dDQ3FHU000OUJBTUNBMGdBTUVVQ0lFb0wxWkhyd0tMY3A2L3kvOVJld3VJeVhPd09YR1BFCmNJTVhQM3JxRmpNb0FpRUE3OEdtQzNDZ3hteTYxazhyakhrVWg1Q2NsYU0rLzIrT08vY3c3RkYwNHhzPQotLS0tLUVORCBDRVJUSUZJQ0FURSBSRVFVRVNULS0tLS0K",
        # "x-tt-passport-trace-id": "find_account_e1e2dd47d1684277937a29a231386867",
        "passport-sdk-settings": "x-tt-token,sec_user_id",
        "passport-sdk-sign": "x-tt-token,sec_user_id",
        "passport-sdk-version": "203250",
        "x-vc-bdturing-sdk-version": "3.7.2.cn",
        "user-agent": "com.ss.android.ugc.aweme/310101 (Linux; U; Android 9; zh_CN; SKW-A0; Build/PQ3B.190801.06281541;tt-ok/3.12.13.4-tiktok)",
        # "x-ladon": "Zrznnw==",
        # "x-khronos": "1723656095",
        # "x-argus": "n+e8Zg==",
        # "x-gorgon": "8404c05e40815a8059c54d77850df338b32308c045d53ddf04f7",
        # "x-helios": "CN9PaETHeJv0j82za7ZDwJEVKt50NNx/MYcjNa6ksAXM5syl",
        # "x-medusa": "nOe8ZmgP45xIMGBdSc10Fsgo3X7x+AABuhVOcpM0AeYFOCEPyq2+cbyhnG1iNJHwT9DcjsMExvEs/qzSUI2gSMzcugHe847P7XsJb398q1znQERBMCgPueYO2lIHP3bk9VEITrKi243tOaaEwIbBX35Eb8k85TJJmP4p+XZSV9OINztPLFlRWXUdbcLmxW/8qFGn4iNq74Fqv1zFhmhpYSQbvOn6FxHFdG5f+Qqd57Iane1B8Op0BEeJd8+AiOD76bYWSVcco3OurKo/gpeeH8hvIGlytwcFB9bduEc3DZ+Jbq87hYzYMWNS2BPHqp3cefnppaVJ3C3XE8PXGN+7wqs0xY67wlUiE/ot8+SpYnaZ5P0GrcQjtnBUN9SPnSiBg/P9IGCxVqYZHzMcpETBr0Y8phEnS7CSN999Wl/oD2e55UpUtcSs1VFyE1LUbjhdicqGAJpUl09IZKAooBBcdknTAcjtTeBPotFxQQIPuYfxFsRwF6/9XiX2K/vFK0PtfjtenSHTqgsVFcR5+GWVc+sY1ZPEmstbK9ZPqmdesst9nNDPtQ6w+JxgP80rjY0+qummyHDGFdeh7MQP31Xyg63sUI+ply+Sdiu5fFVZZTKFLLE0YEHi/nKv8i+RXpGAZI2wQKkeN9HwpnUlSHR7YtM+fcs78kOZTF021QizU95nuLh+Bdhx8xapopRuUSDIgOo3SFZQkdZO/DV2+pSPFciW74X2Ib9h5j+H94YGyXliJMvcfbF5c+nSYJUrhxwXWYIGgl1WsRCyG8AeMtMPmBq9j6qXY9BepKvN19n5LSs0ARP18ZEpaBL6Fk3TQGvu30tzPBHh2LYrG4aByFz5CHY12E6ifuXEpU2yhtSNYx1AoU/2VtSUwexBKv6t3+XL9f7Nm98ZS95DMQmCKf049RxANug1o+4JLAYxgijsGZxkLKoSzVK5UhOtQKVy9MrYp2Sf056MdJoKICs/WpNQwPzqNBgth9fcrnfl/deT//3XEr9FKw==",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    cookies = {
        "store-region": "cn-gz",
        "store-region-src": "did",
        "install_id": "1132959998687130",
        "ttreq": "1$575c626c8bdde914622dc1bb92f10c79a8406792",
        "odin_tt": "8ad6aa7950339dbc65ceea85fed358ef4b88004b5ac0c9e09d7eb8bea1df25c17c928818199cf0066f4231ac1fca45faefb47744bd45d9cd34ff371e621c61e984e9059cf7e7fd5b6f9eedcac2e4ecf4",
        "passport_csrf_token": "5705bbb0d9251352fcf0e41c72ba2d36",
        "passport_csrf_token_default": "5705bbb0d9251352fcf0e41c72ba2d36",
        "d_ticket": "ec2c21b1f8183448987c2de3c5ef765a926d4"
    }
    url = "https://api.amemv.com/passport/safe/query_account/"
    params = {
        "is_vcd": "1",
        "request_tag_from": "h5",
        "iid": "1132959998687130",
        "device_id": "4281930742540667",
        "ac": "wifi",
        "channel": "update",
        "aid": "8662",
        "app_name": "aweme",
        "version_code": "310100",
        "version_name": "31.1.0",
        "device_platform": "android",
        "os": "android",
        "ssmix": "a",
        "device_type": "SKW-A0",
        "device_brand": "blackshark",
        "language": "zh",
        "os_api": "28",
        "os_version": "9",
        "manifest_version_code": "310101",
        "resolution": "900*1600",
        "dpi": "320",
        "update_version_code": "31109900",
        "_rticket": "1723656096257",
        "package": "com.ss.android.ugc.aweme",
        "mcc_mnc": "46000",
        "first_launch_timestamp": "0",
        "last_deeplink_update_version_code": "0",
        "cpu_support64": "true",
        "host_abi": "arm64-v8a",
        "is_guest_mode": "0",
        "app_type": "normal",
        "minor_status": "0",
        "appTheme": "light",
        "is_preinstall": "0",
        "need_personal_recommend": "1",
        "is_android_pad": "0",
        "is_android_fold": "0",
        "ts": "1723656096",
        "cdid": "23d5616d-df98-4769-bb85-13c9771b64cd",
        "okhttp_version": "4.2.195.7",
        "use_store_region_cookie": "1"
    }
    data = {
        "is_guest_mode": "0",
        "manifest_version_code": "310101",
        "_rticket": "1723656096256",
        "app_type": "normal",
        "is_preinstall": "0",
        "iid": "1132959998687130",
        "channel": "update",
        "is_android_pad": "0",
        "device_type": "SKW-A0",
        "language": "zh",
        "cpu_support64": "true",
        "host_abi": "arm64-v8a",
        "resolution": "900*1600",
        "scene": "find_account",
        "update_version_code": "31109900",
        "cdid": "23d5616d-df98-4769-bb85-13c9771b64cd",
        "minor_status": "0",
        "appTheme": "light",
        "os_api": "28",
        "is_android_fold": "0",
        "dpi": "320",
        "ac": "wifi",
        "package": "com.ss.android.ugc.aweme",
        "device_id": "4281930742540667",
        "os": "android",
        "mcc_mnc": "46000",
        "mix_mode": "1",
        "area_code": "86",
        "os_version": "9",
        "mobile": py_account_password(mobile),
        "version_code": "310100",
        "last_deeplink_update_version_code": "0",
        "query_type": "0",
        "app_name": "aweme",
        "version_name": "31.1.0",
        "device_brand": "blackshark",
        "need_personal_recommend": "1",
        "ssmix": "a",
        "device_platform": "android",
        "first_launch_timestamp": "0",
        "aid": "8662",
        "ts": "1723656096"
    }

    # 调用接口获取六神，并将六神更新至headers，更新业务接口params。注意，业务请求是POST时传data参数，GET不传。
    sign_headers, sign_urls = core_sixgod(surl=url, params=params, data=data, devices=dev, header=headers, log=True)
    # 直接调用返回的headers和url（url已经更新好并拼接了params，所以请求业务时不需要带params）
    response = requests.post(
        url=sign_urls,
        cookies=cookies,
        headers=sign_headers,
        data=data,
        proxies=proxys
    )
    print(response.text)
    if response.json()["data"].get("verify_center_decision_conf"):
        vdata = {
            "verify_data": response.json()["data"].get("verify_center_decision_conf"),
            "device_id": dev["device_id"] if dev else params["device_id"],
            "iid": dev["iid"] if dev else params["iid"],
            "proxy": ""
        }
        call_slider(vdata)
        dev["captchaVerify"] = "true"
        query_account(dev, mobile, proxys=proxys)
    else:
        if response.json()["data"].get("description") == "用户不存在":
            return response
        if dev.get("captchaVerify") == "true" and response.json()["message"] == "error":
            time.sleep(2)
            query_account(dev, mobile, proxys=proxys)



if __name__ == '__main__':

    dev = {"aid":"8662","iid":"3076883975280827","device_id":"3076883975276731","channel":"wandoujia_1128_0413","version_code":310900,"version_name":"31.9.0","device_type":"V2046A","device_brand":"vivo","device_model":"V2046A","device_manufacturer":"vivo","os_api":33,"os_version":"13","openudid":"db520532f38c6fe4","manifest_version_code":320300,"resolution":"2376×1080","dpi":480,"update_version_code":31909900,"host_abi":"arm64-v8a","cdid":"98203c9d-5d7f-46e6-940b-0294e6b5f324","uuid":"","mssdkVersionStr":"v04.06.01-ml-android","mssdkVersionInt":67502336,"ua":"com.ss.android.ugc.aweme/310900 (Linux; U; Android 13; zh_CN; V2046A; Build/TP1A.220624.014; Cronet/TTNetVersion:4801b8cf 2023-09-04 QuicVersion:0d108adb 2023-07-19)","x_tt_dt":"AAA74WVTJS462XT655SB5TK6ZBYJSIFYT4YIOJFIGKSEE4AECHUS2XXF5ITSCRPLQZY4HYOTLRJKMFHRS6MO3OJIXYSCTACYUPGZ7FGGQR4RHYMBX6UDWELMG7BEQ","mssdk_token":"AqG_OdHgdAhDy9ODqDjIq2JNe","rom":"eng.compil.20240308.210140","rom_version":"full_erd9815_rt-user 13 TP1A.220624.014 eng.compil.20240308.210140 release-keys","mssdk_token_200":"AThQKUmjHyypbjZnpnsX-Bl8E","mssdk_token_202":"AqG_OdHgdAhDy9ODqDjIq2JNe","first_launch_timestamp":1737360779777,"server_time":1737360828,"proxy":"","captchaVerify":"false"}

    mobile = f"13149542215"
    query_account(dev, mobile=mobile, proxys=None)
