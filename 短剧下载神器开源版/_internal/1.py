"""
Python translation of 1.go — Short drama video parsing endpoint
Handles: video_model API → fallback_api → download & CENC decrypt → serve local MP4

Reference: decrypt.py logic for CENC decryption and spade_a key derivation.
"""

import os
import re
import json
import sys
import time
import struct
import base64
import hashlib
import binascii
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlsplit, parse_qsl

import requests
from Crypto.Cipher import AES
from Crypto.Util import Counter

LIUSHEN_DIR = Path(__file__).resolve().parent / "liushen"
if str(LIUSHEN_DIR) not in sys.path:
    sys.path.insert(0, str(LIUSHEN_DIR))


def load_dotenv_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs from .env without adding a dependency."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv_file(Path(__file__).resolve().parent / ".env")

from flurl.core import core_sixgod

# ─── Constants ───────────────────────────────────────────────────────────────

USER_AGENT = (
    "com.phoenix.read/71332 (Linux; U; Android 16; zh_CN; 25053RT47C; "
    "Build/BP2A.250605.031.A3; Cronet/TTNetVersion:04657795 2026-01-23 "
    "QuicVersion:c67e9834 2025-09-08)"
)

VIDEO_MODEL_URL_TEMPLATE = (
    "https://api5-normal-sinfonlineb.fqnovel.com/novel/player/multi_video_model/v1/"
    "?iid={install_id}&device_id={device_id}&ac=wifi&channel=update_64&aid=8662"
    "&app_name=novelread&version_code=71332&version_name=7.1.3.32"
    "&device_platform=android&os=android&ssmix=a&device_type=25053RT47C"
    "&device_brand=Redmi&language=zh&os_api=36&os_version=16"
    "&manifest_version_code=71332&resolution=1280*2772&dpi=520"
    "&update_version_code=71332&host_abi=arm64-v8a&dragon_device_type=phone"
    "&pv_player=71332&compliance_status=0&need_personal_recommend=1"
    "&player_so_load=1&is_android_pad_screen=0"
)

# ─── Helpers (stubs — adapt to your BaseEndpoint equivalents) ─────────────────

def load_local_config() -> Dict[str, Any]:
    """Load optional local runtime config from config.json beside script/exe."""
    config_path = get_runtime_base_dir() / "config.json"
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"[config] failed_to_read_config={config_path} error={exc}")
        return {}


def get_device_keys() -> Dict[str, str]:
    """Return device credentials from env vars or local config.json.

    ?????????? device_id / install_id??????????
    ?? EXE ??????????????????? config.json?
    """
    config = load_local_config()

    device_id = (
        os.getenv("DUANJU_DEVICE_ID")
        or str(config.get("device_id") or config.get("DUANJU_DEVICE_ID") or "")
    ).strip()
    install_id = (
        os.getenv("DUANJU_INSTALL_ID")
        or str(config.get("install_id") or config.get("DUANJU_INSTALL_ID") or "")
    ).strip()
    platform = (
        os.getenv("DUANJU_PLATFORM")
        or str(config.get("platform") or config.get("DUANJU_PLATFORM") or "android")
    ).strip() or "android"

    if not device_id or not install_id:
        raise RuntimeError(
            "Missing device configuration. Set DUANJU_DEVICE_ID / "
            "DUANJU_INSTALL_ID, or open the web UI and save local config."
        )

    return {
        "device_id": device_id,
        "install_id": install_id,
        "platform": platform,
    }

def build_liushen_device(device_keys: Dict[str, str]) -> Dict[str, str]:
    """Build the minimum device payload required by liushen signing."""
    return {
        "device_id": device_keys.get("device_id", ""),
        "iid": device_keys.get("install_id", ""),
        "install_id": device_keys.get("install_id", ""),
        "device_brand": "Redmi",
        "device_model": "25053RT47C",
        "device_type": "25053RT47C",
        "device_manufacturer": "Xiaomi",
        "os_version": "16",
        "version_name": "7.1.3.32",
        "ua": USER_AGENT,
    }


