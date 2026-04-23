# Authored By Certified Coders © 2025
import asyncio
import contextlib
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch, Playlist

from AnnieXMedia.utils.cookie_handler import COOKIE_PATH
from AnnieXMedia.utils.database import is_on_off
from AnnieXMedia.utils.downloader import yt_dlp_download
from AnnieXMedia.utils.errors import capture_internal_err
from AnnieXMedia.utils.formatters import time_to_seconds, seconds_to_min
from AnnieXMedia.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL
from AnnieXMedia.utils.nubcoder_api import get_video_info as nubcoder_get_info, search_videos as nubcoder_search
from config import API_KEY, API_URL, VIDEO_API_URL

USE_NUBCODER_API = bool(API_KEY and API_URL)


# === Caches ===
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()
_stream_cache: Dict[str, Tuple[float, str]] = {} # Cache for stream URLs
_stream_lock = asyncio.Lock()
STREAM_TTL = 3600 # 1 hour for stream URLs


# === Constants ===
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


# === Helpers ===
def _cookiefile_path() -> Optional[str]:
    # Don't use cookies when NubCoder API is configured
    if USE_NUBCODER_API:
        return None
    path = str(COOKIE_PATH)
    try:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    except Exception:
        pass
    return None


def _cookies_args() -> List[str]:
    path = _cookiefile_path()
    return ["--cookies", path] if path else []


async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
        # Suppress error messages in stderr (like 403 Forbidden)
        return stdout, b""  # Return empty stderr to suppress errors
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return b"", b"timeout"


@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()

    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val
            _cache.pop(key, None)
        if len(_cache) > YOUTUBE_META_MAX:
            _cache.clear()

    result = []
    
    # Try NubCoder API first if available
    if USE_NUBCODER_API:
        try:
            api_results = nubcoder_search(query, max_results=1)
            if api_results and len(api_results) > 0:
                video = api_results[0]
                # Only use API result if video_id is valid
                if video.get('video_id') != 'N/A':
                    # Convert NubCoder API format to expected format
                    duration_sec = video.get('duration', 0)
                    duration_str = seconds_to_min(duration_sec) if duration_sec else None
                    
                    result = [{
                        'id': video.get('video_id', ''),
                        'title': video.get('title', ''),
                        'duration': duration_str,
                        'thumbnail': video.get('thumbnail', ''),
                        'channel': {'name': video.get('channel_name', '')},
                        'views': {'short': str(video.get('views', 0))}
                    }]
        except Exception as e:
            from AnnieXMedia.logging import LOGGER
            LOGGER(__name__).debug(f"NubCoder API search failed: {e}")
    
    # Fallback to youtubesearchpython if API failed or not available
    if not result:
        try:
            data = await VideosSearch(query, limit=1).next()
            result = data.get("result", [])
        except Exception:
            result = []

    if result:
        async with _cache_lock:
            _cache[key] = (now, result)

    return result


