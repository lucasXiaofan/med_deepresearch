"""Download eurorad case images to local cache.

Eurorad.org is behind Cloudflare protection, so images cannot be downloaded
by simple HTTP clients. This script opens a visible browser window, lets
Cloudflare's JS challenge complete, then downloads images automatically.

Usage:
    # Download images for specific cases
    uv run python -m agent_v2.download_images --cases 68 69 70

    # Download images for all cases in the CSV
    uv run python -m agent_v2.download_images --all

    # Download with custom cache directory
    uv run python -m agent_v2.download_images --cases 68 --cache-dir /path/to/cache

    # Check cache status
    uv run python -m agent_v2.download_images --status

Cache structure:
    data/image_cache/{case_id}/{img_id}.jpg
"""
import argparse
import asyncio
import csv
import re
import sys
import time
from pathlib import Path
from typing import Optional

# Paths
MODULE_DIR = Path(__file__).parent
PROJECT_ROOT = MODULE_DIR.parent.parent
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "image_cache"
DEFAULT_CONFIG_PATH = MODULE_DIR / "agent_config.yaml"


def get_image_csv_path() -> Path:
    """Resolve image CSV path from config."""
    from .config import load_config, resolve_image_csv_path
    config = load_config(DEFAULT_CONFIG_PATH)
    return resolve_image_csv_path(config, DEFAULT_CONFIG_PATH)


def load_image_index(csv_path: Path) -> dict:
    """Load image CSV into case_id -> list of image dicts."""
    index = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            plink = row.get("plink", "")
            match = re.search(r'/case/(\d+)', plink)
            if not match:
                continue
            case_id = match.group(1)
            img = {
                "url": row.get("img_url", ""),
                "img_id": row.get("img_id", ""),
                "caption": row.get("img_alt", ""),
            }
            if img["url"] and img["img_id"]:
                index.setdefault(case_id, []).append(img)
    return index


def check_cached(cache_dir: Path, case_id: str, img_id: str) -> bool:
    """Check if an image is already in the cache."""
    case_dir = cache_dir / case_id
    if not case_dir.exists():
        return False
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        if (case_dir / f"{img_id}{ext}").exists():
            return True
    return False


def show_status(cache_dir: Path, index: dict):
    """Show cache status."""
    total_images = sum(len(imgs) for imgs in index.values())
    cached = 0
    missing = 0
    for case_id, images in index.items():
        for img in images:
            if check_cached(cache_dir, case_id, img["img_id"]):
                cached += 1
            else:
                missing += 1

    print(f"Image cache: {cache_dir}")
    print(f"Total cases: {len(index)}")
    print(f"Total images: {total_images}")
    print(f"Cached: {cached}")
    print(f"Missing: {missing}")
    if total_images > 0:
        print(f"Coverage: {cached/total_images*100:.1f}%")


async def download_with_nodriver(case_ids: list, index: dict, cache_dir: Path):
    """Download images using nodriver (undetected Chrome).

    Opens a visible browser window. Cloudflare challenge will auto-resolve
    (may require brief user interaction on first visit).

    Strategy: open browser to pass Cloudflare, extract cookies, then use
    requests with those cookies for fast batch downloading.
    """
    try:
        import nodriver as uc
    except ImportError:
        print("Error: nodriver not installed. Run: uv add nodriver")
        sys.exit(1)

    import requests as req

    # Collect URLs to download
    downloads = []
    for case_id in case_ids:
        images = index.get(case_id, [])
        if not images:
            print(f"  No images found for case {case_id}")
            continue
        for img in images:
            if check_cached(cache_dir, case_id, img["img_id"]):
                continue
            downloads.append((case_id, img))

    if not downloads:
        print("All images already cached!")
        return

    print(f"Downloading {len(downloads)} images across {len(case_ids)} cases...")
    print("A browser window will open. Cloudflare may require brief interaction.")
    print()

    browser = await uc.start(headless=False)

    # Visit eurorad homepage first to establish session/pass challenge
    print("Visiting eurorad.org to pass Cloudflare challenge...")
    tab = await browser.get("https://www.eurorad.org")

    # Wait for challenge to resolve
    for i in range(30):
        await asyncio.sleep(1)
        try:
            title = await tab.evaluate("document.title")
            if "moment" not in title.lower():
                print(f"  Cloudflare passed! (title: {title})")
                break
        except Exception:
            pass
    else:
        print("  WARNING: Cloudflare challenge may not have resolved.")
        print("  If images fail to download, try running the script again.")

    await asyncio.sleep(2)

    # Extract cookies from browser via CDP
    print("Extracting browser cookies...")
    cookies_data = await tab.send(uc.cdp.network.get_cookies())
    session = req.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://www.eurorad.org/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    })
    for cookie in cookies_data:
        session.cookies.set(cookie.name, cookie.value, domain=cookie.domain)

    print(f"  Got {len(cookies_data)} cookies")

    # Download images by navigating the browser tab to each image URL
    # and extracting image data via CDP Network domain
    success = 0
    failed = 0
    for i, (case_id, img) in enumerate(downloads, 1):
        url = img["url"]
        img_id = img["img_id"]

        case_dir = cache_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        url_path = url.split("?")[0].lower()
        if url_path.endswith(".png"):
            ext = ".png"
        elif url_path.endswith(".gif"):
            ext = ".gif"
        elif url_path.endswith(".webp"):
            ext = ".webp"
        else:
            ext = ".jpg"

        out_path = case_dir / f"{img_id}{ext}"

        try:
            # Navigate to image URL in the browser
            await tab.get(url)
            await asyncio.sleep(1)

            # Extract image via JS: create img element, draw to canvas, get data URL
            js_code = """
            (function() {
                var img = document.querySelector('img');
                if (!img) return null;
                var canvas = document.createElement('canvas');
                canvas.width = img.naturalWidth || img.width;
                canvas.height = img.naturalHeight || img.height;
                if (canvas.width === 0 || canvas.height === 0) return null;
                var ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);
                return canvas.toDataURL('image/jpeg', 0.95);
            })()
            """
            data_url = await tab.evaluate(js_code)

            if data_url and isinstance(data_url, str) and data_url.startswith("data:"):
                import base64 as b64
                b64_data = data_url.split(",", 1)[1]
                image_bytes = b64.b64decode(b64_data)

                if len(image_bytes) < 100:
                    print(f"  [{i}/{len(downloads)}] SKIP case {case_id}/{img_id} (too small)")
                    failed += 1
                    continue

                with open(out_path, "wb") as f:
                    f.write(image_bytes)
                print(f"  [{i}/{len(downloads)}] OK case {case_id}/{img_id} ({len(image_bytes)} bytes)")
                success += 1
            else:
                print(f"  [{i}/{len(downloads)}] FAIL case {case_id}/{img_id} (no image element found)")
                failed += 1

        except Exception as e:
            print(f"  [{i}/{len(downloads)}] FAIL case {case_id}/{img_id}: {e}")
            failed += 1

        # Rate limiting
        if i % 10 == 0:
            await asyncio.sleep(1)

    print(f"\nDone! {success} downloaded, {failed} failed.")
    browser.stop()