def sign_json_request_with_liushen(
    url: str,
    body_obj: Dict[str, Any],
    device_keys: Dict[str, str],
) -> Tuple[str, Dict[str, str], bytes]:
    """JSON dump before signing, then reuse the same bytes for the POST body."""
    body_text = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
    body_data = json.loads(body_text)
    body_bytes = body_text.encode("utf-8")

    ts = str(int(time.time() * 1000))
    base_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json; charset=utf-8,application/x-protobuf",
        "Content-Type": "application/json; charset=UTF-8",
        "x-xs-from-web": "0",
        "x-ss-req-ticket": ts,
        "x-tt-request-tag": "t=0;n=0",
        "sdk-version": "2",
        "passport-sdk-version": "50561",
        "x-vc-bdturing-sdk-version": "3.7.2.cn",
    }

    url_parts = urlsplit(url)
    base_url = f"{url_parts.scheme}://{url_parts.netloc}{url_parts.path}"
    params = dict(parse_qsl(url_parts.query, keep_blank_values=True))
    sign_headers, sign_url = core_sixgod(
        surl=base_url,
        params=params,
        data=body_data,
        devices=build_liushen_device(device_keys),
        header=base_headers,
        log=False,
    )
    return sign_url, sign_headers, body_bytes


def replace_failed_device(device_id: str, platform: str) -> None:
    """Mark a device as failed so it isn't reused. Hook for your device pool."""
    pass


def get_current_domain(request=None) -> str:
    """Return the current server's base URL for serving local files."""
    if request is not None:
        return request.host_url.rstrip("/")
    return f"http://127.0.0.1:{os.getenv('APP_PORT', '5000')}"


def get_runtime_base_dir() -> Path:
    """Return the directory of the running exe or script."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


DEFAULT_TIMEOUT = 30
VIDEO_WORKER_POOL = ThreadPoolExecutor(max_workers=4)
FFMPEG_BIN = "ffmpeg"
VIDEO_TTL_SECONDS = 300


def get_ffmpeg_binary() -> str:
    """Resolve ffmpeg for source checkout and PyInstaller onedir runs."""
    runtime_dir = get_runtime_base_dir()
    candidates = [
        runtime_dir / "ffmpeg.exe",
        runtime_dir / "??" / "ffmpeg.exe",
        Path(getattr(sys, "_MEIPASS", runtime_dir)) / "ffmpeg.exe",
        Path(getattr(sys, "_MEIPASS", runtime_dir)) / "??" / "ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return os.getenv("FFMPEG_BIN", FFMPEG_BIN)


def schedule_video_cleanup(filepath: Path, delay_seconds: int = VIDEO_TTL_SECONDS) -> None:
    """Delete generated video files after a fixed retention period."""

    def _delete_file() -> None:
        try:
            filepath.unlink(missing_ok=True)
            print(f"[cleanup] deleted_expired_video={filepath.name}")
        except Exception as exc:
            print(f"[cleanup] delete_failed file={filepath.name} error={exc}")

    timer = threading.Timer(delay_seconds, _delete_file)
    timer.daemon = True
    timer.start()


def curl_request(
    url: str,
    headers: Dict[str, str],
    post_body: Optional[bytes] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> bytes:
    """Minimal HTTP request helper — mimics Go's curlRequest."""
    if post_body is not None:
        resp = requests.post(url, headers=headers, data=post_body, timeout=timeout)
    else:
        resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.content


# ─── Main endpoint (matching 1.go Handle / resolveVideoURL) ──────────────────

