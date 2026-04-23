# Authored By Certified Coders © 2025
import requests
import re
from typing import List, Dict, Optional, Tuple
from config import API_KEY, API_URL

BASE_URL = API_URL or 'https://api.nubcoder.com'
API_TOKEN = API_KEY


def _parse_duration(duration) -> int:
    """Parse duration to seconds. Handles both 'MM:SS' format and integer seconds."""
    if isinstance(duration, (int, float)):
        return int(duration)
    if isinstance(duration, str):
        # Handle MM:SS or HH:MM:SS format
        parts = duration.split(':')
        try:
            if len(parts) == 2:  # MM:SS
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:  # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except (ValueError, IndexError):
            pass
    return 0


def get_video_info(url_or_query: str, max_results: int = 1) -> Dict:
    """
    Get video info from NubCoder API
    Returns dict with: title, video_id, duration, youtube_link, channel_name, views, url, thumbnail, time_taken
    """
    try:
        response = requests.get(
            f'{BASE_URL}/info',
            params={'token': API_TOKEN, 'q': url_or_query, 'max_results': max_results},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        if 'error' in data:
            return {'error': data.get('error')}
        
        # Handle both 'url' and 'stream_url' field names
        stream_url = data.get('url') or data.get('stream_url', 'N/A')
        
        # Parse duration to seconds
        duration_raw = data.get('duration', 0)
        duration_seconds = _parse_duration(duration_raw)
        
        return {
            'title': data.get('title', 'N/A'),
            'video_id': data.get('video_id', 'N/A'),
            'duration': duration_seconds,
            'youtube_link': data.get('youtube_link', 'N/A'),
            'channel_name': data.get('channel_name', 'N/A'),
            'views': data.get('views', 0),
            'url': stream_url,
            'thumbnail': data.get('thumbnail', 'N/A'),
            'time_taken': data.get('time_taken', 'N/A')
        }
    except requests.RequestException as e:
        return {'error': str(e)}

def search_videos(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search videos from NubCoder API
    Returns list of dicts with: title, video_id, channel_name, duration, views, youtube_link
    """
    try:
        response = requests.get(
            f'{BASE_URL}/search',
            params={'q': query, 'max_results': max_results},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        if 'error' in data:
            return []
        
        results = []
        for video in data.get('results', []):
            # Parse duration to seconds
            duration_raw = video.get('duration', 0)
            duration_seconds = _parse_duration(duration_raw)
            
            results.append({
                'title': video.get('title', 'N/A'),
                'video_id': video.get('video_id', 'N/A'),
                'channel_name': video.get('channel_name', 'N/A'),
                'duration': duration_seconds,
                'views': video.get('views', 0),
                'youtube_link': video.get('youtube_link', 'N/A'),
                'thumbnail': video.get('thumbnail', '')
            })
        return results
    except requests.RequestException as e:
        return []

def get_rate_limit_status() -> Dict:
    """
    Get quota status from NubCoder API
    Returns dict with: daily_limit, requests_used, requests_remaining, is_admin, reset_time
    """
    try:
        response = requests.get(
            f'{BASE_URL}/rate-limit-status',
            params={'token': API_TOKEN},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            'daily_limit': data.get('daily_limit', 0),
            'requests_used': data.get('requests_used', 0),
            'requests_remaining': data.get('requests_remaining', 0),
            'is_admin': data.get('is_admin', False),
            'reset_time': data.get('reset_time', 'N/A')
        }
    except requests.RequestException as e:
        return {'error': str(e)}
