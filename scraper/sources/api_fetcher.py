"""
API 数据源获取模块
支持汇率、股票、商品等实时数据

注意: 此模块需要 API Key 才能工作
没有 API Key 时，相关功能将被禁用，但不影响其他功能
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_shared_http_client = None


async def _get_shared_client():
    """获取共享的 httpx.AsyncClient（连接池复用）"""
    global _shared_http_client
    if _shared_http_client is None or _shared_http_client.is_closed:
        import httpx
        _shared_http_client = httpx.AsyncClient(timeout=15)
    return _shared_http_client


async def close_shared_client():
    """关闭共享 httpx.AsyncClient"""
    global _shared_http_client
    if _shared_http_client and not _shared_http_client.is_closed:
        await _shared_http_client.aclose()
        _shared_http_client = None


@dataclass
class MarketData:
    """市场数据结构"""
    source: str
    data_type: str  # forex, commodity, stock, crypto
    symbol: str
    value: float
    timestamp: datetime
    metadata: dict = None


class ExchangeRateAPI:
    """
    ExchangeRate-API 汇率数据获取
    免费计划: 1500 请求/月, 每天更新
    注册: https://www.exchangerate-api.com/
    """
    
    def __init__(self):
        self.api_key = os.getenv("EXCHANGE_RATE_API_KEY", "")
        self.base_url = "https://v6.exchangerate-api.com/v6"
        self.enabled = bool(self.api_key)
        
        if not self.enabled:
            logger.info("ExchangeRate-API: 未配置 API Key，汇率数据功能已禁用")
    
    async def get_latest_rates(self, base_currency: str = "USD") -> Optional[dict]:
        """获取最新汇率"""
        if not self.enabled:
            return None
        
        url = f"{self.base_url}/{self.api_key}/latest/{base_currency}"
        
        try:
            client = await _get_shared_client()
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("result") == "success":
                return {
                    "base": base_currency,
                    "date": data.get("time_last_update_utc"),
                    "rates": data.get("conversion_rates", {}),
                    "source": "exchangerate-api"
                }
            else:
                logger.warning(f"ExchangeRate-API 返回错误: {data.get('error-type')}")
        except Exception as e:
            logger.error(f"ExchangeRate-API 请求失败: {type(e).__name__}")
        
        return None
    
    async def get_forex_pairs(self, pairs: list[tuple[str, str]] = None) -> list[MarketData]:
        """获取主要货币对汇率"""
        if pairs is None:
            pairs = [
                ("USD", "CNY"),
                ("USD", "EUR"),
                ("USD", "JPY"),
                ("USD", "GBP"),
                ("EUR", "CNY"),
                ("EUR", "JPY"),
            ]
        
        rates = await self.get_latest_rates("USD")
        if not rates:
            return []
        
        results = []
        for base, quote in pairs:
            if base == "USD":
                rate = rates["rates"].get(quote)
            else:
                base_rate = rates["rates"].get(base)
                quote_rate = rates["rates"].get(quote)
                if base_rate and quote_rate:
                    rate = quote_rate / base_rate
                else:
                    continue
            
            if rate:
                results.append(MarketData(
                    source="exchangerate-api",
                    data_type="forex",
                    symbol=f"{base}/{quote}",
                    value=rate,
                    timestamp=datetime.now(),
                    metadata={"base": base, "quote": quote}
                ))
        
        return results


class AlphaVantageAPI:
    """
    Alpha Vantage 市场数据获取
    免费计划: 25 请求/天, 5 请求/分钟
    注册: https://www.alphavantage.co/support/#api-key
    """
    
    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        self.base_url = "https://www.alphavantage.co/query"
        self.enabled = bool(self.api_key)
        
        if not self.enabled:
            logger.info("Alpha Vantage: 未配置 API Key，股票/商品数据功能已禁用")
    
    async def _query(self, params: dict) -> Optional[dict]:
        """发送查询请求"""
        if not self.enabled:
            return None
        
        params["apikey"] = self.api_key
        
        try:
            client = await _get_shared_client()
            response = await client.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Alpha Vantage 请求失败: {e}")
        
        return None
    
    async def get_forex_rate(self, from_currency: str, to_currency: str) -> Optional[MarketData]:
        """获取外汇汇率"""
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_currency,
            "to_currency": to_currency
        }
        
        data = await self._query(params)
        if not data or "Realtime Currency Exchange Rate" not in data:
            return None
        
        rate_data = data["Realtime Currency Exchange Rate"]
        
        return MarketData(
            source="alphavantage",
            data_type="forex",
            symbol=f"{from_currency}/{to_currency}",
            value=float(rate_data.get("5. Exchange Rate", 0)),
            timestamp=datetime.now(),
            metadata={
                "bid": rate_data.get("8. Bid Price"),
                "ask": rate_data.get("9. Ask Price")
            }
        )
    
    async def get_commodity_price(self, commodity: str) -> Optional[MarketData]:
        """获取商品价格（原油等）"""
        params = {
            "function": "WTI",
            "interval": "daily"
        }
        
        data = await self._query(params)
        if not data or "data" not in data:
            return None
        
        latest = data["data"][0] if data["data"] else None
        if not latest:
            return None
        
        return MarketData(
            source="alphavantage",
            data_type="commodity",
            symbol="WTI",
            value=float(latest.get("value", 0)),
            timestamp=datetime.fromisoformat(latest.get("date", "")),
            metadata={"unit": "USD/barrel"}
        )
    
    async def get_crypto_rate(self, symbol: str, market: str = "USD") -> Optional[MarketData]:
        """获取加密货币价格"""
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": symbol,
            "to_currency": market
        }
        
        data = await self._query(params)
        if not data or "Realtime Currency Exchange Rate" not in data:
            return None
        
        rate_data = data["Realtime Currency Exchange Rate"]
        
        return MarketData(
            source="alphavantage",
            data_type="crypto",
            symbol=f"{symbol}/{market}",
            value=float(rate_data.get("5. Exchange Rate", 0)),
            timestamp=datetime.now(),
            metadata={"market": market}
        )


class MarketDataFetcher:
    """
    市场数据聚合获取器
    统一管理多个 API 数据源
    
    使用方法:
        fetcher = MarketDataFetcher()
        data = await fetcher.fetch_all()
        
    注意: 没有 API Key 时，返回空数据，不会报错
    """
    
    def __init__(self):
        self.exchangerate = ExchangeRateAPI()
        self.alphavantage = AlphaVantageAPI()
        
        # 检查是否有任何可用的 API
        self.has_any_api = self.exchangerate.enabled or self.alphavantage.enabled
        
        if not self.has_any_api:
            logger.info("未配置任何市场数据 API Key，市场数据功能已禁用")
            logger.info("如需启用，请在 .env 文件中配置:")
            logger.info("  - EXCHANGE_RATE_API_KEY (汇率)")
            logger.info("  - ALPHA_VANTAGE_API_KEY (股票/商品)")
    
    def get_status(self) -> dict:
        """获取 API 配置状态"""
        return {
            "exchangerate": {
                "enabled": self.exchangerate.enabled,
                "description": "汇率数据"
            },
            "alphavantage": {
                "enabled": self.alphavantage.enabled,
                "description": "股票/商品/加密货币"
            }
        }
    
    async def fetch_all(self) -> dict[str, list[MarketData]]:
        """获取所有市场数据"""
        results = {
            "forex": [],
            "commodity": [],
            "crypto": [],
            "stock": []
        }
        
        if not self.has_any_api:
            return results
        
        # 并发获取各类数据
        tasks = [
            self._fetch_forex(),
            self._fetch_commodities(),
            self._fetch_crypto(),
        ]
        
        for task_results in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(task_results, Exception):
                logger.error(f"获取市场数据失败: {task_results}")
                continue
            
            for data in task_results:
                if data.data_type in results:
                    results[data.data_type].append(data)
        
        return results
    
    async def _fetch_forex(self) -> list[MarketData]:
        """获取外汇数据"""
        # 优先使用 ExchangeRate-API（配额更多）
        if self.exchangerate.enabled:
            return await self.exchangerate.get_forex_pairs()
        
        # 备选：Alpha Vantage
        if self.alphavantage.enabled:
            pairs = [("USD", "CNY"), ("USD", "EUR"), ("USD", "JPY")]
            results = []
            for base, quote in pairs:
                data = await self.alphavantage.get_forex_rate(base, quote)
                if data:
                    results.append(data)
                await asyncio.sleep(0.2)  # 避免速率限制
            return results
        
        return []
    
    async def _fetch_commodities(self) -> list[MarketData]:
        """获取商品数据"""
        if not self.alphavantage.enabled:
            return []
        
        results = []
        
        # 获取原油价格
        oil = await self.alphavantage.get_commodity_price("oil")
        if oil:
            results.append(oil)
        
        return results
    
    async def _fetch_crypto(self) -> list[MarketData]:
        """获取加密货币数据"""
        if not self.alphavantage.enabled:
            return []
        
        results = []
        cryptos = ["BTC", "ETH"]
        
        for crypto in cryptos:
            data = await self.alphavantage.get_crypto_rate(crypto)
            if data:
                results.append(data)
            await asyncio.sleep(0.2)
        
        return results
    
    def format_for_storage(self, data: list[MarketData]) -> list[dict]:
        """格式化数据用于存储到数据库"""
        return [
            {
                "source": d.source,
                "data_type": d.data_type,
                "symbol": d.symbol,
                "value": d.value,
                "timestamp": d.timestamp.isoformat(),
                "metadata": d.metadata or {}
            }
            for d in data
        ]


# 全局单例（避免在 run_news.py 中每次调用都创建新实例）
_market_fetcher = None


def get_market_fetcher() -> MarketDataFetcher:
    """获取全局 MarketDataFetcher 单例"""
    global _market_fetcher
    if _market_fetcher is None:
        _market_fetcher = MarketDataFetcher()
    return _market_fetcher


async def fetch_market_data() -> dict[str, list[MarketData]]:
    """获取所有市场数据的便捷函数"""
    return await get_market_fetcher().fetch_all()


if __name__ == "__main__":
    # 测试代码
    async def test():
        logging.basicConfig(level=logging.INFO)
        
        fetcher = MarketDataFetcher()
        
        # 显示配置状态
        print("\n📊 API 配置状态:")
        for name, info in fetcher.get_status().items():
            status = "✅" if info["enabled"] else "❌"
            print(f"  {status} {name}: {info['description']}")
        
        if not fetcher.has_any_api:
            print("\n⚠️  未配置任何 API Key，无法获取市场数据")
            print("请在 .env 文件中配置 API Key")
            return
        
        print("\n📈 获取市场数据...")
        data = await fetcher.fetch_all()
        
        for category, items in data.items():
            if items:
                print(f"\n{category}:")
                for item in items:
                    print(f"  {item.symbol}: {item.value}")
    
    asyncio.run(test())
