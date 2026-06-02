"""
数据源配置检查工具
帮助用户了解哪些数据源可用，哪些需要配置 API Key
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class ConfigChecker:
    """配置检查器"""
    
    def __init__(self):
        self.results = []
    
    def check_rss_sources(self) -> dict:
        """检查 RSS 源配置"""
        config_path = Path(__file__).parent.parent / "scraper" / "sources" / "config.yaml"
        
        if not config_path.exists():
            return {"status": "error", "message": "config.yaml not found"}
        
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        sources = config.get("sources", [])
        categories = {}
        
        for source in sources:
            cat = source.get("category", "unknown")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(source["name"])
        
        return {
            "status": "ok",
            "total": len(sources),
            "categories": categories
        }
    
    def check_api_sources(self) -> dict:
        """检查 API 数据源配置"""
        api_sources = {
            "ExchangeRate-API": {
                "env_key": "EXCHANGE_RATE_API_KEY",
                "description": "汇率数据 (165 种货币)",
                "free_quota": "1500 请求/月",
                "register_url": "https://www.exchangerate-api.com/"
            },
            "Alpha Vantage": {
                "env_key": "ALPHA_VANTAGE_API_KEY",
                "description": "股票/外汇/商品/加密货币",
                "free_quota": "25 请求/天",
                "register_url": "https://www.alphavantage.co/support/#api-key"
            },
            "Trading Economics": {
                "env_key": "TRADING_ECONOMICS_KEY",
                "description": "经济日历/宏观数据",
                "free_quota": "500 请求/月",
                "register_url": "https://tradingeconomics.com/api"
            }
        }
        
        results = {}
        for name, info in api_sources.items():
            key = os.getenv(info["env_key"], "")
            results[name] = {
                "configured": bool(key),
                "key_preview": f"{key[:8]}..." if key else "Not set",
                "description": info["description"],
                "free_quota": info["free_quota"],
                "register_url": info["register_url"]
            }
        
        return results
    
    def check_ai_config(self) -> dict:
        """检查 AI 分析配置"""
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        
        return {
            "configured": bool(api_key),
            "api_base": api_base,
            "key_preview": f"{api_key[:8]}..." if api_key else "Not set"
        }
    
    def print_report(self):
        """打印配置报告"""
        print("=" * 60)
        print("  Zheye 数据源配置检查报告")
        print("=" * 60)
        
        # RSS 源检查
        print("\n📡 RSS 数据源")
        print("-" * 40)
        rss = self.check_rss_sources()
        if rss["status"] == "ok":
            print(f"  总计: {rss['total']} 个源")
            for cat, sources in rss["categories"].items():
                print(f"  {cat}: {len(sources)} 个")
                for s in sources[:3]:
                    print(f"    - {s}")
                if len(sources) > 3:
                    print(f"    ... 还有 {len(sources) - 3} 个")
        else:
            print(f"  ❌ 错误: {rss['message']}")
        
        # API 数据源检查
        print("\n📊 API 数据源")
        print("-" * 40)
        apis = self.check_api_sources()
        for name, info in apis.items():
            status = "✅" if info["configured"] else "⚠️"
            print(f"  {status} {name}")
            print(f"     {info['description']}")
            print(f"     免费配额: {info['free_quota']}")
            if info["configured"]:
                print(f"     API Key: {info['key_preview']}")
            else:
                print(f"     注册: {info['register_url']}")
        
        # AI 配置检查
        print("\n🤖 AI 分析配置")
        print("-" * 40)
        ai = self.check_ai_config()
        status = "✅" if ai["configured"] else "⚠️"
        print(f"  {status} DeepSeek API")
        print(f"     API Base: {ai['api_base']}")
        if ai["configured"]:
            print(f"     API Key: {ai['key_preview']}")
        else:
            print(f"     注册: https://platform.deepseek.com/")
        
        # 总结
        print("\n" + "=" * 60)
        print("  配置说明")
        print("=" * 60)
        print("""
  1. RSS 源无需配置，开箱即用
  2. API 数据源需要注册免费 API Key
  3. AI 分析功能需要 DeepSeek API Key
  
  配置方法:
    cp .env.example .env
    # 编辑 .env 文件，填入你的 API Key
  
  没有 API Key 也能运行:
    - RSS 新闻抓取正常工作
    - 分类、关键词匹配等功能正常
    - API 数据源和 AI 分析功能将被禁用
        """)


def main():
    """主函数"""
    checker = ConfigChecker()
    checker.print_report()


if __name__ == "__main__":
    main()
