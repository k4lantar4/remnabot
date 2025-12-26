import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import aiohttp
from packaging import version
import re

from app.config import settings
from app.localization.texts import get_texts


_default_texts = get_texts()

logger = logging.getLogger(__name__)


class VersionInfo:
    def __init__(self, tag_name: str, published_at: str, name: str, body: str, prerelease: bool = False):
        self.tag_name = tag_name
        self.published_at = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        self.name = name or tag_name
        self.body = body
        self.prerelease = prerelease
        self.is_dev = 'dev' in tag_name.lower()
    
    @property
    def clean_version(self) -> str:
        return re.sub(r'^v', '', self.tag_name)
    
    @property
    def version_obj(self):
        try:
            clean_ver = self.clean_version
            if 'dev' in clean_ver:
                base_ver = clean_ver.split('-dev')[0]
                return version.parse(f"{base_ver}.dev")
            return version.parse(clean_ver)
        except Exception:
            return version.parse("0.0.0")
    
    @property
    def formatted_date(self) -> str:
        return self.published_at.strftime('%d.%m.%Y %H:%M')
    
    @property
    def short_description(self) -> str:
        if not self.body:
            return _default_texts.get_text("VERSION_NO_DESCRIPTION", "No description")
        
        description = self.body.strip()
        if len(description) > 350:
            description = description[:347] + "..."
        
        return description


class VersionService:
    def __init__(self, bot=None):
        self.bot = bot
        self.repo = getattr(settings, 'VERSION_CHECK_REPO', 'fr1ngg/remnawave-bedolaga-telegram-bot')
        self.enabled = getattr(settings, 'VERSION_CHECK_ENABLED', True)
        self.current_version = self._get_current_version()
        self.cache_ttl = 3600  
        self._cache: Dict = {}
        self._last_check: Optional[datetime] = None
        self._notification_service = None
    
    async def get_latest_stable_version(self) -> str:
        try:
            url = f"https://api.github.com/repos/{self.repo}/releases/latest"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['tag_name']
        except Exception:
            pass
        return "UNKNOW"
    
    def _get_current_version(self) -> str:
        import os
        
        current = os.getenv('VERSION', '').strip()
        
        if current:
            if '-' in current and current.startswith('v'):
                base_version = current.split('-')[0] 
                if base_version.count('.') == 2: 
                    return base_version
            return current
        
        return "UNKNOW"
    
    def set_notification_service(self, notification_service):
        self._notification_service = notification_service
    
    async def check_for_updates(self, force: bool = False) -> Tuple[bool, List[VersionInfo]]:
        if not self.enabled:
            return False, []
        
        try:
            releases = await self._fetch_releases(force)
            if not releases:
                return False, []
            
            current_ver = self._parse_version(self.current_version)
            newer_releases = []
            
            for release in releases:
                release_ver = release.version_obj
                if release_ver > current_ver:
                    newer_releases.append(release)
            
            newer_releases.sort(key=lambda x: x.version_obj, reverse=True)
            
            has_updates = len(newer_releases) > 0
            
            if has_updates and not force:
                await self._send_update_notification(newer_releases)
            
            return has_updates, newer_releases
            
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return False, []
    
    async def _fetch_releases(self, force: bool = False) -> List[VersionInfo]:
        if not force and self._cache and self._last_check:
            if datetime.now() - self._last_check < timedelta(seconds=self.cache_ttl):
                return self._cache.get('releases', [])
        
        url = f"https://api.github.com/repos/{self.repo}/releases"
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        releases = []
                        
                        for release_data in data[:20]: 
                            release = VersionInfo(
                                tag_name=release_data['tag_name'],
                                published_at=release_data['published_at'],
                                name=release_data['name'],
                                body=release_data['body'] or '',
                                prerelease=release_data['prerelease']
                            )
                            releases.append(release)
                        
                        self._cache['releases'] = releases
                        self._last_check = datetime.now()
                        
                        logger.info(f"Fetched {len(releases)} releases from GitHub")
                        return releases
                    else:
                        logger.warning(f"GitHub API returned status {response.status}")
                        return []
                        
        except asyncio.TimeoutError:
            logger.warning("Timeout while requesting GitHub API")
            return []
        except Exception as e:
            logger.error(f"GitHub API request failed: {e}")
            return []
    
    def _parse_version(self, version_str: str):
        try:
            clean_ver = re.sub(r'^v', '', version_str)
            if 'dev' in clean_ver:
                base_ver = clean_ver.split('-dev')[0]
                return version.parse(f"{base_ver}.dev")
            if 'unknow' in clean_ver.lower(): 
                return version.parse("0.0.0")
            return version.parse(clean_ver)
        except Exception:
            return version.parse("0.0.0")
    
    async def _send_update_notification(self, newer_releases: List[VersionInfo]):
        if not self._notification_service or not newer_releases:
            return
        
        try:
            latest_version = newer_releases[0]
            cache_key = f"notified_{latest_version.tag_name}"
            
            if self._cache.get(cache_key):
                return
            
            await self._notification_service.send_version_update_notification(
                current_version=self.current_version,
                latest_version=latest_version,
                total_updates=len(newer_releases)
            )
            
            self._cache[cache_key] = True
            
        except Exception as e:
            logger.error(f"Failed to send update notification: {e}")
    
    async def get_version_info(self) -> Dict:
        try:
            has_updates, newer_releases = await self.check_for_updates()
            all_releases = await self._fetch_releases()
            
            current_release = None
            current_ver = self._parse_version(self.current_version)
            
            for release in all_releases:
                if release.version_obj == current_ver:
                    current_release = release
                    break
            
            return {
                'current_version': self.current_version,
                'current_release': current_release,
                'has_updates': has_updates,
                'newer_releases': newer_releases[:5],
                'total_newer': len(newer_releases),
                'last_check': self._last_check,
                'repo_url': f"https://github.com/{self.repo}"
            }
            
        except Exception as e:
            logger.error(f"Failed to get version info: {e}")
            return {
                'current_version': self.current_version,
                'current_release': None,
                'has_updates': False,
                'newer_releases': [],
                'total_newer': 0,
                'last_check': None,
                'repo_url': f"https://github.com/{self.repo}",
                'error': str(e)
            }
    
    async def start_periodic_check(self):
        if not self.enabled:
            logger.info("Version checks disabled")
            return
        
        logger.info(f"Starting periodic update checks for {self.repo}")
        logger.info(f"Current version: {self.current_version}")
        
        while True:
            try:
                await asyncio.sleep(3600) 
                await self.check_for_updates()
                
            except asyncio.CancelledError:
                logger.info("Stopping update checks")
                break
            except Exception as e:
                logger.error(f"Error in periodic update check: {e}")
                await asyncio.sleep(300) 
    
    def format_version_display(self, version_info: VersionInfo) -> str:
        status_icon = ""
        if version_info.prerelease:
            status_icon = "🧪"
        elif version_info.is_dev:
            status_icon = "🔧"
        else:
            status_icon = "📦"
        
        return f"{status_icon} {version_info.tag_name}"


version_service = VersionService()
