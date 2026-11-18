from __future__ import annotations

import contextlib
import fnmatch
import hashlib
import ipaddress
import json
import random
import re
import shlex
import socket
from html.parser import HTMLParser
from http import HTTPStatus
from io import BytesIO
from threading import RLock
from time import time
from typing import IO, TYPE_CHECKING, Annotated, Any, TypedDict, override
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from PIL import Image

from prompt_hub.online_accounts import OnlineAccountStore
from prompt_hub.studio_store import StudioError, write_json

if TYPE_CHECKING:
    from pathlib import Path

    from prompt_hub.gallery import GalleryStore


class GallerySource(TypedDict):
    label: str
    url: str
    popular: bool


SOURCES: dict[str, GallerySource] = {
    "danbooru": {"label": "Danbooru", "url": "https://danbooru.donmai.us", "popular": True},
    "safebooru": {"label": "Safebooru", "url": "https://safebooru.donmai.us", "popular": True},
    "gelbooru": {"label": "Gelbooru", "url": "https://gelbooru.com", "popular": False},
    "aitag": {"label": "AI TAG", "url": "https://aitag.win", "popular": True},
    "quicktagcloud": {
        "label": "QuickTagCloud",
        "url": "https://novelai.quicktagcloud.com",
        "popular": False,
    },
}


MAX_DONMAI_QUERY_TAGS = 2
MAX_LOCAL_FILTER_TAGS = 6
ONLINE_PAGE_SIZE = 36


def public_url(url: str) -> str:
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.port not in {None, 443}
    ):
        msg = "線上圖片地址無效"
        raise StudioError(msg)
    try:
        addresses = socket.getaddrinfo(parts.hostname, 443)
        known = any(
            parts.hostname == domain or parts.hostname.endswith("." + domain)
            for domain in (
                "donmai.us",
                "gelbooru.com",
                "aitag.win",
                "quicktagcloud.com",
                "10118899.xyz",
            )
        )
        if not addresses or any(
            not ipaddress.ip_address(a[4][0]).is_global
            and not (
                known and ipaddress.ip_address(a[4][0]) in ipaddress.ip_network("198.18.0.0/15")
            )
            for a in addresses
        ):
            msg = "線上地址需要指向公開網站"
            raise StudioError(msg)
    except socket.gaierror as error:
        msg = "網站名稱無法解析，請稍後重試"
        raise StudioError(msg) from error
    return url


class NoRedirect(HTTPRedirectHandler):
    @override
    def redirect_request(
        self, req: Request, fp: IO[bytes], code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


def request_headers(url: str) -> dict[str, str]:
    """Port the launcher's Donmai client and shared image-cache headers."""
    host = urlsplit(url).hostname or ""
    browser = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    headers = {
        "User-Agent": "NAI-Launcher/1.0" if host.endswith("donmai.us") else browser,
        "Accept": "application/json, image/avif, image/webp, image/*, */*;q=0.8",
        "Referer": "https://" + host + "/",
    }
    if host.endswith("donmai.us") and urlsplit(url).path.endswith(".json"):
        headers["Accept"] = "application/json"
    if host == "aitag.win" or host.endswith(".10118899.xyz"):
        headers["Referer"] = "https://aitag.win/"
    if host == "gelbooru.com" or host.endswith(".gelbooru.com"):
        headers.update(Referer="https://gelbooru.com/", Cookie="fringeBenefits=yup")
    return headers


def fetch_bytes(url: str, maximum: int = 24_000_000) -> bytes:
    for _ in range(4):
        public_url(url)
        try:
            request = Request(  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
                url,
                headers=request_headers(url),
            )
            with build_opener(NoRedirect()).open(request, timeout=35) as response:
                body = response.read(maximum + 1)
                if len(body) > maximum:
                    msg = "網站回應超過大小限制"
                    raise StudioError(msg)
                return body
        except HTTPError as error:
            if error.code in {301, 302, 303, 307, 308}:
                url = urljoin(url, error.headers["Location"])
                continue
            msg = f"網站回應 HTTP {error.code}，可切換來源或稍後重試"
            raise StudioError(msg) from error
        except (URLError, TimeoutError, OSError) as error:
            msg = "線上來源連線失敗，請稍後重試"
            raise StudioError(msg) from error
    msg = "網站重新導向次數過多"
    raise StudioError(msg)


def fetch_json(url: str) -> Any:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
    raw = fetch_bytes(url)
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError) as error:
        if raw.lstrip().startswith(b"<"):
            msg = "網站回傳驗證頁，請切換來源或稍後重試"
            raise StudioError(msg) from error
        msg = "網站沒有回傳可讀取的 JSON 資料"
        raise StudioError(msg) from error


