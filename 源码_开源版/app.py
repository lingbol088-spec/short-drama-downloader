"""
短剧下载工具 · 开源版

启动：python app.py
API：
  - GET/POST /api/search
  - GET/POST /hg?vid=VIDEO_ID
"""
import importlib
import json
import os
import re
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_from_directory


APP_DIR = Path(__file__).resolve().parent
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
}
ITEMS_PER_PAGE = 50


SOURCE_ALIASES = {
    "红果短剧": "hongguo",
    "红果短剧官网": "hongguo",
    "红果漫剧": "hongguo_manju",
    "红果免费漫剧": "hongguo_manju",
    "爱奇艺短剧": "iqiyi",
    "FlexTV": "flextv",
    "熊猫短剧": "xiongmao",
    "趣看看短剧": "qukankan",
    "全网聚合": "all",
    "其他短剧平台": "all",
    "本地导入": "local",
}

# 红果短剧官网分类参数，来自公开分类页。
HONGGUO_CATEGORY_MAP = {
    "现代": "background=cate_757",
    "都市": "background=cate_1",
    "古代": "background=cate_758",
    "乡村": "background=cate_11",
    "年代": "background=cate_79",
    "架空": "background=cate_452",
    "职场": "background=cate_127",
    "民国": "background=cate_390",
    "宫廷": "background=cate_1153",
    "校园": "background=cate_4",
    "现言": "topic=cate_1021",
    "女性成长": "topic=cate_1048",
    "脑洞": "topic=cate_262",
    "奇幻": "topic=cate_1020",
    "玄幻": "topic=cate_1019",
    "古言": "topic=cate_439",
    "战神": "topic=cate_1038",
    "宫斗": "topic=cate_246",
    "仙侠": "topic=cate_1013",
    "权谋": "topic=cate_1047",
    "悬疑": "topic=cate_165",
    "喜剧": "topic=cate_303",
    "科幻": "topic=cate_1092",
    "打脸虐渣": "setting=cate_1051",
    "大女主": "setting=cate_760",
    "大男主": "setting=cate_1207",
    "马甲": "setting=cate_266",
    "重生": "setting=cate_36",
    "穿越": "setting=cate_37",
    "系统": "setting=cate_19",
    "先婚后爱": "setting=cate_265",
    "神豪": "setting=cate_20",
    "破镜重圆": "setting=cate_475",
    "豪门": "setting=cate_936",
    "甜宠": "setting=cate_96",
    "娱乐圈": "setting=cate_43",
    "赘婿": "setting=cate_1044",
    "赘婿逆袭": "setting=cate_1044",
    "神医": "setting=cate_26",
    "男频": "gender=1",
    "女频": "gender=0",
    "最新": "sort_type=2",
    "最热": "sort_type=1",
}


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


load_dotenv_file(APP_DIR / ".env")

if getattr(sys, "frozen", False):
    EXE_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", EXE_DIR / "_internal"))
else:
    RESOURCE_DIR = APP_DIR

LIUSHEN_DIR = RESOURCE_DIR / "liushen"
STATIC_DIR = RESOURCE_DIR / "static"