def handle_video_request(
    video_id: str,
    request=None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Top-level handler. Given a video_id, returns the flattened response payload.
    """
    return resolve_video_url(video_id, request, max_retries)


def resolve_video_url(
    video_id: str,
    request=None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Full flow (with retries):
      1. get device_keys
      2. POST multi_video_model
      3. extract fallback_api
      4. download + CENC-decrypt best-quality video
    Returns a flattened response dict.
    """
    last_err: Optional[Exception] = None

    for attempt in range(max_retries):
        device_keys = get_device_keys()
        target_url = build_video_model_url(
            device_keys["device_id"], device_keys["install_id"]
        )

        post_payload = {
            "biz_param": {
                "detail_page_version": 0,
                "device_level": 3,
                "disable_digg_stat": False,
                "need_all_video_definition": True,
                "need_mp4_align": False,
                "use_os_player": False,
                "use_server_dns": False,
                "video_platform": 1024,
            },
            "mixed_video_id_map": {
                "1004": [video_id],
            },
        }
        signed_url, headers, post_body = sign_json_request_with_liushen(
            target_url, post_payload, device_keys
        )

        try:
            resp = curl_request(signed_url, headers, post_body, 30)
        except Exception as exc:
            last_err = Exception(f"video_model request failed: {exc}")
            time.sleep(0.1)
            continue

        try:
            data = json.loads(resp)
        except Exception as exc:
            last_err = Exception(f"video_model JSON parse failed: {exc}")
            continue

        if not isinstance(data, dict) or "data" not in data:
            print("video_model raw response:")
            print(json.dumps(data, ensure_ascii=False, indent=2))

        try:
            fallback_api, video_model = extract_fallback_api(data, video_id)
        except Exception as exc:
            last_err = exc
            continue

        try:
            result = download_and_decrypt_video(
                request,
                fallback_api,
                video_model,
                device_keys,
                video_id,
                max_retries=3,
            )
            return result
        except Exception as exc:
            last_err = exc
            time.sleep(0.1)
            continue

    raise Exception(f"Video request failed, retried {max_retries} times: {last_err}")


def build_video_model_url(device_id: str, install_id: str) -> str:
    """Build the multi_video_model request URL (uses url-encoded params)."""
    from urllib.parse import quote

    return VIDEO_MODEL_URL_TEMPLATE.format(
        install_id=quote(install_id, safe=""),
        device_id=quote(device_id, safe=""),
    )


# ─── Extract fallback_api ────────────────────────────────────────────────────

def extract_fallback_api(
    data: Dict[str, Any], video_id: str
) -> Tuple[str, Dict[str, Any]]:
    """Extract fallback_api URL from video_model response."""
    data_map = data.get("data")
    if not isinstance(data_map, dict):
        raise ValueError("Response missing data field")

    video_entry: Optional[Dict[str, Any]] = None

    # 1) direct lookup
    if video_id in data_map and isinstance(data_map[video_id], dict):
        video_entry = data_map[video_id]

    # 2) fallback scan
    if video_entry is None:
        for v in data_map.values():
            if isinstance(v, dict):
                video_entry = v
                break
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                video_entry = v[0]
                break

    if video_entry is None:
        keys = list(data_map.keys())
        raise ValueError(
            f"video entry not found (looked for {video_id}, available keys: {keys})"
        )

    video_model: Optional[Dict[str, Any]] = None
    vm = video_entry.get("video_model")
    if isinstance(vm, str):
        video_model = json.loads(vm)
    elif isinstance(vm, dict):
        video_model = vm
    else:
        raise ValueError("video_model is empty or unknown format")

    fallback_raw = video_model.get("fallback_api")
    fallback_str = parse_fallback_api(fallback_raw)
    if not fallback_str:
        raise ValueError(f"fallback_api cannot be parsed: {type(fallback_raw)} => {fallback_raw}")

    return fallback_str, video_model


def parse_fallback_api(raw: Any) -> str:
    """Parse fallback_api value in various formats."""
    if isinstance(raw, str):
        if raw.startswith("{"):
            try:
                decoded = json.loads(raw)
                if isinstance(decoded, dict) and "fallback_api" in decoded:
                    return str(decoded["fallback_api"])
            except (json.JSONDecodeError, TypeError):
                pass
        if len(raw) > 10:
            return raw
    elif isinstance(raw, list) and len(raw) > 0:
        if isinstance(raw[0], str):
            return raw[0]
    elif isinstance(raw, dict):
        if "fallback_api" in raw:
            return str(raw["fallback_api"])
    return ""


# ─── Download & Decrypt ──────────────────────────────────────────────────────

def download_and_decrypt_video(
    request,
    fallback_api: str,
    video_model: Dict[str, Any],
    device_keys: Dict[str, str],
    video_id: str,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Call fallback_api → parse video_info.data → pick best quality →
    download encrypted MP4 → CENC decrypt → serve locally.
    Returns a flattened response dict.
    """
    current_url = fallback_api
    current_device_keys = device_keys
    last_err: Optional[Exception] = None

    for attempt in range(max_retries):
        headers = {"User-Agent": USER_AGENT}

        try:
            resp = curl_request(current_url, headers, None, 30)
        except Exception as exc:
            last_err = Exception(f"fallback_api request failed: {exc}")
        else:
            try:
                data = json.loads(resp)
            except Exception as exc:
                last_err = Exception(f"fallback_api JSON parse failed: {exc}")
            else:
                video_info = data.get("video_info", {})
                if not isinstance(video_info, dict):
                    video_info = {}
                video_data = video_info.get("data", {})
                if not isinstance(video_data, dict):
                    video_data = {}

                if not video_data:
                    last_err = Exception("fallback_api response structure abnormal")
                else:
                    # decode key_seed for URL decryption
                    key_seed_b64 = video_data.get("key_seed", "")
                    key_seed_raw = b64_decode_padded(key_seed_b64)

                    # pick best quality
                    video_list = video_data.get("video_list", {})
                    if isinstance(video_list, dict):
                        best_key, best_item = select_best_quality(video_list)
                        if best_key and best_item:
                            spade_a = best_item.get("spade_a", "")
                            content_key = None
                            if spade_a:
                                try:
                                    content_key = derive_content_key(spade_a)
                                except Exception:
                                    pass

                            raw_main_url = best_item.get("main_url", "")
                            if raw_main_url:
                                real_main_url = raw_main_url
                                if key_seed_raw and len(raw_main_url) > 10:
                                    try:
                                        dec = decrypt_spade_url(raw_main_url, key_seed_raw)
                                        if dec:
                                            real_main_url = dec
                                    except Exception:
                                        pass

                                try:
                                    future = VIDEO_WORKER_POOL.submit(
                                        download_decrypt_and_serve,
                                        request,
                                        real_main_url,
                                        content_key,
                                    )
                                    local_url = future.result()
                                    if local_url:
                                        best_item["main_url"] = local_url
                                except Exception:
                                    pass

                            # only keep best quality
                            video_data["video_list"] = {best_key: best_item}

                    video_info["data"] = video_data
                    data["video_info"] = video_info
                    return build_response_payload(video_id, video_model, video_data, best_item)

        # retry with new device
        if attempt < max_retries - 1 and video_id:
            if current_device_keys:
                replace_failed_device(
                    current_device_keys.get("device_id", ""),
                    current_device_keys.get("platform", ""),
                )
            try:
                new_url, new_keys = refresh_fallback_url(video_id)
                if new_url:
                    current_url = new_url
                    current_device_keys = new_keys
            except Exception:
                pass

    raise Exception(
        f"fallback_api request failed, retried {max_retries} times: {last_err}"
    )


def download_decrypt_and_serve(
    request,
    video_url: str,
    content_key: Optional[bytes],
) -> Optional[str]:
    """Use ffmpeg to stream-copy the main video into a local MP4 file."""
    pipeline_start = time.perf_counter()
    local_url = stream_copy_video_with_ffmpeg(request, video_url, content_key)
    pipeline_seconds = time.perf_counter() - pipeline_start
    print(f"[timing] video_pipeline_seconds={pipeline_seconds:.3f}")
    return local_url


def stream_copy_video_with_ffmpeg(
    request,
    video_url: str,
    content_key: Optional[bytes],
) -> str:
    """Let ffmpeg pull the remote MP4 directly and write a local playable file."""
    stream_start = time.perf_counter()
    src_dir = get_runtime_base_dir() / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    filename = f"video_{time.time_ns()}.mp4"
    filepath = src_dir / filename

    ffmpeg_bin = get_ffmpeg_binary()
    command = [ffmpeg_bin, "-y"]
    if content_key:
        command.extend(["-decryption_key", content_key.hex()])
    command.extend([
        "-i",
        video_url,
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(filepath),
    ])

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        raise Exception(f"Failed to stream video with ffmpeg: {exc}")

    stream_seconds = time.perf_counter() - stream_start
    print(f"[timing] stream_copy_seconds={stream_seconds:.3f}")
    schedule_video_cleanup(filepath)
    current_domain = get_current_domain(request)
    return f"{current_domain}/src/{filename}"


def download_video_bytes(video_url: str) -> bytes:
    """Download the source video bytes."""
    download_start = time.perf_counter()
    try:
        resp = requests.get(
            video_url,
            headers={
                "User-Agent": "com.phoenix.read/71332",
                "Referer": "https://novel.snssdk.com/",
            },
            timeout=120,
        )
        resp.raise_for_status()
        download_seconds = time.perf_counter() - download_start
        print(f"[timing] download_seconds={download_seconds:.3f}")
        return resp.content
    except Exception as exc:
        raise Exception(f"Failed to download video: {exc}")


def decrypt_video_bytes(encrypted_data: bytes, content_key: Optional[bytes]) -> bytes:
    """Decrypt video bytes when a content key is available."""
    if content_key is None:
        print("[timing] decrypt_seconds=0.000 content_key_missing=true")
        return encrypted_data

    decrypt_start = time.perf_counter()
    try:
        decrypted_data = decrypt_mp4_cenc(encrypted_data, content_key)
        decrypt_seconds = time.perf_counter() - decrypt_start
        print(f"[timing] decrypt_seconds={decrypt_seconds:.3f}")
        return decrypted_data
    except Exception as exc:
        raise Exception(f"Failed to decrypt video: {exc}")


def save_video_bytes(request, decrypted_data: bytes) -> str:
    """Save processed video bytes beside the running script/exe."""
    save_start = time.perf_counter()
    src_dir = get_runtime_base_dir() / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    filename = f"video_{time.time_ns()}.mp4"
    filepath = src_dir / filename
    filepath.write_bytes(decrypted_data)

    current_domain = get_current_domain(request)
    save_seconds = time.perf_counter() - save_start
    print(f"[timing] save_seconds={save_seconds:.3f}")
    return f"{current_domain}/src/{filename}"


def refresh_fallback_url(video_id: str) -> Tuple[str, Dict[str, str]]:
    """Re-fetch fallback_api URL with a new device."""
    device_keys = get_device_keys()
    target_url = build_video_model_url(
        device_keys["device_id"], device_keys["install_id"]
    )

    post_payload = {
        "biz_param": {
            "detail_page_version": 0,
            "device_level": 3,
            "disable_digg_stat": False,
            "need_all_video_definition": True,
            "need_mp4_align": False,
            "use_os_player": False,
            "use_server_dns": False,
            "video_platform": 1024,
        },
        "mixed_video_id_map": {"1004": [video_id]},
    }
    signed_url, headers, post_body = sign_json_request_with_liushen(
        target_url, post_payload, device_keys
    )

    resp = curl_request(signed_url, headers, post_body, 30)
    data = json.loads(resp)

    fallback_api, _ = extract_fallback_api(data, video_id)
    return fallback_api, device_keys


# ─── CENC decryption (reference: decrypt.py) ─────────────────────────────────

def derive_content_key(spade_b64: str) -> bytes:
    """
    Derive 16-byte content_key from spade_a (Base64 string).
    Fully matches Go's deriveContentKey / Python's derive_key.
    """
    s = spade_b64.strip()
    m = 4 - len(s) % 4
    if m != 4:
        s += "=" * m

    raw = base64.b64decode(s)

    if len(raw) < 3:
        raise ValueError(f"spade_a too short: {len(raw)} bytes")

    v6 = raw[0] ^ raw[1] ^ raw[2]
    v8 = len(raw) - v6 + 47

    if v8 <= 0 or v8 > len(raw) * 2:
        raise ValueError(f"spade_a: computed v8={v8} out of range")
    if 1 + v8 > len(raw):
        v8 = len(raw) - 1
    if v8 < 33:
        raise ValueError(f"spade_a: v8={v8} too small (need >=33)")

    v13 = bytearray(raw[1 : 1 + v8])

    vA, vB = 85, 246
    for i in range(v8):
        popcnt = bin(i).count("1")
        if i & 1:
            v24 = vA
            vA = v13[i]
        else:
            v24 = vB
            vB = v13[i]
        v25 = v24 ^ v13[i]
        v26 = -21 - popcnt
        v13[i] = (v26 + v25) & 0xFF

    hex_str = bytes(v13[1:33]).decode("ascii")
    key = binascii.unhexlify(hex_str)
    return key


def decrypt_mp4_cenc(data: bytes, content_key: bytes) -> bytes:
    """
    Decrypt CENC-encrypted MP4 data.
    Fully matches Go's decryptMP4CENC / Python's decrypt_video.
    """
    data = bytearray(data)

    # locate moov
    ftyp_end = struct.unpack(">I", data[0:4])[0]
    if ftyp_end + 8 >= len(data):
        raise ValueError("invalid MP4: ftyp too large")

    moov_size = struct.unpack(">I", data[ftyp_end : ftyp_end + 4])[0]
    if ftyp_end + 8 + moov_size > len(data):
        raise ValueError("invalid MP4: moov out of range")
    moov = data[ftyp_end + 8 : ftyp_end + moov_size]

    t1_off, t1_sz = find_box(moov, "trak", 0)
    t2_off, _ = find_box(moov, "trak", t1_off + t1_sz)

    for t_off in (t1_off, t2_off):
        if t_off < 0:
            continue
        result = parse_track(moov, t_off)
        if result is None:
            continue
        sizes, offsets, cns, aux_off, aux_sz, ns = result
        if ns == 0:
            continue
        if aux_off + aux_sz > len(data):
            continue
        aux = data[aux_off : aux_off + aux_sz]

        si, ap = 0, 0
        for ci, off in enumerate(offsets):
            for k in range(cns[ci]):
                if si >= ns:
                    break
                sz = sizes[si]
                if off + sz > len(data):
                    break

                # build 16-byte IV: high 8 bytes from aux, low 8 bytes zero
                iv = bytearray(8)
                if ap + 8 <= len(aux):
                    iv[:] = aux[ap : ap + 8]
                ctr_bytes = bytes(iv) + b"\x00" * 8

                # AES-CTR decrypt this sample
                cipher = AES.new(content_key, AES.MODE_CTR, nonce=b"", initial_value=ctr_bytes)
                decrypted = cipher.decrypt(bytes(data[off : off + sz]))
                data[off : off + sz] = decrypted

                off += sz
                si += 1
                ap += 8

    # Replace fourcc: encv→hvc1, enca→mp4a
    for old, new in ((b"encv", b"hvc1"), (b"enca", b"mp4a")):
        _replace_fourcc(data, old, new)

    # Replace sinf → free
    _replace_sinf(data)

    return bytes(data)


# ─── MP4 box parsing helpers ─────────────────────────────────────────────────

def find_box(data: memoryview, fourcc: str, start: int) -> Tuple[int, int]:
    """Find a box by four-character code. Returns (offset, size) or (-1, 0)."""
    b = fourcc.encode("ascii")
    for i in range(start, len(data) - 8):
        if data[i : i + 4] == b and i >= 4:
            sz = struct.unpack(">I", data[i - 4 : i])[0]
            if 0 < sz < 5000000:
                return i - 4, sz
    return -1, 0


def get_box(data: memoryview, fourcc: str, stbl_off: int) -> Optional[memoryview]:
    """Get the body of a box (skip 8-byte header)."""
    o, sz = find_box(data, fourcc, stbl_off)
    if o >= 0:
        return data[o + 8 : o + sz]
    return None


def parse_track(
    moov: memoryview, t_off: int
) -> Optional[Tuple[List[int], List[int], List[int], int, int, int]]:
    """Parse a track's stbl boxes. Returns (sizes, offsets, cns, aux_off, aux_sz, ns)."""
    stbl_off, _ = find_box(moov, "stbl", t_off + 8)

    stsz = get_box(moov, "stsz", stbl_off)
    if stsz is None:
        return None
    ds = struct.unpack(">I", stsz[4:8])[0]   # default sample size
    ns = struct.unpack(">I", stsz[8:12])[0]  # number of samples
    sizes: List[int] = []
    if ds == 0:
        for i in range(ns):
            sizes.append(struct.unpack(">I", stsz[12 + i * 4 : 16 + i * 4])[0])
    else:
        sizes = [ds] * ns

    stco = get_box(moov, "stco", stbl_off)
    if stco is None:
        return None
    nc = struct.unpack(">I", stco[4:8])[0]  # number of chunks
    offsets = []
    for i in range(nc):
        offsets.append(struct.unpack(">I", stco[8 + i * 4 : 12 + i * 4])[0])

    stsc = get_box(moov, "stsc", stbl_off)
    if stsc is None:
        return None
    nsc = struct.unpack(">I", stsc[4:8])[0]
    entries = []
    for i in range(nsc):
        entries.append((
            struct.unpack(">I", stsc[8 + i * 12 : 12 + i * 12])[0],   # first_chunk
            struct.unpack(">I", stsc[12 + i * 12 : 16 + i * 12])[0],  # samples_per_chunk
            struct.unpack(">I", stsc[16 + i * 12 : 20 + i * 12])[0],  # sample_desc_index
        ))

    cns = [0] * nc
    for i in range(nsc):
        fc = entries[i][0]
        spc = entries[i][1]
        end = nc
        if i + 1 < nsc:
            end = entries[i + 1][0] - 1
        for c in range(fc - 1, min(end, nc)):
            cns[c] = spc

    saiz = get_box(moov, "saiz", stbl_off)
    if saiz is None:
        return None
    da = saiz[4]
    na = struct.unpack(">I", saiz[5:9])[0]

    saio = get_box(moov, "saio", stbl_off)
    if saio is None:
        return None
    aux_off = struct.unpack(">I", saio[8:12])[0]
    aux_sz = na * max(da, 8)

    return sizes, offsets, cns, aux_off, aux_sz, ns


def select_best_quality(video_list: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Pick the best quality video entry (max vheight; tie-break on bitrate)."""
    best_key = ""
    best_item: Dict[str, Any] = {}
    best_height = 0
    for k, item in video_list.items():
        if not isinstance(item, dict):
            continue
        h = int(item.get("vheight", 0))
        if h > best_height:
            best_height = h
            best_key = k
            best_item = item
        elif h == best_height and best_item:
            cur_br = int(item.get("bitrate", 0))
            best_br = int(best_item.get("bitrate", 0))
            if cur_br > best_br:
                best_key = k
                best_item = item
    return best_key, best_item


def build_response_payload(
    video_id: str,
    video_model: Dict[str, Any],
    video_data: Dict[str, Any],
    best_item: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the flattened response payload expected by the caller."""
    pic = first_non_empty(
        best_item.get("cover"),
        best_item.get("poster"),
        video_model.get("origin_cover"),
        video_model.get("cover_url"),
        video_model.get("dynamic_cover"),
        video_model.get("cover"),
        video_data.get("cover"),
        video_data.get("poster"),
    )
    url = first_non_empty(
        best_item.get("main_url"),
        best_item.get("play_addr"),
        best_item.get("backup_url_1"),
        best_item.get("url"),
    )
    height = stringify_int(first_non_empty(best_item.get("vheight"), best_item.get("height")))
    width = stringify_int(first_non_empty(best_item.get("vwidth"), best_item.get("width")))

    return {
        "vid": video_id,
        "pic": normalize_media_url(pic),
        "url": normalize_media_url(url),
        "quality": format_quality(best_item, height),
        "duration": format_duration(first_non_empty(video_model.get("duration"), video_data.get("duration"))),
        "size": format_size(first_non_empty(best_item.get("size"), best_item.get("data_size"), best_item.get("file_size"))),
        "height": height,
        "width": width,
        "create_time": format_create_time(
            first_non_empty(
                video_model.get("create_time"),
                video_model.get("publish_time"),
                video_data.get("create_time"),
                video_data.get("publish_time"),
            )
        ),
    }


def first_non_empty(*values: Any) -> str:
    for value in values:
        normalized = unwrap_media_value(value)
        if normalized:
            return normalized
    return ""


def unwrap_media_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        for item in value:
            normalized = unwrap_media_value(item)
            if normalized:
                return normalized
        return ""
    if isinstance(value, dict):
        for key in ("url", "uri", "src", "download_url"):
            normalized = unwrap_media_value(value.get(key))
            if normalized:
                return normalized
        for key in ("url_list", "urls"):
            normalized = unwrap_media_value(value.get(key))
            if normalized:
                return normalized
    return ""


def normalize_media_url(value: str) -> str:
    if value.startswith("//"):
        return f"https:{value}"
    return value


def stringify_int(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value)


def format_quality(best_item: Dict[str, Any], height: str) -> str:
    label = first_non_empty(
        best_item.get("quality"),
        best_item.get("definition"),
        best_item.get("gear_name"),
        best_item.get("quality_desc"),
    )
    if label:
        return label
    if height:
        return f"{height}p"
    return ""


def format_duration(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        total_seconds = int(float(value))
    except (TypeError, ValueError):
        return str(value)

    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}小时{minutes}分钟{seconds}秒"
    return f"{minutes}分钟{seconds}秒"


def format_size(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        size_bytes = float(value)
    except (TypeError, ValueError):
        return str(value)

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    while size_bytes >= 1024 and unit_index < len(units) - 1:
        size_bytes /= 1024
        unit_index += 1
    return f"{size_bytes:.2f}{units[unit_index]}"


def format_create_time(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(
                timezone(timedelta(hours=8))
            ).isoformat()
        try:
            numeric = float(text)
        except ValueError:
            return text
        value = numeric

    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1e12:
            timestamp /= 1000
        dt = datetime.fromtimestamp(timestamp, tz=timezone(timedelta(hours=8)))
        return dt.isoformat()
    return str(value)


# ─── Utility ─────────────────────────────────────────────────────────────────

def decrypt_spade_url(b64_str: str, key_seed: bytes) -> str:
    """
    AES-128-CBC decrypt a spade-encoded URL (used by content_endpoint).
    Matches Go's decryptSpadeURL.
    """
    if not b64_str:
        return ""

    raw = b64_decode_padded(b64_str)
    if len(raw) < 5:
        raise ValueError("Ciphertext too short")
    if raw[0] != 0xA8 or raw[2] != 0x01 or raw[3] != 0x00:
        raise ValueError("Ciphertext header format error")

    cipher_data = raw[4:]
    cipher_len = (len(cipher_data) // 16) * 16
    cipher_data = cipher_data[:cipher_len]

    constants = bytes([
        0x4D, 0xD4, 0xC2, 0xE6, 0xB8, 0x31, 0x62, 0x09, 0x0E, 0x52, 0xB3, 0xC7, 0xA6, 0x73, 0x3B, 0xA4,
        0x1C, 0xB2, 0x46, 0x2B, 0x82, 0x9A, 0xB5, 0x8A, 0x19, 0x6B, 0x39, 0xDB, 0x57, 0x17, 0x75, 0x24,
        0xF4, 0x9B, 0xAF, 0x7F, 0x08, 0xE8, 0xD6, 0x8D, 0x26, 0xA7, 0x2E, 0x37, 0xC1, 0xA9, 0x5A, 0x2F,
        0x1F, 0x05, 0xA5, 0x18, 0x92, 0xAE, 0xF2, 0x94, 0x97, 0x32, 0xB6, 0x2A, 0x38, 0xAA, 0xDD, 0x58,
    ])

    h1 = hashlib.sha512(key_seed).digest()
    h2 = hashlib.sha512(h1 + constants).digest()
    aes_key = h2[:16]
    iv = h2[16:32]

    cipher = AES.new(aes_key, AES.MODE_CBC, iv=iv)
    plaintext = cipher.decrypt(cipher_data)

    # PKCS7 unpad
    if plaintext:
        pad = plaintext[-1]
        if 1 <= pad <= 16 and pad <= len(plaintext):
            plaintext = plaintext[:-pad]

    return plaintext.rstrip(b"\x00").decode("utf-8", errors="replace")


def b64_decode_padded(s: str) -> bytes:
    """Relaxed base64 decode with auto-padding."""
    s = s.strip()
    pad = len(s) % 4
    if pad:
        s += "=" * (4 - pad)
    try:
        return base64.b64decode(s)
    except Exception:
        return base64.urlsafe_b64decode(s)


# ─── Internal helpers ────────────────────────────────────────────────────────

def _replace_fourcc(data: bytearray, old: bytes, new: bytes) -> None:
    """Replace all occurrences of old fourcc with new."""
    old_len = len(old)
    for i in range(len(data) - old_len):
        if data[i : i + old_len] == old:
            data[i : i + len(new)] = new


def _replace_sinf(data: bytearray) -> None:
    """Replace sinf boxes with free (zeroed)."""
    i = 0
    while i < len(data) - 4:
        if data[i : i + 4] == b"sinf":
            if i >= 4:
                sz = struct.unpack(">I", data[i - 4 : i])[0]
                if 0 < sz < 50000:
                    # set size to 8
                    data[i - 4 : i] = b"\x00\x00\x00\x08"
                    data[i : i + 4] = b"free"
                    end = min(i - 4 + sz, len(data))
                    for j in range(i + 4, end):
                        data[j] = 0
                    i = end
                    continue
        i += 1


# ─── Flask blueprint (optional, matches Go HTTP handler) ─────────────────────
# Usage:
#   from flask import Flask, request, jsonify
#   app = Flask(__name__)
#   app.add_url_rule("/hg", "hg", video_endpoint, methods=["GET", "POST"])

def video_endpoint():
    """Flask-compatible endpoint handler for /hg?vid=xxxx."""
    from flask import request, jsonify

    # --- KEY SYSTEM REMOVED ---

    video_id = request.args.get("vid")
    if not video_id and request.method == "POST":
        video_id = request.form.get("vid")
    if not video_id:
        return jsonify({"error": "Missing vid parameter"}), 400

    try:
        result = handle_video_request(video_id, request, max_retries=3)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ─── CLI entry point (for testing) ───────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python 1.py <video_id>")
        sys.exit(1)

    vid = sys.argv[1]
    print(f"Resolving video_id={vid} ...")
    try:
        result = handle_video_request(vid)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
