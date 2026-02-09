"""Image loader for medical case images.

Loads image URLs and captions from a CSV file (deepresearch图片链接.csv)
and provides lookup by eurorad case ID. Used by vision-capable agents
to inject case images into LLM messages.

Image loading:
1. Check local cache (data/image_cache/{case_id}/{img_id}.jpg) — instant
2. On cache miss, lazily start a browser to bypass Cloudflare and download
3. Downloaded images are cached to disk — never downloaded twice
"""
import asyncio
import base64
import csv
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any


class BrowserFetcher:
    """Lazy browser-based image fetcher that bypasses Cloudflare.

    Starts a real browser (nodriver) on first use, passes the Cloudflare
    challenge once, then downloads images by navigating to each URL and
    extracting pixel data via canvas.

    Thread-safe: uses a dedicated event loop in a background thread.
    """

    def __init__(self):
        self._browser = None
        self._tab = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = False
        self._failed = False
        self._lock = threading.Lock()

    def _start_loop(self):
        """Run the asyncio event loop in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro):
        """Run an async coroutine from sync code, using the background loop."""
        if not self._loop or not self._loop.is_running():
            return None
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=60)

    def _ensure_browser(self):
        """Start browser and pass Cloudflare challenge (once)."""
        if self._ready or self._failed:
            return

        with self._lock:
            if self._ready or self._failed:
                return

            try:
                import nodriver as uc
            except ImportError:
                print("[ImageLoader] nodriver not installed — cannot download images on-the-fly.")
                print("[ImageLoader] Install with: uv add nodriver")
                self._failed = True
                return

            # Start background event loop
            self._thread = threading.Thread(target=self._start_loop, daemon=True)
            self._thread.start()

            # Give loop time to start
            import time
            time.sleep(0.2)

            try:
                async def _init_browser():
                    browser = await uc.start(headless=False)
                    tab = await browser.get("https://www.eurorad.org")
                    # Wait for Cloudflare challenge
                    for _ in range(30):
                        await asyncio.sleep(1)
                        try:
                            title = await tab.evaluate("document.title")
                            if "moment" not in title.lower():
                                return browser, tab
                        except Exception:
                            pass
                    # Timed out but return anyway
                    return browser, tab

                print("[ImageLoader] Starting browser to bypass Cloudflare...")
                self._browser, self._tab = self._run_async(_init_browser())
                self._ready = True
                print("[ImageLoader] Browser ready — images will download on-the-fly")
            except Exception as e:
                print(f"[ImageLoader] Browser startup failed: {e}")
                self._failed = True

    def download(self, url: str, save_path: Path) -> bool:
        """Download a single image via browser and save to disk.

        Returns True on success.
        """
        self._ensure_browser()
        if not self._ready:
            return False

        try:
            async def _fetch():
                await self._tab.get(url)
                await asyncio.sleep(1)
                # Extract image via canvas
                js = """
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
                return await self._tab.evaluate(js)

            data_url = self._run_async(_fetch())
            if data_url and isinstance(data_url, str) and data_url.startswith("data:"):
                b64_data = data_url.split(",", 1)[1]
                image_bytes = base64.b64decode(b64_data)
                if len(image_bytes) < 100:
                    return False
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(image_bytes)
                return True
        except Exception as e:
            print(f"[ImageLoader] Browser download failed for {url}: {e}")
        return False

    def shutdown(self):
        """Stop the browser and event loop."""
        if self._browser and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    asyncio.coroutine(lambda: self._browser.stop())(),
                    self._loop
                ).result(timeout=5)
            except Exception:
                pass
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)


