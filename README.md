# PyCoin Trading Framework

一个完整的加密货币交易框架，提供多交易所API封装、配置管理、日志记录、通知服务等功能。适合快速开发交易机器人和量化策略。

## ✨ 核心特性

- 🚀 **多交易所支持** - Binance、Gate.io、Bybit 完整API封装
- ⚡ **异步高性能** - 基于asyncio的异步架构
- 🔧 **完整框架** - 配置管理、日志记录、通知服务、Redis缓存
- 📊 **实时数据** - WebSocket实时行情和交易数据
- 🛡️ **安全可靠** - 配置文件分离、完整的签名验证和错误处理
- 📱 **多种通知** - 企业微信、Telegram、钉钉、邮件通知
- 🎯 **开箱即用** - 一键初始化，快速开始交易开发

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/4cya/pycoin-framework.git my_trading_bot
cd my_trading_bot
```

### 2. 创建虚拟环境 (推荐)

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. 安装依赖

```bash
# 确保虚拟环境已激活，然后安装依赖
pip install -r requirements.txt
```

### 4. 初始化配置

```bash
# 运行初始化脚本 (确保虚拟环境已激活)
python setup_project.py
```

或手动复制配置文件：

```bash
# 复制配置模板
cp config/app.example.yaml config/app.yaml
cp secrets/accounts.example.yaml secrets/accounts.yaml
```

### 5. 配置API密钥

编辑 `secrets/accounts.yaml` 文件：

```yaml
exchanges:
  binance:
    api_key: "your_binance_api_key"
    api_secret: "your_binance_secret"
```

### 6. 开始使用

```python
import asyncio
from exchange.binance.binance_spot import BinanceSpotExchange
from utils.settings import Settings

async def main():
    # 加载配置
    settings = Settings()
    
    # 获取Binance配置
    binance_config = settings.get_account("binance")
    
    # 创建交易客户端
    client = BinanceSpotExchange(
        api_key=binance_config["api_key"],
        api_secret=binance_config["api_secret"]
    )
    
    # 获取账户信息
    account, error = await client.get_account()
    if not error:
        print("✅ 账户连接成功")
        print(f"账户余额: {account}")
    else:
        print(f"❌ 连接失败: {error}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 📁 项目结构

```
pycoin-framework/
├── config/
│   ├── app.example.yaml      # 应用配置模板
│   └── app.yaml             # 应用配置 (用户创建)
├── secrets/
│   ├── accounts.example.yaml # 账户配置模板
│   └── accounts.yaml        # 账户配置 (用户创建)
├── exchange/                # 交易所API封装
│   ├── binance/            # Binance API
│   ├── gate/               # Gate.io API
│   └── bybit/              # Bybit API
├── utils/                  # 工具类
│   ├── settings.py         # 配置管理
│   ├── log.py              # 日志管理
│   ├── notifier.py         # 通知服务
│   ├── redis_client.py     # Redis客户端
│   └── http_client.py      # HTTP客户端
├── examples/               # 示例代码
├── setup_project.py        # 项目初始化脚本
├── requirements.txt        # 依赖列表
└── README.md              # 项目说明
```

## 🔧 功能模块

### 交易所API
- **Binance**: 现货、合约、WebSocket
- **Gate.io**: 现货、合约、WebSocket  
- **Bybit**: 统一账户、WebSocket

### 工具服务
- **配置管理**: YAML配置文件，环境变量覆盖
- **日志记录**: 多级别日志，文件轮转
- **通知服务**: 企业微信、Telegram、钉钉、邮件
- **Redis缓存**: 数据缓存和状态管理
- **心跳监控**: 服务状态监控

## 📚 配置说明

### 应用配置 (config/app.yaml)
```yaml
# Redis配置
redis:
  host: localhost
  port: 6379

# 代理配置
proxy:
  enabled: false
  http: "http://127.0.0.1:7890"

# 通知配置
notifications:
  wxwork:
    webhook_key: "your-webhook-key"
```

### 账户配置 (secrets/accounts.yaml)
```yaml
exchanges:
  binance:
    api_key: "your_api_key"
    api_secret: "your_api_secret"
```

## 🔗 获取API密钥

| 交易所 | 返佣比例 | 注册链接 | 特色 |
|--------|----------|----------|------|
| **Binance** | 20% | [点击注册](https://accounts.marketwebb.me/zh-CN/register?ref=BN2025) | 全球最大，流动性最好 |
| **Gate.io** | 40% | [点击注册](https://aaspeed.gaterelay.com/zh/signup?ref_type=103&ref=A1UQVVsN) | 老牌交易所，币种丰富 |
| **Bybit** | 33% | [点击注册](https://partner.bybit.com/b/BB2025) | 体验流畅，可交易美股 |

> 💡 **提示**: 使用上述邀请链接注册可享受手续费返佣优惠，降低交易成本

## 📱 通知服务

### 企业微信机器人
1. 在企业微信群中添加机器人
2. 获取Webhook Key
3. 配置到 `config/app.yaml`

### Telegram机器人
1. 创建Telegram机器人 (@BotFather)
2. 获取Bot Token和Chat ID
3. 配置到 `config/app.yaml`

## 🛡️ 安全建议

- ✅ 使用测试网进行开发测试
- ✅ API密钥设置只读权限（数据获取）
- ✅ 生产环境使用环境变量
- ✅ 定期轮换API密钥
- ✅ 设置IP白名单
- ✅ 不要将配置文件提交到代码仓库

## 📝 示例代码

查看 `examples/` 目录获取更多示例：

- `basic_trading.py` - 基础交易示例
- `websocket_demo.py` - WebSocket实时数据
- `multi_exchange.py` - 多交易所套利
- `notification_test.py` - 通知服务测试

## ⚠️ 风险提示

加密货币交易存在极高风险，可能导致本金全部损失。本框架仅供学习和研究使用，请谨慎投资，理性交易。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