for path in (RESOURCE_DIR, LIUSHEN_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")

parser_module = importlib.import_module("1")
handle_video_request = parser_module.handle_video_request


# ───────────────────────── 配置 ─────────────────────────

def get_config_path() -> Path:
    return parser_module.get_runtime_base_dir() / "config.json"


def mask_value(value: str) -> str:
    value = str(value or "")
    if len(value) <= 6:
        return "*" * len(value)
    return value[:3] + "*" * (len(value) - 6) + value[-3:]


def read_local_config() -> dict:
    path = get_config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@app.route("/api/config", methods=["GET"])
def get_config():
    cfg = read_local_config()
    device_id = os.getenv("DUANJU_DEVICE_ID") or str(cfg.get("device_id", ""))
    install_id = os.getenv("DUANJU_INSTALL_ID") or str(cfg.get("install_id", ""))
    platform = os.getenv("DUANJU_PLATFORM") or str(cfg.get("platform", "android"))
    return jsonify({
        "configured": bool(device_id and install_id),
        "device_id_masked": mask_value(device_id),
        "install_id_masked": mask_value(install_id),
        "platform": platform or "android",
        "config_path": str(get_config_path()),
    })


@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.get_json(silent=True) or {}
    device_id = str(data.get("device_id", "")).strip()
    install_id = str(data.get("install_id", "")).strip()
    platform = str(data.get("platform", "android")).strip() or "android"

    if not device_id or not install_id:
        return jsonify({"error": "device_id and install_id are required"}), 400

    path = get_config_path()
    path.write_text(
        json.dumps({"device_id": device_id, "install_id": install_id, "platform": platform}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return jsonify({"ok": True, "config_path": str(path)})


# ───────────────────────── 搜索源 ─────────────────────────

def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def estimate_duration_from_episodes(episode_text: str) -> str:
    """Return a conservative series duration estimate when official duration is absent."""
    m = re.search(r"(\d+)", episode_text or "")
    if not m:
        return ""
    episodes = int(m.group(1))
    # Most short-drama episodes are about 1-2 minutes; use a neutral range.
    return f"\u7ea6 {episodes}-{episodes * 2} \u5206\u949f\uff08\u6309\u6bcf\u96c6 1-2 \u5206\u949f\u4f30\u7b97\uff09"


def public_unknown_time() -> str:
    return "\u5b98\u7f51\u672a\u516c\u5f00"


def fetch_text(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def dedupe_items(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        key = item.get("drama_id") or item.get("source_url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def matches_keywords(item: dict, keyword: str, category_filter: str) -> bool:
    keys = []
    if keyword:
        keys.extend([x.strip() for x in re.split(r"[,，\s]+", keyword) if x.strip()])
    if category_filter:
        keys.extend([x.strip() for x in re.split(r"[,，]+", category_filter) if x.strip()])
    if not keys:
        return True
    haystack = " ".join(str(item.get(k, "")) for k in ("title", "category", "author", "desc", "source"))
    return any(k in haystack for k in keys)


def apply_page(items: list[dict], page: int) -> list[dict]:
    page = max(int(page or 1), 1)
    start = (page - 1) * ITEMS_PER_PAGE
    return items[start:start + ITEMS_PER_PAGE]


def first_category_query(keyword: str, category_filter: str) -> str:
    text = f"{keyword},{category_filter}"
    for name, query in HONGGUO_CATEGORY_MAP.items():
        if name and name in text:
            return query
    return "sort_type=1"


def parse_hongguo_cards(html_text: str, base_url: str = "https://hongguoduanju.com") -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    items = []
    for a in soup.select('a[href*="/detail?series_id="]'):
        href = a.get("href") or ""
        parsed = urlparse(urljoin(base_url, href))
        series_id = (parse_qs(parsed.query).get("series_id") or [""])[0]
        if not series_id:
            continue

        texts = [clean_text(x) for x in a.stripped_strings if clean_text(x)]
        text_join = " ".join(texts)
        episode = next((x for x in texts if re.search(r"全\d+集", x)), "")

        title = ""
        title_node = a.select_one('[class*="title"]')
        if title_node:
            title = clean_text(title_node.get_text(" "))
        if not title:
            # fallback: 去掉“全xx集”和标签后，取第一段不像标签的文本
            candidates = [x for x in texts if not re.fullmatch(r"全\d+集", x)]
            title = candidates[0] if candidates else text_join[:40]

        tag_texts = []
        for node in a.select('[class*="tag-text"], [class*="tag"] span'):
            t = clean_text(node.get_text(" "))
            if t and t not in tag_texts and len(t) <= 12:
                tag_texts.append(t)
        if not tag_texts:
            # fallback: anchor 文本中除标题/集数外的短词作为标签
            tag_texts = [x for x in texts if x not in {title, episode} and 1 <= len(x) <= 12][:5]

        items.append({
            "author": "红果短剧",
            "title": title,
            "drama_id": series_id,
            "episodes": episode,
            "duration": estimate_duration_from_episodes(episode),
            "online_time": public_unknown_time(),
            "category": " / ".join(tag_texts),
            "source": "红果短剧官网",
            "source_url": urljoin(base_url, href),
            "downloadable": True,
            "desc": text_join,
            "duration_source": "estimated_from_episode_count" if episode else "not_public",
            "online_time_source": "not_public",
        })
    return dedupe_items(items)


def search_hongguo(keyword: str, page: int, category_filter: str) -> list[dict]:
    urls = []
    query = first_category_query(keyword, category_filter)
    urls.append(f"https://hongguoduanju.com/category?{query}")
    urls.append("https://hongguoduanju.com/category?sort_type=1")
    urls.append("https://hongguoduanju.com/")

    items = []
    for url in urls:
        try:
            items.extend(parse_hongguo_cards(fetch_text(url), "https://hongguoduanju.com"))
        except Exception as exc:
            print(f"[search][hongguo] failed url={url} error={exc}")
    items = dedupe_items(items)
    filtered = [x for x in items if matches_keywords(x, keyword, category_filter)]
    return apply_page(filtered or items, page)


def parse_generic_cards(html_text: str, base_url: str, source_name: str, keyword: str = "") -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    items = []
    for a in soup.find_all("a", href=True):
        title = clean_text(a.get_text(" "))
        href = urljoin(base_url, a.get("href") or "")
        if len(title) < 2:
            continue
        if keyword and keyword not in title:
            continue
        if not any(x in title for x in ["短剧", "漫剧", "剧", keyword]) and not re.search(r"\d+集", title):
            continue
        drama_id = ""
        m = re.search(r"(?:series_id|book_id|album_id|id)=([0-9A-Za-z_-]+)", href)
        if m:
            drama_id = m.group(1)
        items.append({
            "author": source_name,
            "title": title[:80],
            "drama_id": drama_id,
            "episodes": next(iter(re.findall(r"全?\d+集", title)), ""),
            "duration": "",
            "online_time": "",
            "category": source_name,
            "source": source_name,
            "source_url": href,
            "downloadable": False,
            "desc": title,
        })
    return dedupe_items(items)


def search_bing_web(query: str, source_name: str, limit: int = 30) -> list[dict]:
    """Use public Bing result pages as a fallback source for platforms without public list APIs."""
    url = "https://www.bing.com/search?q=" + quote_plus(query)
    try:
        html_text = fetch_text(url)
    except Exception as exc:
        print(f"[search][bing] failed query={query} error={exc}")
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    items = []
    for block in soup.select("li.b_algo"):
        a = block.select_one("h2 a") or block.select_one("a")
        if not a or not a.get("href"):
            continue
        title = clean_text(a.get_text(" "))
        href = a.get("href")
        desc = clean_text((block.select_one("p") or block).get_text(" "))
        drama_id = ""
        m = re.search(r"(?:series_id|book_id|album_id|id)=([0-9A-Za-z_-]+)", href)
        if m:
            drama_id = m.group(1)
        items.append({
            "author": source_name,
            "title": title,
            "drama_id": drama_id,
            "episodes": next(iter(re.findall(r"全?\d+集", title + " " + desc)), ""),
            "duration": "",
            "online_time": "",
            "category": source_name,
            "source": source_name,
            "source_url": href,
            "downloadable": bool(drama_id and "hongguoduanju.com" in href),
            "desc": desc[:180],
        })
        if len(items) >= limit:
            break
    return dedupe_items(items)


def search_yuyue_manju(keyword: str, page: int, category_filter: str) -> list[dict]:
    items = []
    # 官网是动态落地页，公开 HTML 中暂无剧目列表，先提取官网入口。
    try:
        html_text = fetch_text("https://yuyuedushu.com/")
        soup = BeautifulSoup(html_text, "html.parser")
        desc = clean_text((soup.find("meta", attrs={"name": "description"}) or {}).get("content", ""))
        items.append({
            "author": "红果漫剧",
            "title": "红果漫剧官网",
            "drama_id": "",
            "episodes": "",
            "duration": "",
            "online_time": "",
            "category": "漫剧 / 短剧平台",
            "source": "红果漫剧官网",
            "source_url": "https://yuyuedushu.com/",
            "downloadable": False,
            "desc": desc or "红果漫剧公开官网入口",
        })
    except Exception as exc:
        print(f"[search][yuyue] home failed error={exc}")

    q = f"{keyword or category_filter or '热门'} 红果漫剧 短剧 漫剧"
    items.extend(search_bing_web(q, "红果漫剧公开检索", limit=20))
    all_items = dedupe_items(items)
    filtered = [x for x in all_items if matches_keywords(x, keyword, category_filter) or not keyword]
    return apply_page(filtered or all_items, page)


def search_official_page(url: str, source_name: str, keyword: str, page: int, category_filter: str) -> list[dict]:
    items = []
    try:
        items.extend(parse_generic_cards(fetch_text(url), url, source_name, keyword=keyword))
    except Exception as exc:
        print(f"[search][page] failed url={url} error={exc}")
    if len(items) < 5:
        domain = urlparse(url).netloc
        q = f"site:{domain} {keyword or category_filter or '热门短剧'}"
        items.extend(search_bing_web(q, source_name, limit=30))
    all_items = dedupe_items(items)
    if not all_items:
        all_items = [{
            "author": source_name,
            "title": f"{source_name} \u5b98\u7f51/\u516c\u5f00\u5165\u53e3",
            "drama_id": "",
            "episodes": "",
            "duration": "",
            "online_time": "",
            "category": "\u5e73\u53f0\u5165\u53e3",
            "source": source_name,
            "source_url": url,
            "downloadable": False,
            "desc": f"\u672a\u5728\u516c\u5f00\u9875\u9762\u68c0\u7d22\u5230\u300a{keyword}\u300b\u7ed3\u679c\uff0c\u53ef\u6253\u5f00\u5b98\u7f51\u7ee7\u7eed\u641c\u7d22\u3002",
        }]
    filtered = [x for x in all_items if matches_keywords(x, keyword, category_filter) or not keyword]
    return apply_page(filtered or all_items, page)


def search_short_drama(keyword: str, page: int, source: str, category_filter: str) -> list[dict]:
    source_key = SOURCE_ALIASES.get(source, source)
    if source_key == "local":
        return []
    if source_key == "hongguo":
        return search_hongguo(keyword, page, category_filter)
    if source_key == "hongguo_manju":
        return search_yuyue_manju(keyword, page, category_filter)
    if source_key == "iqiyi":
        return search_official_page("https://www.iqiyi.com/microdrama/", "爱奇艺短剧", keyword, page, category_filter)
    if source_key == "flextv":
        return search_official_page("https://www.flextv.cc/tc", "FlexTV", keyword, page, category_filter)
    if source_key == "xiongmao":
        return search_official_page("https://www.xiongmao-player.com/", "熊猫短剧", keyword, page, category_filter)
    if source_key == "qukankan":
        return search_official_page("https://keying.contentchina.com/", "趣看看短剧", keyword, page, category_filter)

    # 全网聚合：红果官网结果 + 几个公开平台检索结果。
    items = []
    items.extend(search_hongguo(keyword, 1, category_filter))
    query = f"{keyword or category_filter or '热门'} 短剧 site:hongguoduanju.com OR site:iqiyi.com OR site:flextv.cc OR site:yuyuedushu.com"
    items.extend(search_bing_web(query, "全网公开检索", limit=40))
    return apply_page(dedupe_items(items), page)


@app.route("/api/search", methods=["GET", "POST"])
def api_search():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        keyword = str(payload.get("keyword", "")).strip()
        page = int(payload.get("page") or 1)
        source = str(payload.get("source", "红果短剧")).strip()
        category_filter = str(payload.get("category_filter", "")).strip()
    else:
        keyword = request.args.get("keyword", "").strip()
        page = int(request.args.get("page") or 1)
        source = request.args.get("source", "红果短剧").strip()
        category_filter = request.args.get("category_filter", "").strip()

    try:
        items = search_short_drama(keyword, page, source, category_filter)
        message = f"搜索完成：{source}，第 {page} 页，返回 {len(items)} 条。"
        return jsonify({"items": items, "page": page, "source": source, "message": message})
    except Exception as exc:
        return jsonify({"items": [], "page": page, "source": source, "message": f"搜索失败：{exc}"}), 500


# ───────────────────────── 页面和下载 ─────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/src/<path:filename>")
def generated_video(filename):
    src_dir = parser_module.get_runtime_base_dir() / "src"
    return send_from_directory(str(src_dir), filename)


@app.route("/hg", methods=["GET", "POST"])
def hg():
    video_id = request.args.get("vid") or (request.form.get("vid") if request.method == "POST" else None)
    if not video_id:
        return jsonify({"error": "Missing vid parameter"}), 400

    try:
        result = handle_video_request(video_id.strip(), request, max_retries=3)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _should_open_browser() -> bool:
    return os.getenv("OPEN_BROWSER", "1").strip().lower() not in {"0", "false", "no", "off"}


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("APP_PORT", "5000"))
    url = f"http://127.0.0.1:{port}"

    if _should_open_browser():
        def open_browser():
            import time
            time.sleep(1)
            webbrowser.open(url)

        threading.Thread(target=open_browser, daemon=True).start()

    print(f"短剧下载工具 开源版: {url}")
    app.run(host="127.0.0.1", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
