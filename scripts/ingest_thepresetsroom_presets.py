from __future__ import annotations

import argparse
import html
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.preset_analysis import (  # noqa: E402
    PresetAnalysisError,
    ingest_preset_archive_bytes,
    load_preset_style_profiles,
    save_default_preset_source_registry,
)
from app.services.preset_style_index import save_preset_style_index  # noqa: E402


BASE_URL = "https://thepresetsroom.com/free-lightroom-presets/"
DOWNLOAD_URL = "https://thepresetsroom.com/download/"
USER_AGENT = "TonePilotLocal/0.1 public-lightroom-preset-analysis"


@dataclass(frozen=True)
class PresetPage:
    url: str
    title: str
    category: str
    order: int


def fetch(url: str, *, data: bytes | None = None, referer: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def absolute_url(url: str) -> str:
    return urllib.parse.urljoin(BASE_URL, html.unescape(url))


def extract_links(page: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r'''href=["']([^"']+)''', page):
        url = absolute_url(match.group(1)).split("#")[0]
        if url.startswith("https://thepresetsroom.com/free-lightroom-presets/") and url not in seen:
            seen.add(url)
            links.append(url)
    return links


def category_slug(url: str) -> str:
    parts = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
    try:
        index = parts.index("free-lightroom-presets")
    except ValueError:
        return "unknown"
    if len(parts) > index + 1:
        return parts[index + 1]
    return "unknown"


def is_category_url(url: str) -> bool:
    parts = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
    return len(parts) == 2 and parts[0] == "free-lightroom-presets"


def is_preset_url(url: str) -> bool:
    parts = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
    return len(parts) >= 3 and parts[0] == "free-lightroom-presets"


def clean_title(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text or "Lightroom preset"


def page_title(page: str, fallback_url: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return clean_title(match.group(1))
    title = re.search(r"<title[^>]*>(.*?)</title>", page, flags=re.DOTALL | re.IGNORECASE)
    if title:
        return clean_title(title.group(1)).split("|")[0].strip()
    return Path(urllib.parse.urlparse(fallback_url).path).stem.replace("-", " ").title()


def discover_preset_pages(limit: int) -> list[PresetPage]:
    main = fetch(BASE_URL).decode("utf-8", errors="ignore")
    main_links = extract_links(main)
    category_urls = [url for url in main_links if is_category_url(url)]
    preset_urls: list[str] = []
    seen: set[str] = set()

    for url in main_links:
        if is_preset_url(url) and url not in seen:
            seen.add(url)
            preset_urls.append(url)

    for category_url in category_urls:
        if len(preset_urls) >= limit * 2:
            break
        try:
            category_page = fetch(category_url).decode("utf-8", errors="ignore")
        except Exception:
            continue
        for url in extract_links(category_page):
            if is_preset_url(url) and url not in seen:
                seen.add(url)
                preset_urls.append(url)
        time.sleep(0.05)

    pages: list[PresetPage] = []
    for order, url in enumerate(preset_urls, start=1):
        if len(pages) >= limit * 2:
            break
        try:
            page = fetch(url).decode("utf-8", errors="ignore")
        except Exception:
            continue
        title = page_title(page, url)
        if "free preset" not in title.casefold() and "preset" not in title.casefold():
            title = f"{title} (Free Preset)"
        pages.append(PresetPage(url=url, title=title, category=category_slug(url), order=order))
        time.sleep(0.04)
    return pages


def download_zip_for_page(preset: PresetPage) -> tuple[str, bytes]:
    page = fetch(preset.url).decode("utf-8", errors="ignore")
    form = re.search(r"<form[^>]+action=\"https://thepresetsroom.com/download/\"[^>]*>(.*?)</form>", page, flags=re.DOTALL)
    if not form:
        raise PresetAnalysisError(f"No public download form found: {preset.url}")
    hidden = dict(re.findall(r"name=\"([^\"]+)\"\s+value=\"([^\"]*)\"", form.group(1)))
    if not hidden.get("archivo") or not hidden.get("id-preset"):
        raise PresetAnalysisError(f"Download form missing preset fields: {preset.url}")

    body = urllib.parse.urlencode({"archivo": hidden["archivo"], "id-preset": hidden["id-preset"]}).encode()
    download_page = fetch(DOWNLOAD_URL, data=body, referer=preset.url).decode("utf-8", errors="ignore")
    match = re.search(r"https://thepresetsroom\.b-cdn\.net/free-download/[^\"'\s<>]+?\.zip", download_page)
    if not match:
        raise PresetAnalysisError(f"No CDN ZIP link found after download form: {preset.url}")
    zip_url = html.unescape(match.group(0))
    return zip_url, fetch(zip_url, referer=DOWNLOAD_URL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze public/free ThePresetsRoom Lightroom presets.")
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--sleep", type=float, default=0.08)
    args = parser.parse_args()

    save_default_preset_source_registry()
    discovered = discover_preset_pages(args.target)
    if not discovered:
        raise RuntimeError("No ThePresetsRoom preset pages discovered")

    existing_profiles = load_preset_style_profiles()
    existing = existing_profiles.count
    seen_source_urls = {
        profile.metadata.sourceUrl
        for profile in existing_profiles.items
        if profile.metadata.sourceUrl
    }
    imported = 0
    failures: list[str] = []
    for preset in discovered:
        current_count = load_preset_style_profiles().count
        if current_count >= args.target:
            break
        if preset.url in seen_source_urls:
            continue
        remaining = args.target - current_count
        try:
            zip_url, content = download_zip_for_page(preset)
            responses = ingest_preset_archive_bytes(
                content,
                filename=Path(urllib.parse.urlparse(zip_url).path).name,
                concept=f"thepresetsroom {preset.category} {preset.title}",
                source_url=preset.url,
                download_url=zip_url,
                license_name="free public download; originals not redistributed",
                source_type="allowed_public_preset",
                downloaded_at=datetime.now(UTC).isoformat(),
                max_profiles=remaining,
                formats={".xmp"},
            )
            imported += len(responses)
            seen_source_urls.update(
                response.profile.metadata.sourceUrl
                for response in responses
                if response.profile.metadata.sourceUrl
            )
            print(f"imported={load_preset_style_profiles().count} +{len(responses)} {preset.title} <- {zip_url}")
        except Exception as exc:
            failures.append(f"{preset.url}: {exc}")
            print(f"failed {preset.url}: {exc}")
        time.sleep(args.sleep)

    index = save_preset_style_index()
    print(f"existingBefore={existing}")
    print(f"importedThisRun={imported}")
    print(f"profileCount={index['profileCount']}")
    print(f"groupCount={index['groupCount']}")
    print(f"uniqueHashCount={index['duplicates']['uniqueHashCount']}")
    if failures:
        print("failures:")
        for failure in failures[:20]:
            print(f"  {failure}")
    return 0 if index["profileCount"] >= args.target else 1


if __name__ == "__main__":
    raise SystemExit(main())