class ImageLoader:
    """Loads and indexes medical case images from CSV.

    On cache miss, lazily starts a browser to download images on-the-fly.
    Downloaded images are cached — never downloaded twice.
    """

    DEFAULT_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "image_cache"

    def __init__(self, csv_path: str | Path, cache_dir: Optional[str | Path] = None):
        self.csv_path = Path(csv_path)
        self.cache_dir = Path(cache_dir) if cache_dir else self.DEFAULT_CACHE_DIR
        self._index: Dict[str, List[Dict[str, str]]] = {}
        self._fetcher: Optional[BrowserFetcher] = None
        self._load()

    def _extract_case_id(self, plink: str) -> Optional[str]:
        """Extract case ID from eurorad URL."""
        match = re.search(r'/case/(\d+)', plink)
        return match.group(1) if match else None

    def _load(self):
        """Load CSV and build case_id -> images index."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Image CSV not found: {self.csv_path}")

        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                plink = row.get("plink", "")
                case_id = self._extract_case_id(plink)
                if not case_id:
                    continue
                img = {
                    "url": row.get("img_url", ""),
                    "caption": row.get("img_alt", ""),
                    "img_id": row.get("img_id", ""),
                    "plink": plink
                }
                if img["url"]:
                    self._index.setdefault(case_id, []).append(img)

    @property
    def case_ids(self) -> List[str]:
        return sorted(self._index.keys(), key=int)

    @property
    def total_images(self) -> int:
        return sum(len(imgs) for imgs in self._index.values())

    def get_images(self, case_id: str | int) -> List[Dict[str, str]]:
        return self._index.get(str(case_id), [])

    def has_images(self, case_id: str | int) -> bool:
        return str(case_id) in self._index

    def _get_cached_path(self, case_id: str, img_id: str) -> Optional[Path]:
        """Find cached image file."""
        case_dir = self.cache_dir / case_id
        if not case_dir.exists():
            return None
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            path = case_dir / f"{img_id}{ext}"
            if path.exists():
                return path
        return None

    def _encode_local_image(self, path: Path) -> Optional[str]:
        """Encode a local image file to a base64 data URL."""
        suffix = path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"
        }
        mime_type = mime_types.get(suffix, "image/jpeg")
        try:
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}"
        except Exception as e:
            print(f"[ImageLoader] Failed to encode {path}: {e}")
            return None

    def _download_via_browser(self, case_id: str, img: Dict[str, str]) -> Optional[Path]:
        """Download an image via browser and cache it. Returns cached path or None."""
        if not self._fetcher:
            self._fetcher = BrowserFetcher()

        url = img["url"]
        img_id = img["img_id"]

        # Determine extension from URL
        url_path = url.split("?")[0].lower()
        if url_path.endswith(".png"):
            ext = ".png"
        elif url_path.endswith(".gif"):
            ext = ".gif"
        elif url_path.endswith(".webp"):
            ext = ".webp"
        else:
            ext = ".jpg"

        save_path = self.cache_dir / case_id / f"{img_id}{ext}"

        if self._fetcher.download(url, save_path):
            print(f"[ImageLoader] Downloaded case {case_id}/{img_id} -> {save_path.name}")
            return save_path
        return None

    def _resolve_image(self, case_id: str, img: Dict[str, str]) -> Optional[str]:
        """Resolve an image to a base64 data URL.

        1. Check local cache (instant)
        2. On miss, download via browser and cache (one-time cost per image)
        """
        # 1. Cache hit
        cached = self._get_cached_path(case_id, img["img_id"])
        if cached:
            return self._encode_local_image(cached)

        # 2. Download on-the-fly, cache it, then encode
        downloaded = self._download_via_browser(case_id, img)
        if downloaded:
            return self._encode_local_image(downloaded)

        return None

    def format_as_api_content(self, case_id: str | int) -> List[Dict[str, Any]]:
        """Format case images as OpenAI API content blocks.

        Loads from cache or downloads on-the-fly via browser.
        Falls back to text-only caption if image can't be loaded.
        """
        case_id_str = str(case_id)
        images = self.get_images(case_id_str)
        if not images:
            return []

        blocks: List[Dict[str, Any]] = []
        for i, img in enumerate(images, 1):
            caption = img["caption"] or f"Image {i}"
            data_url = self._resolve_image(case_id_str, img)
            if not data_url:
                blocks.append({
                    "type": "text",
                    "text": f"[Image {i}/{len(images)}] {caption} (image not available)"
                })
                continue
            blocks.append({
                "type": "text",
                "text": f"[Image {i}/{len(images)}] {caption}"
            })
            blocks.append({
                "type": "image_url",
                "image_url": {"url": data_url}
            })

        return blocks

    def format_as_text(self, case_id: str | int) -> str:
        """Format case images as text description (for non-vision models)."""
        images = self.get_images(case_id)
        if not images:
            return ""

        lines = [f"Case {case_id} has {len(images)} image(s):"]
        for i, img in enumerate(images, 1):
            caption = img["caption"] or "No caption"
            lines.append(f"  {i}. {caption} (URL: {img['url']})")
        return "\n".join(lines)
