from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.preset_analysis import (  # noqa: E402
    PresetAnalysisError,
    ingest_preset_bytes,
    load_preset_style_profiles,
    save_default_preset_source_registry,
)
from app.services.preset_style_index import save_preset_style_index  # noqa: E402


BASE_URL = "https://editingfree.com/category/free-lightroom-presets/"
USER_AGENT = "TonePilotLocal/0.1 youtube-lightroom-preset-analysis"


@dataclass(frozen=True)
class PresetPost:
    url: str
    title: str
    order: int


def fetch(url: str) -> tuple[bytes, Message, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read(), response.headers, response.geturl()


def absolute_url(url: str) -> str:
    return urllib.parse.urljoin(BASE_URL, html.unescape(url)).split("#")[0]


def clean_title(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    text = re.sub(r"\s*-\s*EditingFree.*$", "", text, flags=re.IGNORECASE)
    return text or "YouTube Lightroom preset"


def page_title(page: str, fallback_url: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return clean_title(match.group(1))
    title = re.search(r"<title[^>]*>(.*?)</title>", page, flags=re.DOTALL | re.IGNORECASE)
    if title:
        return clean_title(title.group(1))
    return Path(urllib.parse.urlparse(fallback_url).path).stem.replace("-", " ").title()


def is_post_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc != "editingfree.com":
        return False
    path = parsed.path.strip("/")
    if not path or "/" in path:
        return False
    if path in {"feed", "xmlrpc.php"}:
        return False
    blocked_prefixes = ("category", "tag", "page", "wp-", "author")
    return not path.startswith(blocked_prefixes)


def extract_links(page: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r'''href=["']([^"']+)["']''', page):
        url = absolute_url(match.group(1))
        if url not in seen:
            seen.add(url)
            links.append(url)
    return links


def discover_posts(max_pages: int, limit: int) -> list[PresetPost]:
    posts: list[PresetPost] = []
    seen: set[str] = set()
    discovery_limit = max(limit * 3, limit + 75)
    for page_number in range(1, max_pages + 1):
        url = BASE_URL if page_number == 1 else urllib.parse.urljoin(BASE_URL, f"page/{page_number}/")
        try:
            content, _, _ = fetch(url)
        except Exception:
            continue
        page = content.decode("utf-8", errors="ignore")
        for link in extract_links(page):
            if not is_post_url(link) or link in seen:
                continue
            seen.add(link)
            posts.append(PresetPost(url=link, title=Path(urllib.parse.urlparse(link).path).stem, order=len(posts) + 1))
            if len(posts) >= discovery_limit:
                return posts
        time.sleep(0.05)
    return posts


def extract_xmp_download_url(page: str) -> str | None:
    anchors = re.finditer(
        r'''<a\b[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>''',
        page,
        flags=re.DOTALL | re.IGNORECASE,
    )
    fallback: str | None = None
    for match in anchors:
        href = html.unescape(match.group(1))
        body = html.unescape(match.group(2)).casefold()
        if "docs.google.com/uc" not in href:
            continue
        if "xmp" in body:
            return href
        fallback = fallback or href
    return fallback


def filename_from_headers(headers: Message, fallback: str) -> str:
    disposition = headers.get("Content-Disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition, flags=re.IGNORECASE)
    if match:
        filename = urllib.parse.unquote(match.group(1)).strip()
        if filename:
            return filename
    return fallback if fallback.endswith(".xmp") else f"{fallback}.xmp"


def looks_like_xmp(content: bytes) -> bool:
    sample = content[:256].lstrip()
    return sample.startswith(b"<x:xmpmeta") or b"adobe:ns:meta/" in sample


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest public/free YouTube-linked Lightroom presets from Editingfree.")
    parser.add_argument("--target-new", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args()

    save_default_preset_source_registry()
    existing_profiles = load_preset_style_profiles()
    seen_source_urls = {
        profile.metadata.sourceUrl
        for profile in existing_profiles.items
        if profile.metadata.sourceUrl
    }
    seen_hashes = {profile.metadata.sha256 for profile in existing_profiles.items}

    posts = discover_posts(args.max_pages, args.target_new)
    imported = 0
    skipped = 0
    failures: list[str] = []
    for post in posts:
        if imported >= args.target_new:
            break
        if post.url in seen_source_urls:
            skipped += 1
            continue
        try:
            post_content, _, _ = fetch(post.url)
            post_page = post_content.decode("utf-8", errors="ignore")
            title = page_title(post_page, post.url)
            download_url = extract_xmp_download_url(post_page)
            if not download_url:
                skipped += 1
                continue
            content, headers, final_url = fetch(download_url)
            if not looks_like_xmp(content):
                raise PresetAnalysisError(f"download did not return XMP: {final_url}")
            sha = hashlib.sha256(content).hexdigest()
            if sha in seen_hashes:
                skipped += 1
                continue
            filename = filename_from_headers(headers, Path(urllib.parse.urlparse(post.url).path).stem)
            response = ingest_preset_bytes(
                content,
                filename=filename,
                concept=f"editingfree-youtube {title}",
                source_url=post.url,
                download_url=download_url,
                license_name="free public download; originals not redistributed",
                source_type="allowed_public_preset",
                downloaded_at=datetime.now(UTC).isoformat(),
            )
            seen_source_urls.add(post.url)
            seen_hashes.add(sha)
            imported += 1
            print(f"imported={imported} total={load_preset_style_profiles().count} {title} <- {post.url}")
        except Exception as exc:
            failures.append(f"{post.url}: {exc}")
            print(f"failed {post.url}: {exc}")
        time.sleep(args.sleep)

    index = save_preset_style_index()
    print(f"importedThisRun={imported}")
    print(f"skipped={skipped}")
    print(f"profileCount={index['profileCount']}")
    print(f"groupCount={index['groupCount']}")
    print(f"uniqueHashCount={index['duplicates']['uniqueHashCount']}")
    if failures:
        print("failures:")
        for failure in failures[:25]:
            print(f"- {failure}")
    return 0 if imported > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