def matches(item: dict[str, Any], query: str) -> bool:
    try:
        terms = shlex.split(query)
    except ValueError:
        terms = query.split()
    tags = set(item.get("tags", []))
    text = " ".join([item.get("title", ""), item.get("prompt", ""), *tags]).casefold()
    positive = []
    for raw_term in terms:
        term = raw_term
        if term.startswith(("order:", "sort:", "random:", "id:")):
            continue
        negative = term.startswith("-")
        term = term.lstrip("-~").casefold()
        if term.startswith("rating:"):
            aliases = {
                "general": "g",
                "safe": "g",
                "sensitive": "s",
                "questionable": "q",
                "explicit": "e",
            }
            rating = str(item.get("rating", "")).casefold()
            found = aliases.get(rating, rating) == aliases.get(term[7:], term[7:])
        else:
            found = (
                any(fnmatch.fnmatchcase(tag.casefold(), term) for tag in tags)
                if tags and item.get("source") in {"danbooru", "safebooru", "gelbooru"}
                else term.replace("_", " ") in text or term in text
            )
        if negative and found:
            return False
        if not negative:
            positive.append(found)
    return all(positive)


def permutation_index(position: int, length: int, seed: int) -> int:
    """Port of Launcher 4.3.1's six-round Feistel with cycle walking."""
    if length <= 1:
        return 0
    bits = 1
    while 1 << (bits * 2) < length:
        bits += 1
    mask = (1 << bits) - 1
    value = position
    while True:
        left, right = value >> bits, value & mask
        for round_index in range(6):
            mixed = (right ^ seed ^ (round_index * 0x9E3779B9)) & 0xFFFFFFFF
            mixed = ((mixed ^ (mixed >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
            mixed = ((mixed ^ (mixed >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
            left, right = right, left ^ ((mixed ^ (mixed >> 16)) & mask)
        value = (left << bits) | right
        if value < length:
            return value


class GelHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.posts: dict[str, dict[str, Any]] = {}
        self.current = ""
        self.image = ""
        self.tags = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "a":
            match = re.search(r"[?&]id=(\d+)", a.get("href", "") or "")
            self.current = match.group(1) if match and "s=view" in (a.get("href", "") or "") else ""
        if tag == "img":
            if a.get("id") == "image":
                self.image = a.get("src", "") or ""
                self.tags = a.get("alt", "") or ""
            if self.current:
                self.posts[self.current] = {
                    "id": self.current,
                    "preview_url": a.get("src", ""),
                    "tags": a.get("alt", ""),
                }


class OnlineGallery:
    def __init__(self, root: Path, gallery: GalleryStore) -> None:
        self.root = root / "online-gallery"
        self.gallery = gallery
        self.lock = RLock()
        self.cache: dict[str, tuple[float, Any]] = {}
        self.items: dict[str, dict[str, Any]] = {}
        self.fallback_urls: set[str] = set()
        self.native_random = True
        self.accounts = OnlineAccountStore(root)

    def cached(self, url: str, ttl: int = 300) -> Any:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
        cached = self.cache.get(url)
        if cached and time() - cached[0] < ttl:
            return cached[1]
        try:
            value = fetch_json(url)
            self.fallback_urls.discard(url)
        except StudioError as error:
            failure = error.__cause__
            parts = urlsplit(url)
            if (
                parts.hostname != "safebooru.donmai.us"
                or not isinstance(failure, HTTPError)
                or failure.code != HTTPStatus.FORBIDDEN
            ):
                raise
            # Safebooru is the general-rating view of the same Donmai database.
            # Keep its rating restriction when its hostname rejects the client.
            query = parse_qs(parts.query)
            if parts.path == "/posts.json":
                tags = query.get("tags", [""])[0].split()
                query["tags"] = [
                    " ".join(
                        [tag for tag in tags if not tag.lstrip("-~").startswith("rating:")]
                        + ["rating:g"]
                    )
                ]
            alternate = urlunsplit(
                ("https", "danbooru.donmai.us", parts.path, urlencode(query, doseq=True), "")
            )
            value = fetch_json(alternate)
            self.fallback_urls.add(url)
            if (
                parts.path.startswith("/posts/")
                and isinstance(value, dict)
                and value.get("rating") != "g"
            ):
                msg = "這張圖片不在 Safebooru 的一般分級範圍"
                raise StudioError(msg) from error
        self.cache[url] = (time(), value)
        return value

    def favorites(self) -> list[dict[str, Any]]:
        path = self.root / "favorites.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []

    def remember(self, item: dict[str, Any]) -> dict[str, Any]:
        self.items[item["key"]] = item
        return item

    def media(self, url: str) -> tuple[Path, str]:
        host = urlsplit(url).hostname or ""
        if not any(
            host == domain or host.endswith("." + domain)
            for domain in (
                "donmai.us",
                "gelbooru.com",
                "aitag.win",
                "quicktagcloud.com",
                "10118899.xyz",
            )
        ):
            msg = "圖片不屬於已接入的畫廊來源"
            raise StudioError(msg)
        public_url(url)
        digest = hashlib.sha256(url.encode()).hexdigest()
        target = self.root / "media-cache" / digest
        if not target.is_file() or time() - target.stat().st_mtime > 7 * 86400:
            raw = fetch_bytes(url, 50_000_000)
            try:
                with Image.open(BytesIO(raw)) as image:
                    image.verify()
            except (ValueError, OSError) as error:
                msg = "來源沒有回傳可讀取的圖片"
                raise StudioError(msg) from error
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(digest + "." + uuid4().hex + ".tmp")
            try:
                temporary.write_bytes(raw)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            with self.lock:
                files = [
                    path
                    for path in target.parent.iterdir()
                    if re.fullmatch(r"[0-9a-f]{64}", path.name)
                ]
                for old in sorted(files, key=lambda path: path.stat().st_mtime)[
                    : max(0, len(files) - 1000)
                ]:
                    with contextlib.suppress(OSError):
                        old.unlink(missing_ok=True)
        with Image.open(target) as image:
            media_type = Image.MIME.get(image.format, "application/octet-stream")
        return target, media_type

    def normalize_booru(self, source: str, raw: dict[str, Any]) -> dict[str, Any]:
        base = SOURCES[source]["url"]
        identifier = str(raw["id"])
        tags = str(raw.get("tag_string") or raw.get("tags") or "").split()
        original = str(raw.get("file_url") or "")
        thumbnail = str(
            raw.get("preview_file_url")
            or raw.get("preview_url")
            or raw.get("sample_url")
            or original
        )
        return self.remember(
            {
                "key": source + ":" + identifier,
                "source": source,
                "id": identifier,
                "title": " ".join(tags[:7]) or identifier,
                "prompt": ", ".join(tags),
                "tags": tags,
                "negative": "",
                "rating": raw.get("rating", ""),
                "score": raw.get("score", 0),
                "original_url": urljoin(base, original) if original else "",
                "thumbnail_url": urljoin(base, thumbnail) if thumbnail else "",
                "source_url": base
                + ("/index.php?page=post&s=view&id=" if source == "gelbooru" else "/posts/")
                + identifier,
                "metadata": raw,
            }
        )

    def donmai_query_plan(self, source: str, query: str) -> tuple[str, bool]:
        terms = query.split()
        meta = [
            term
            for term in terms
            if ":" in term
            and term.split(":", 1)[0].lstrip("-")
            in {
                "rating",
                "id",
                "order",
                "date",
                "score",
                "width",
                "height",
                "source",
                "status",
                "filetype",
                "random",
            }
        ]
        ordinary = [term for term in terms if term not in meta]
        if len(ordinary) > MAX_LOCAL_FILTER_TAGS:
            msg = "每次最多查詢六個標籤"
            raise StudioError(msg)
        if len(ordinary) <= MAX_DONMAI_QUERY_TAGS:
            return query, False
        names = [term.lstrip("-") for term in ordinary if "*" not in term]
        counts = {}
        try:
            records = self.cached(
                SOURCES[source]["url"]
                + "/tags.json?"
                + urlencode({"search[name_space]": " ".join(names), "limit": 100})
            )
            counts = {record["name"]: int(record.get("post_count", 0)) for record in records}
        except StudioError:
            pass
        ordered = sorted(
            ordinary,
            key=lambda term: (term.startswith("-"), counts.get(term.lstrip("-"), 2**62), term),
        )
        return " ".join([*ordered[:2], *meta]), True

    def query(  # noqa: C901, PLR0911, PLR0912, PLR0913, PLR0915, PLR0917 - protocol validation and dispatch stay together
        self,
        source: str,
        query: str,
        feed: str,
        page: int,
        seed: int,
        period: str = "day",
        date: str = "",
        codex: str = "",
        username: str = "",
    ) -> dict[str, Any]:
        if source not in SOURCES or feed not in {
            "search",
            "popular",
            "random",
            "favorites",
            "remote_favorites",
        }:
            msg = "線上畫廊來源或模式無效"
            raise StudioError(msg)
        if feed == "remote_favorites":
            if source not in {"danbooru", "safebooru"}:
                message = "此來源不支援遠端收藏"
                raise StudioError(message)
            rows = self.accounts.favorites(username, page, general_only=source == "safebooru")
            return {
                "items": [self.normalize_booru(source, row) for row in rows],
                "has_more": len(rows) >= ONLINE_PAGE_SIZE,
            }
        if feed == "popular" and not SOURCES[source]["popular"]:
            msg = "這個來源沒有熱門榜單"
            raise StudioError(msg)
        if feed == "favorites":
            items = [i for i in self.favorites() if i["source"] == source and matches(i, query)]
            return {
                "items": items[(page - 1) * 36 : page * 36],
                "has_more": page * 36 < len(items),
                "total": len(items),
            }
        if source == "quicktagcloud":
            return self.quicktag(query, feed, page, seed, codex)
        if source == "aitag":
            return self.aitag(query, feed, page, seed, period)
        base = SOURCES[source]["url"]
        if source == "gelbooru":
            tags = query + (" sort:random" if feed == "random" else "")
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "limit": 36,
                "pid": page - 1,
                "tags": tags,
            }
            try:
                data = self.cached(
                    base + "/index.php?" + urlencode(params), 10 if feed == "random" else 300
                )
                rows = data.get("post", []) if isinstance(data, dict) else data
            except StudioError:
                parser = GelHTML()
                parser.feed(
                    fetch_bytes(
                        base
                        + "/index.php?"
                        + urlencode(
                            {"page": "post", "s": "list", "tags": tags, "pid": (page - 1) * 42}
                        )
                    ).decode("utf-8", errors="replace")
                )
                rows = list(parser.posts.values())
            items = [self.normalize_booru(source, r) for r in rows]
            return {"items": items, "has_more": len(items) >= ONLINE_PAGE_SIZE}
        path = "/explore/posts/popular.json" if feed == "popular" else "/posts.json"
        server_query, local_filter = self.donmai_query_plan(source, query)
        params = {"tags": server_query, "limit": 36, "page": page}
        if feed == "popular":
            params.update(scale=period if period in {"day", "week", "month"} else "day")
            if date:
                params["date"] = date
        # Danbooru's native random matches upstream's simple-query route.
        if feed == "random" and not local_filter:
            params["tags"] = server_query + f" random:{seed}"
            params.pop("page", None)
        elif feed == "random":
            latest = self.cached(
                base + "/posts.json?" + urlencode({"tags": server_query, "limit": 1})
            )
            earliest = self.cached(
                base + "/posts.json?" + urlencode({"tags": server_query, "limit": 1, "page": "a0"})
            )
            if not latest or not earliest:
                return {"items": [], "has_more": False}
            low, high = sorted([int(latest[0]["id"]), int(earliest[0]["id"])])
            generator = random.Random(seed)  # noqa: S311 - seeded visual sampling, never used for credentials
            params["page"] = ("a" if generator.getrandbits(1) else "b") + str(
                generator.randint(low, high)
            )
        request_url = base + path + "?" + urlencode(params)
        try:
            rows = self.cached(request_url, 10 if feed == "random" else 300)
        except StudioError as error:
            if feed != "random" or source != "safebooru" or "422" not in str(error):
                raise
            # Safebooru deployments without native random: sample an ID boundary.
            latest = self.cached(base + "/posts.json?limit=1")
            maximum = int(latest[0]["id"]) if latest else 1
            boundary = random.Random(seed).randint(1, maximum)  # noqa: S311 - seeded visual sampling, never used for credentials
            params = {"tags": server_query, "page": "a" + str(boundary), "limit": 36}
            request_url = base + "/posts.json?" + urlencode(params)
            rows = self.cached(request_url, 10)
        items = [self.normalize_booru(source, row) for row in rows]
        if source == "safebooru":
            items = [item for item in items if item["rating"] == "g"]
        # The popular endpoint ignores tags, so apply its filters locally.
        if local_filter or feed == "popular":
            ordinary_query = " ".join(
                term
                for term in query.split()
                if ":" not in term or term.lstrip("-~").startswith("rating:")
            )
            items = [item for item in items if matches(item, ordinary_query)]
        result = {"items": items, "has_more": len(rows) >= ONLINE_PAGE_SIZE and feed != "random"}
        if request_url in self.fallback_urls:
            result["notice"] = "Safebooru 目前透過 Danbooru 同庫讀取一般級圖片。"
        return result

    def aitag(self, query: str, feed: str, page: int, seed: int, period: str) -> dict[str, Any]:
        base = SOURCES["aitag"]["url"]
        self.cached(base + "/api/config")
        path = "/api/ai_works_search" if feed != "popular" else "/api/rank/monthly/real"
        params: dict[str, Any] = {
            "q": query,
            "page": page,
            "page_size": 60,
            "sort": "new",
            "prompt": "",
            "time_range": "all",
        }
        if feed == "popular" and re.fullmatch(r"\d{4}-\d{2}", period):
            path = "/api/rank/monthly/fixed"
            params["month"] = period
        data = self.cached(base + path + "?" + urlencode(params))
        if feed == "random":
            total_pages = max(1, (int(data.get("total", 0)) + 59) // 60)
            params["page"] = random.Random(seed).randint(1, total_pages)  # noqa: S311 - seeded visual sampling, never used for credentials
            if params["page"] != page:
                data = self.cached(base + path + "?" + urlencode(params))
        items = []
        for raw in data.get("items", []):
            identifier = str(raw["id"])
            tags = raw.get("tags", [])
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except ValueError:
                    tags = tags.split()
            items.append(
                self.remember(
                    {
                        "key": "aitag:" + identifier,
                        "id": identifier,
                        "source": "aitag",
                        "title": str(raw.get("title") or identifier),
                        "prompt": "",
                        "negative": "",
                        "tags": tags,
                        "thumbnail_url": "",
                        "original_url": "",
                        "source_url": base + "/i/" + identifier,
                        "metadata": raw,
                        "pending": True,
                    }
                )
            )
        if feed == "random":
            random.Random(seed).shuffle(items)  # noqa: S311 - seeded visual sampling, never used for credentials
        return {
            "items": items,
            "has_more": page * 60 < int(data.get("total", 0)) and feed != "random",
            "total": data.get("total"),
        }

    def quick_catalog(self) -> tuple[str, dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        config = self.cached("https://novelai.quicktagcloud.com/data-source.json", 3600)
        base = config["baseUrl"].rstrip("/") + "/"
        pointer = self.cached(urljoin(base, config.get("pointer", "current.json")), 3600)
        manifest = self.cached(urljoin(base, pointer["manifest"]), 3600)
        release_base = urljoin(base, pointer["manifest"].rsplit("/", 1)[0] + "/")
        expected = "".join(
            name + "\0" + entry["sha256"] + "\n"
            for name, entry in sorted(manifest["files"].items())
        )
        digest = hashlib.sha256(expected.encode()).hexdigest()
        if digest != manifest["contentHash"] or digest != pointer["contentHash"]:
            msg = "QuickTagCloud 清單校驗失敗"
            raise StudioError(msg)

        def verified(name: str) -> Any:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
            cache_key = release_base + name
            if cache_key in self.cache:
                return self.cache[cache_key][1]
            raw = fetch_bytes(cache_key)
            meta = manifest["files"][name]
            if len(raw) != meta["size"] or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
                msg = "QuickTagCloud 檔案校驗失敗"
                raise StudioError(msg)
            value = json.loads(raw)
            self.cache[cache_key] = (time(), value)
            return value

        return release_base, manifest, verified("codexes.json"), verified("media.json")

    def quicktag(self, query: str, feed: str, page: int, seed: int, codex: str) -> dict[str, Any]:  # noqa: C901 - protocol validation and dispatch stay together
        base, manifest, catalogs, media = self.quick_catalog()
        catalog = next((c for c in catalogs if c["id"] == codex), catalogs[0] if catalogs else None)
        if not catalog:
            return {"items": [], "has_more": False, "catalogs": []}
        name = catalog.get("fallbackDataUrl") or f"{catalog['id']}.json"
        data_url = catalog.get("dataUrl") or urljoin(base, name)
        fallback = False
        try:
            data = self.cached(data_url, 3600)
        except StudioError:
            if not catalog.get("dataUrl") or name not in manifest["files"]:
                raise
            data_url = urljoin(base, name)
            data = self.cached(data_url, 3600)
            fallback = True
            catalog = {**catalog, "dataUrl": "", "assetPathMode": "codex", "assetBaseUrl": ""}
        if (fallback or not catalog.get("dataUrl")) and name in manifest["files"]:
            # Validate the canonical bytes, not reserialized JSON.
            checked = self.cache.get(data_url + "#verified")
            if not checked:
                raw_file = fetch_bytes(data_url)
                meta = manifest["files"][name]
                if (
                    len(raw_file) != meta["size"]
                    or hashlib.sha256(raw_file).hexdigest() != meta["sha256"]
                ):
                    msg = "QuickTagCloud 詞典校驗失敗"
                    raise StudioError(msg)
                data = json.loads(raw_file)
                self.cache[data_url + "#verified"] = (time(), True)
        items = []
        for index, raw in enumerate(data.get("entries", [])):
            if not isinstance(raw, dict):
                continue
            identifier = str(raw.get("id", index))
            images = raw.get("images", [])
            image = raw.get("image", "") or (
                images[0].get("path", "")
                if images and isinstance(images[0], dict)
                else images[0]
                if images
                else ""
            )

            def asset_url(
                path: str, *, original: bool = False, record: dict[str, Any] = raw
            ) -> str:
                if not path:
                    return ""
                if path.startswith("https://"):
                    return path
                mode = (
                    catalog.get("assetPathMode")
                    or data.get("assetPathMode")
                    or ("relative" if catalog.get("dataUrl") else "codex")
                )
                if mode == "relative":
                    root = data.get("assetBaseUrl") or catalog.get("assetBaseUrl") or ""
                else:
                    root = media.get("baseUrl", "")
                    path = "/".join(
                        [
                            media.get(
                                "originalPrefix" if original else "imagePrefix",
                                "originals" if original else "images",
                            ),
                            record.get("assetCodexId") or catalog["id"],
                            path,
                        ]
                    )
                url = root.rstrip("/") + "/" + "/".join(quote(p) for p in path.split("/"))
                return url + (
                    "?v=" + quote(str(record["assetRev"])) if record.get("assetRev") else ""
                )

            prompt = str(
                raw.get("prompt")
                or raw.get("value")
                or raw.get("tag")
                or raw.get("tags")
                or raw.get("name")
                or ""
            )
            if isinstance(raw.get("tags"), list) and not raw.get("prompt"):
                prompt = ", ".join(str(tag) for tag in raw["tags"])
            item = {
                "key": "quicktagcloud:" + catalog["id"] + ":" + identifier,
                "id": catalog["id"] + ":" + identifier,
                "source": "quicktagcloud",
                "title": str(raw.get("name") or raw.get("title") or prompt or identifier),
                "prompt": prompt,
                "negative": str(raw.get("negative", "")),
                "rating": raw.get("rating", ""),
                "tags": raw.get("tags", [])
                if isinstance(raw.get("tags", []), list)
                else str(raw.get("tags", "")).split(","),
                "thumbnail_url": asset_url(str(image)),
                "original_url": asset_url(str(raw["original"]), original=True)
                if raw.get("original")
                else asset_url(str(image)),
                "source_url": SOURCES["quicktagcloud"]["url"],
                "metadata": {
                    **raw,
                    "codexTitle": catalog.get("title", ""),
                    "categoryPath": raw.get("path", []),
                },
            }
            item["media"] = [
                {
                    "url": asset_url(str(shot.get("original")), original=True)
                    if isinstance(shot, dict) and shot.get("original")
                    else asset_url(str(shot.get("path", "")))
                    if isinstance(shot, dict)
                    else asset_url(str(shot)),
                    "prompt": str(shot.get("rawTag") or prompt)
                    if isinstance(shot, dict)
                    else prompt,
                }
                for shot in images
            ]
            if matches(item, query):
                items.append(self.remember(item))
        page_items = (
            [
                items[permutation_index(i, len(items), seed)]
                for i in range((page - 1) * 36, min(page * 36, len(items)))
            ]
            if feed == "random"
            else items[(page - 1) * 36 : page * 36]
        )
        return {
            "items": page_items,
            "has_more": page * 36 < len(items),
            "total": len(items),
            "catalogs": [{"id": c["id"], "title": c["title"]} for c in catalogs],
            "codex": catalog["id"],
        }

    def detail(self, source: str, identifier: str) -> dict[str, Any]:  # noqa: C901, PLR0912 - protocol validation and dispatch stay together
        if source not in SOURCES:
            msg = "來源不存在"
            raise StudioError(msg)
        key = source + ":" + identifier
        if source in {"danbooru", "safebooru"}:
            if not identifier.isdigit():
                msg = "作品編號無效"
                raise StudioError(msg)
            return self.normalize_booru(
                source, self.cached(SOURCES[source]["url"] + "/posts/" + identifier + ".json")
            )
        item = self.items.get(key) or next((i for i in self.favorites() if i["key"] == key), None)
        if source == "aitag":
            if not identifier.isdigit():
                msg = "作品編號無效"
                raise StudioError(msg)
            config = self.cached(SOURCES[source]["url"] + "/api/config")
            data = self.cached(SOURCES[source]["url"] + "/api/work/" + identifier)
            work = data.get("work", {})
            media = []
            for image in data.get("images", []):
                url = (
                    str(config.get("asset_base_url", "")).rstrip("/")
                    + "/"
                    + "/".join(
                        quote(str(image.get(k, "")))
                        for k in ("image_type", "author_id", "file_name")
                    )
                    + ".webp"
                )
                ai_json = image.get("ai_json", {})
                if isinstance(ai_json, str):
                    try:
                        ai_json = json.loads(ai_json)
                    except ValueError:
                        ai_json = {}
                generation = ai_json.get("Comment", ai_json) if isinstance(ai_json, dict) else {}
                if isinstance(generation, str):
                    try:
                        generation = json.loads(generation)
                    except ValueError:
                        generation = {}
                if not isinstance(generation, dict):
                    generation = {}
                positive = generation.get("prompt", "")
                if not isinstance(positive, str):
                    positive = ""
                positive = positive or image.get("prompt_text", "")
                media.append(
                    {
                        "url": url,
                        "prompt": positive if isinstance(positive, str) else "",
                        "negative": generation.get("uc", ""),
                        "metadata": image,
                    }
                )
            item = {
                **(item or {}),
                "key": key,
                "source": source,
                "id": identifier,
                "title": str(work.get("title") or identifier),
                "source_url": SOURCES[source]["url"] + "/i/" + identifier,
                "media": media,
                "prompt": str(media[0].get("prompt", "")) if media else "",
                "negative": "",
                "original_url": media[0]["url"] if media else "",
                "thumbnail_url": media[0]["url"] if media else "",
                "metadata": data,
                "pending": False,
            }
        elif source == "gelbooru" and item and not item.get("original_url"):
            parser = GelHTML()
            parser.feed(fetch_bytes(item["source_url"]).decode("utf-8", errors="replace"))
            item.update(original_url=parser.image, prompt=parser.tags.replace(" ", ", "))
        if item is None:
            msg = "請重新搜尋後開啟這個條目"
            raise StudioError(msg)
        return self.remember(item)


def create_online_gallery_router(store: OnlineGallery) -> APIRouter:  # noqa: C901 - FastAPI route registration aggregates nested handlers
    router = APIRouter(prefix="/api/online-gallery")

    @router.get("/account")
    def account() -> dict[str, object]:
        return store.accounts.public()

    @router.put("/account")
    def save_account(values: dict[str, str]) -> dict[str, object]:
        return store.accounts.save(values)

    @router.delete("/account")
    def clear_account() -> dict[str, object]:
        return store.accounts.clear()

    @router.get("/remote-favorite/{post_id}")
    def remote_favorite(post_id: str) -> dict[str, bool]:
        return {"favorite": store.accounts.favorite(post_id)}

    @router.put("/remote-favorite/{post_id}")
    def save_remote_favorite(post_id: str, values: dict[str, bool]) -> dict[str, bool]:
        if not isinstance(values.get("favorite"), bool):
            message = "請指定遠端收藏狀態"
            raise StudioError(message)
        return {"favorite": store.accounts.favorite(post_id, selected=values["favorite"])}

    @router.get("/sources")
    def sources() -> list[dict[str, Any]]:
        return [{"id": key, **value} for key, value in SOURCES.items()]

    @router.get("/media")
    def media(
        url: Annotated[str, Query(max_length=4000)], *, download: bool = False
    ) -> FileResponse:
        path, media_type = store.media(url)
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }.get(media_type, ".img")
        return FileResponse(
            path,
            media_type=media_type,
            filename="gallery-" + path.name[:12] + suffix if download else None,
            headers={
                "Cache-Control": "private, max-age=86400",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/search")
    def search(  # noqa: PLR0913, PLR0917 - matches the existing workflow or route contract
        source: str = "danbooru",
        q: Annotated[str, Query(max_length=1000)] = "",
        feed: str = "search",
        page: Annotated[int, Query(ge=1, le=100000)] = 1,
        seed: int = 1,
        period: str = "day",
        date: str = "",
        codex: str = "",
        username: str = "",
    ) -> dict[str, Any]:
        result = store.query(source, q, feed, page, seed, period, date, codex, username)
        favorites = {item["key"] for item in store.favorites()}
        result["items"] = [
            {**item, "favorite": item["key"] in favorites} for item in result["items"]
        ]
        return result

    @router.get("/detail/{source}/{identifier:path}")
    def detail(source: str, identifier: str) -> dict[str, Any]:
        return store.detail(source, identifier)

    @router.put("/favorite")
    def favorite(values: dict[str, Any]) -> dict[str, Any]:
        item = store.detail(str(values.get("source", "")), str(values.get("id", "")))
        with store.lock:
            favorites = [i for i in store.favorites() if i["key"] != item["key"]]
            if values.get("favorite", True):
                favorites.append(item)
            write_json(store.root / "favorites.json", favorites)
        return {"favorite": bool(values.get("favorite", True))}

    @router.post("/save")
    def save(values: dict[str, Any]) -> dict[str, Any]:
        item = store.detail(str(values.get("source", "")), str(values.get("id", "")))
        media_index = values.get("media_index", 0)
        if not isinstance(media_index, int) or media_index < 0:
            msg = "圖片序號無效"
            raise StudioError(msg)
        if item.get("media"):
            if media_index >= len(item["media"]):
                msg = "圖片序號無效"
                raise StudioError(msg)
            media = item["media"][media_index]
            item = {**item, "original_url": media["url"], "prompt": media.get("prompt", "")}
        if not item.get("original_url"):
            msg = "這個條目沒有可下載的原圖"
            raise StudioError(msg)
        raw = fetch_bytes(item["original_url"], 50_000_000)
        asset = store.gallery.import_bytes(
            raw, filename=item["id"].replace(":", "-") + f"-{media_index}.png", kind="reference"
        )
        return store.gallery.update_asset(
            asset["asset_id"],
            {
                "title": item["title"][:300],
                "source_url": item["source_url"],
                "tags": item.get("tags", []),
                "note": item.get("prompt", "")[:6000],
                "albums": [SOURCES[item["source"]]["label"]],
            },
        )

    return router
