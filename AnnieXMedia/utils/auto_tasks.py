# Authored By Certified Coders © 2025
import asyncio
import os
import shutil
from datetime import datetime, timedelta
from ..logging import LOGGER
from .downloader import close_http_session

async def auto_restart():
    """Restarts the bot every 24 hours"""
    while True:
        await asyncio.sleep(86400) # 24 hours
        LOGGER("AnnieXMedia.auto_tasks").info("Auto-restarting bot (24h schedule)...")
        # We use os._exit(0) to ensure the process actually dies, 
        # and rely on the VPS process manager (pm2/systemd/nohup loop) to restart it.
        try:
            await close_http_session()
        except:
            pass
        os._exit(0)

async def auto_clear_cache():
    """Clears cache and downloads every 7 days"""
    from ..core.dir import DOWNLOAD_DIR, CACHE_DIR, COUPLE_DIR
    
    while True:
        await asyncio.sleep(604800) # 7 days
        LOGGER("AnnieXMedia.auto_tasks").info("Auto-clearing cache and downloads (7d schedule)...")
        
        for directory in [DOWNLOAD_DIR, CACHE_DIR, COUPLE_DIR]:
            if os.path.exists(directory):
                try:
                    for filename in os.listdir(directory):
                        file_path = os.path.join(directory, filename)
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                except Exception as e:
                    LOGGER("AnnieXMedia.auto_tasks").error(f"Failed to clear {directory}: {e}")
        
        LOGGER("AnnieXMedia.auto_tasks").info("Cache and downloads cleared successfully.")