# === Main Class ===
class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()

        link = link.strip()

        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]

        return link.split("&")[0]

    # === URL Handling ===
    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length].split("&si")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&si")[0]
        return None

    async def _ensure_watch_url(self, maybe_query_or_url: str) -> Optional[str]:
        prepared = self._prepare_link(maybe_query_or_url)
        if prepared.startswith("http"):
            return prepared
        data = await cached_youtube_search(prepared)
        if not data:
            return None
        vid = data[0].get("id")
        return self.base_url + vid if vid else None

    # === Metadata Fetching ===
    @capture_internal_err
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        q = self._prepare_link(query)
        
        # Try NubCoder API first if available
        if USE_NUBCODER_API:
            try:
                api_info = nubcoder_get_info(q, max_results=1)
                if api_info and 'error' not in api_info and api_info.get('video_id') != 'N/A':
                    # Convert NubCoder API format to expected format
                    duration_sec = api_info.get('duration', 0)
                    duration_str = seconds_to_min(duration_sec) if duration_sec else None
                    
                    return {
                        'id': api_info.get('video_id', ''),
                        'title': api_info.get('title', ''),
                        'duration': duration_str,
                        'thumbnail': api_info.get('thumbnail', ''),
                        'link': api_info.get('youtube_link', q),
                        'channel': {'name': api_info.get('channel_name', '')}
                    }
            except Exception as e:
                from AnnieXMedia.logging import LOGGER
                LOGGER(__name__).debug(f"NubCoder API info fetch failed: {e}")
        
        # Fallback to youtubesearchpython
        if use_cache and not q.startswith("http"):
            res = await cached_youtube_search(q)
            return res[0] if res else None
        data = await VideosSearch(q, limit=1).next()
        result = data.get("result", [])
        return result[0] if result else None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode())
            return bool(info.get("is_live"))
        except json.JSONDecodeError:
            return False

    @capture_internal_err
    async def details(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], int, str, str, Optional[str]]:
        prepared_link = self._prepare_link(link, videoid)

        try:
            info = await self._fetch_video_info(prepared_link)
            if not info:
                raise ValueError("No results from youtubesearchpython (VideosSearch)")
        except Exception as search_err:
            raise ValueError("Video not found", {"cause": str(search_err)}) from search_err

        dt = info.get("duration")
        if isinstance(dt, int):
            dt = seconds_to_min(dt)
        ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0]
        
        # Try to get stream_url from info if it came from NubCoder API
        stream_url = info.get("url")

        return info.get("title", ""), dt, ds, thumb, info.get("id", ""), stream_url

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0] if info else ""

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared_link = self._prepare_link(link, videoid)

        # Try NubCoder API first if available
        if USE_NUBCODER_API:
            try:
                api_info = nubcoder_get_info(prepared_link, max_results=1)
                if api_info and 'error' not in api_info and api_info.get('video_id') != 'N/A':
                    # Convert NubCoder API format to expected format
                    duration_sec = api_info.get('duration', 0)
                    duration_str = seconds_to_min(duration_sec) if duration_sec else None
                    
                    details = {
                        "title": api_info.get('title', ''),
                        "link": api_info.get('youtube_link', prepared_link),
                        "vidid": api_info.get('video_id', ''),
                        "duration_min": duration_str,
                        "thumb": api_info.get('thumbnail', ''),
                        "stream_url": api_info.get('url'), # PRE-FETCHED
                    }
                    return details, api_info.get('video_id', '')
            except Exception as e:
                from AnnieXMedia.logging import LOGGER
                LOGGER(__name__).debug(f"NubCoder API track fetch failed: {e}")
        
        # Fallback to youtubesearchpython
        try:
            info = await self._fetch_video_info(prepared_link)
            if not info:
                raise ValueError(
                    f"No results from youtubesearchpython (VideosSearch) "
                    f"for query/URL: '{prepared_link}'"
                )
        except Exception as search_err:
            stdout, stderr = await _exec_proc(
                "yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", prepared_link
            )

            def _both_failed(details: str) -> ValueError:
                return ValueError(
                    f"Both methods failed for '{prepared_link}':\n"
                    f"  1. youtubesearchpython error: {search_err}\n"
                    f"{details}"
                )

            if not stdout:
                stderr_msg = stderr.decode().strip() if stderr else "Empty response"
                raise _both_failed(f"  2. yt-dlp error: {stderr_msg}")

            try:
                info = json.loads(stdout.decode())
            except json.JSONDecodeError as json_err:
                raw = stdout.decode()[:400]
                raise _both_failed(
                    f"  2. yt-dlp JSON error: {json_err}\n"
                    f"     Raw: {raw}..."
                ) from json_err

        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0]

        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", prepared_link),
            "vidid": info.get("id", ""),
            "duration_min": (
                info.get("duration")
                if isinstance(info.get("duration"), str)
                else None
            ),
            "thumb": thumb,
        }
        return details, info.get("id", "")

    # === Media & Formats ===
    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        
        # Try NubCoder API first if available
        if USE_NUBCODER_API:
            try:
                api_info = nubcoder_get_info(link, max_results=1)
                if api_info and 'error' not in api_info and api_info.get('video_id') != 'N/A':
                    stream_url = api_info.get('url') or api_info.get('stream_url', '')
                    if stream_url and stream_url != 'N/A':
                        return (1, stream_url)
            except Exception as e:
                from AnnieXMedia.logging import LOGGER
                LOGGER(__name__).debug(f"NubCoder API video fetch failed: {e}")
        
        # Fallback to yt-dlp
        stdout, stderr = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            link,
        )
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    @capture_internal_err
    async def playlist(
        self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None
    ) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = self._prepare_link(link).split("&")[0]

        try:
            plist = await Playlist.get(link)
            items = [video.get("id") for video in plist.get("videos", [])[:limit] if video.get("id")]
            if items:
                return items
        except Exception:
            pass

        stdout, _ = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-i",
            "--get-id",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            "--skip-download",
            link,
        )
        items = stdout.decode().strip().split("\n") if stdout else []
        return [i for i in items if i]

    @capture_internal_err
    async def formats(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        key = f"f:{link}"
        now = time.time()

        async with _formats_lock:
            cached = _formats_cache.get(key)
            if cached and now - cached[0] < YOUTUBE_META_TTL:
                return cached[1], cached[2]

        opts = {"quiet": True}
        if cf := _cookiefile_path():
            opts["cookiefile"] = cf

        out: List[Dict] = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                for fmt in info.get("formats", []):
                    if "dash" in str(fmt.get("format", "")).lower():
                        continue
                    if not any(k in fmt for k in ("filesize", "filesize_approx")):
                        continue
                    if not all(k in fmt for k in ("format", "format_id", "ext", "format_note")):
                        continue
                    size = fmt.get("filesize") or fmt.get("filesize_approx")
                    if not size:
                        continue
                    out.append(
                        {
                            "format": fmt["format"],
                            "filesize": size,
                            "format_id": fmt["format_id"],
                            "ext": fmt["ext"],
                            "format_note": fmt["format_note"],
                            "yturl": link,
                        }
                    )
        except Exception:
            pass

        async with _formats_lock:
            if len(_formats_cache) > YOUTUBE_META_MAX:
                _formats_cache.clear()
            _formats_cache[key] = (now, out, link)

        return out, link

    @capture_internal_err
    async def slider(
        self, link: str, query_type: int, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], str, str]:
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(
                f"Query type index {query_type} out of range (found {len(results)} results)"
            )
        r = results[query_type]
        return (
            r.get("title", ""),
            r.get("duration"),
            r.get("thumbnails", [{}])[-1].get("url", "").split("?")[0],
            r.get("id", ""),
        )

    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        link = self._prepare_link(link, videoid)

        if video:
            if await self.is_live(link):
                status, stream_url = await self.video(link)
                if status == 1:
                    return stream_url, None
                return None, None

            if await is_on_off(1):
                p = await yt_dlp_download(link, type="video", title=await self.title(link))
                return (p, True) if p else (None, None)

            # Try NubCoder API first for video stream
            if USE_NUBCODER_API:
                try:
                    api_info = nubcoder_get_info(link, max_results=1)
                    if api_info and 'error' not in api_info and api_info.get('video_id') != 'N/A':
                        stream_url = api_info.get('url') or api_info.get('stream_url', '')
                        if stream_url and stream_url != 'N/A':
                            return stream_url, None
                except Exception as e:
                    from AnnieXMedia.logging import LOGGER
                    LOGGER(__name__).debug(f"NubCoder API download failed: {e}")

            stdout, _ = await _exec_proc(
                "yt-dlp",
                *(_cookies_args()),
                "-g",
                "-f",
                "best[height<=?720][width<=?1280]",
                link,
            )
            if stdout:
                return stdout.decode().split("\n")[0], None
            return None, None

        # For audio, use yt_dlp_download which already has API integration
        p = await yt_dlp_download(link, type="audio", title=await self.title(link))
        return (p, True) if p else (None, None)