def download_with_playwright(case_ids: list, index: dict, cache_dir: Path):
    """Download images using Playwright (visible browser).

    Fallback if nodriver is not available.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: Neither nodriver nor playwright is installed.")
        print("  Install one: uv add nodriver  OR  uv add playwright")
        sys.exit(1)

    downloads = []
    for case_id in case_ids:
        images = index.get(case_id, [])
        for img in images:
            if not check_cached(cache_dir, case_id, img["img_id"]):
                downloads.append((case_id, img))

    if not downloads:
        print("All images already cached!")
        return

    print(f"Downloading {len(downloads)} images using Playwright (visible browser)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # Visit homepage to pass Cloudflare
        print("Visiting eurorad.org to pass Cloudflare...")
        page.goto("https://www.eurorad.org", timeout=60000)
        page.wait_for_timeout(10000)
        title = page.title()
        print(f"  Title: {title}")

        if "moment" in title.lower():
            print("  Cloudflare challenge detected. Please solve it in the browser window.")
            print("  Waiting up to 60 seconds...")
            for _ in range(60):
                page.wait_for_timeout(1000)
                title = page.title()
                if "moment" not in title.lower():
                    print(f"  Challenge passed! (title: {title})")
                    break
            else:
                print("  WARNING: Challenge may not have resolved.")

        success = 0
        failed = 0
        for i, (case_id, img) in enumerate(downloads, 1):
            url = img["url"]
            img_id = img["img_id"]

            case_dir = cache_dir / case_id
            case_dir.mkdir(parents=True, exist_ok=True)

            url_path = url.split("?")[0].lower()
            ext = ".png" if url_path.endswith(".png") else ".jpg"
            out_path = case_dir / f"{img_id}{ext}"

            try:
                resp = page.goto(url, timeout=15000)
                if resp and resp.status == 200:
                    body = resp.body()
                    if len(body) > 100:
                        with open(out_path, "wb") as f:
                            f.write(body)
                        print(f"  [{i}/{len(downloads)}] OK case {case_id}/{img_id} ({len(body)} bytes)")
                        success += 1
                    else:
                        print(f"  [{i}/{len(downloads)}] SKIP case {case_id}/{img_id} (too small)")
                        failed += 1
                else:
                    status = resp.status if resp else "no response"
                    print(f"  [{i}/{len(downloads)}] FAIL case {case_id}/{img_id} (HTTP {status})")
                    failed += 1
            except Exception as e:
                print(f"  [{i}/{len(downloads)}] FAIL case {case_id}/{img_id}: {e}")
                failed += 1

            if i % 10 == 0:
                page.wait_for_timeout(1000)

        print(f"\nDone! {success} downloaded, {failed} failed.")
        browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="Download eurorad case images to local cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cases", nargs="+", help="Case IDs to download")
    parser.add_argument("--all", action="store_true", help="Download all cases")
    parser.add_argument("--status", action="store_true", help="Show cache status")
    parser.add_argument("--cache-dir", type=str, default=None, help="Cache directory")
    parser.add_argument(
        "--backend", choices=["nodriver", "playwright"], default="nodriver",
        help="Browser backend (default: nodriver)"
    )

    args = parser.parse_args()

    cache_dir = Path(args.cache_dir) if args.cache_dir else DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    csv_path = get_image_csv_path()
    index = load_image_index(csv_path)
    print(f"Loaded {sum(len(v) for v in index.values())} images across {len(index)} cases from CSV")

    if args.status:
        show_status(cache_dir, index)
        return

    if not args.cases and not args.all:
        print("Specify --cases <ids> or --all")
        parser.print_help()
        sys.exit(1)

    case_ids = list(index.keys()) if args.all else args.cases

    if args.backend == "nodriver":
        asyncio.run(download_with_nodriver(case_ids, index, cache_dir))
    else:
        download_with_playwright(case_ids, index, cache_dir)


if __name__ == "__main__":
    main()
