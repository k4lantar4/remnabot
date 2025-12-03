import logging
import aiohttp
import asyncio
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CurrencyConverter:
    
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 3600  # 1 hour
        self._last_update = {}
    
    async def get_usd_to_rub_rate(self) -> float:
        """Get USD/RUB exchange rate with caching"""
        
        cache_key = "USD_RUB"
        now = datetime.utcnow()
        
        # Check cache
        if (cache_key in self._cache and 
            cache_key in self._last_update and
            (now - self._last_update[cache_key]).seconds < self._cache_ttl):
            return self._cache[cache_key]
        
        # Get new rate
        rate = await self._fetch_exchange_rate()
        
        if rate:
            self._cache[cache_key] = rate
            self._last_update[cache_key] = now
            logger.info(f"Updated USD/RUB rate: {rate}")
            return rate
        
        # Return from cache if API is unavailable
        if cache_key in self._cache:
            logger.warning("Exchange rate API unavailable, using cached rate")
            return self._cache[cache_key]
        
        # Fallback rate
        logger.warning("Using fallback USD/RUB rate: 95")
        return 95.0
    
    async def _fetch_exchange_rate(self) -> Optional[float]:
        """Get exchange rate from multiple sources"""
        
        sources = [
            self._fetch_from_cbr,
            self._fetch_from_exchangerate_api,
            self._fetch_from_fixer
        ]
        
        for source in sources:
            try:
                rate = await source()
                if rate and 50 < rate < 200:  # Reasonable rate bounds
                    return rate
            except Exception as e:
                logger.debug(f"Error getting rate from {source.__name__}: {e}")
                continue
        
        return None
    
    async def _fetch_from_cbr(self) -> Optional[float]:
        """Get rate from Central Bank of Russia website"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get('https://www.cbr-xml-daily.ru/daily_json.js') as response:
                    if response.status == 200:
                        data = await response.json()
                        usd_rate = data['Valute']['USD']['Value']
                        return float(usd_rate)
        except Exception as e:
            logger.debug(f"Error getting CBR rate: {e}")
            return None
    
    async def _fetch_from_exchangerate_api(self) -> Optional[float]:
        """Get rate from exchangerate-api.com"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get('https://api.exchangerate-api.com/v4/latest/USD') as response:
                    if response.status == 200:
                        data = await response.json()
                        rub_rate = data['rates']['RUB']
                        return float(rub_rate)
        except Exception as e:
            logger.debug(f"Error getting exchangerate-api rate: {e}")
            return None
    
    async def _fetch_from_fixer(self) -> Optional[float]:
        """Get rate from fixer.io (free plan)"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # Use free endpoint (EUR base)
                async with session.get('https://api.fixer.io/latest?access_key=YOUR_API_KEY&symbols=USD,RUB') as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            # Convert EUR -> USD -> RUB
                            usd_eur = data['rates']['USD']
                            rub_eur = data['rates']['RUB']
                            usd_rub = rub_eur / usd_eur
                            return float(usd_rub)
        except Exception as e:
            logger.debug(f"Error getting fixer rate: {e}")
            return None
    
    async def usd_to_rub(self, usd_amount: float) -> float:
        """Convert USD to RUB"""
        rate = await self.get_usd_to_rub_rate()
        return usd_amount * rate
    
    async def rub_to_usd(self, rub_amount: float) -> float:
        """Convert RUB to USD"""
        rate = await self.get_usd_to_rub_rate()
        return rub_amount / rate

# Global instance
currency_converter = CurrencyConverter()
