"""
配置向导
帮助用户快速设置数据源 API Key
"""

import os
import sys
from pathlib import Path


def create_env_file():
    """创建 .env 文件"""
    env_path = Path(__file__).parent.parent / ".env"
    env_example_path = Path(__file__).parent.parent / ".env.example"
    
    if env_path.exists():
        print(f"⚠️  .env 文件已存在: {env_path}")
        response = input("是否覆盖? (y/N): ").strip().lower()
        if response != "y":
            print("已取消")
            return False
    
    # 读取模板
    if env_example_path.exists():
        with open(env_example_path, "r") as f:
            template = f.read()
    else:
        print("❌ .env.example 文件不存在")
        return False
    
    # 收集用户输入
    print("\n" + "=" * 60)
    print("  Zheye 配置向导")
    print("=" * 60)
    print("\n请填写以下配置（留空跳过）:\n")
    
    # 数据库配置
    print("📦 数据库配置")
    db_url = input("  DATABASE_URL [postgresql+asyncpg://zheye:password@localhost:5432/zheye]: ").strip()
    if db_url:
        template = template.replace(
            "DATABASE_URL=postgresql+asyncpg://zheye:PASSWORD@localhost:5432/zheye",
            f"DATABASE_URL={db_url}"
        )
    
    # AI 配置
    print("\n🤖 AI 分析配置")
    print("  (用于生成每日分析报告、趋势分析等)")
    deepseek_key = input("  DEEPSEEK_API_KEY: ").strip()
    if deepseek_key:
        template = template.replace(
            "DEEPSEEK_API_KEY=your_deepseek_api_key_here",
            f"DEEPSEEK_API_KEY={deepseek_key}"
        )
    
    # 市场数据 API
    print("\n📊 市场数据 API（可选）")
    print("  ExchangeRate-API: https://www.exchangerate-api.com/")
    er_key = input("  EXCHANGE_RATE_API_KEY: ").strip()
    if er_key:
        template = template.replace("EXCHANGE_RATE_API_KEY=", f"EXCHANGE_RATE_API_KEY={er_key}")
    
    print("\n  Alpha Vantage: https://www.alphavantage.co/support/#api-key")
    av_key = input("  ALPHA_VANTAGE_API_KEY: ").strip()
    if av_key:
        template = template.replace("ALPHA_VANTAGE_API_KEY=", f"ALPHA_VANTAGE_API_KEY={av_key}")
    
    # 写入文件
    with open(env_path, "w") as f:
        f.write(template)
    
    print(f"\n✅ 配置已保存到: {env_path}")
    return True


def show_status():
    """显示当前配置状态"""
    from dotenv import load_dotenv
    load_dotenv()
    
    print("\n" + "=" * 60)
    print("  当前配置状态")
    print("=" * 60)
    
    # 检查 .env 文件
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        print("\n⚠️  .env 文件不存在")
        print("运行 `python scripts/setup_config.py` 创建配置")
        return
    
    print(f"\n✅ .env 文件: {env_path}")
    
    # 检查各项配置
    configs = [
        ("DATABASE_URL", "数据库"),
        ("DEEPSEEK_API_KEY", "AI 分析"),
        ("EXCHANGE_RATE_API_KEY", "汇率数据"),
        ("ALPHA_VANTAGE_API_KEY", "股票/商品数据"),
    ]
    
    print("\n配置项:")
    for key, desc in configs:
        value = os.getenv(key, "")
        if value:
            # 只显示前 8 位
            preview = f"{value[:8]}..." if len(value) > 8 else value
            print(f"  ✅ {desc}: {preview}")
        else:
            print(f"  ⚠️  {desc}: 未配置")


def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        show_status()
    else:
        print("Zheye 配置向导")
        print("-" * 40)
        print("1. 创建/更新 .env 配置文件")
        print("2. 查看当前配置状态")
        print("3. 退出")
        
        choice = input("\n请选择 (1-3): ").strip()
        
        if choice == "1":
            create_env_file()
        elif choice == "2":
            show_status()
        else:
            print("已退出")


if __name__ == "__main__":
    main()
