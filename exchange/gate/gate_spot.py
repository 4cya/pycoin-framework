# -*- coding: utf-8 -*-
"""
Gate.io 现货交易 REST API实现 (V4)

提供Gate.io现货交易的完整API接口，包括市场数据、交易、账户管理等功能。
API文档: https://www.gate.com/docs/developers/apiv4/zh_CN/#spot

"""

import time
import hmac
import hashlib
import json
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlencode
from utils.http_client import AsyncHttpRequest
from utils.settings import settings
from utils.log import logger


# API配置
REST_HOST = 'https://api.gateio.ws/api/v4'


class GateSpotExchange:
    """Gate.io 现货交易 REST API (V4)
    
    提供Gate.io现货交易的完整API接口，包括市场数据、交易、账户管理等功能。
    使用Gate.io V4 API规范。
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, proxy: bool = False):
        """初始化Gate.io现货API客户端
        
        Args:
            api_key: API密钥（可选，仅在需要访问私有接口时提供）
            api_secret: API密钥密码（可选，仅在需要访问私有接口时提供）
            proxy: 是否使用代理
            
        Note:
            - 如果只使用公开的行情接口，可以不提供API密钥
            - 访问账户信息、交易等私有接口时必须提供有效的API密钥
        """
        self._host = REST_HOST
        self._key = api_key
        self._secret = api_secret
        self._proxy = settings.get_proxy_config() if proxy else None
        self.recv_window = 5000

    # ========== 市场数据接口 ==========
    
    async def get_server_time(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取服务器时间"""
        result, error = await self.request("GET", "/spot/time")
        return result, error
    
    async def get_currencies(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取所有币种信息
        
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        result, error = await self.request("GET", "/spot/currencies")
        return result, error

    async def get_currency(self, currency: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取单个币种信息
        
        Args:
            currency: 币种名称，如 'BTC'
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        result, error = await self.request("GET", f"/spot/currencies/{currency}")
        return result, error

    async def get_symbols(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取所有交易对信息
        
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        result, error = await self.request("GET", "/spot/currency_pairs")
        return result, error

    async def get_symbol(self, symbol: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取单个交易对详情
        
        Args:
            symbol: 交易对，如 'BTC_USDT'
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        result, error = await self.request("GET", f"/spot/currency_pairs/{symbol}")
        return result, error

    async def get_tickers(self, symbol: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取交易对ticker信息
        
        Args:
            symbol: 交易对，如 'BTC_USDT'，不指定则返回所有交易对
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"currency_pair": symbol} if symbol else {}
        result, error = await self.request("GET", "/spot/tickers", params=params)
        return result, error

    async def get_depth(self, symbol: str, limit: Optional[int] = None, interval: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取订单簿深度
        
        Args:
            symbol: 交易对，如 'BTC_USDT'
            limit: 深度档位数量，默认为10，最大200
            interval: 价格精度，如 '0.1'
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"currency_pair": symbol}
        if limit:
            params["limit"] = limit
        if interval:
            params["interval"] = interval
        
        result, error = await self.request("GET", "/spot/order_book", params=params)
        return result, error

    async def get_trades(self, symbol: str, limit: int = 100, last_id: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取市场成交记录
        
        Args:
            symbol: 交易对，如 'BTC_USDT'
            limit: 返回数量，默认100，最大1000
            last_id: 指定列表项的id，获取从该id之后的数据
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {
            "currency_pair": symbol,
            "limit": limit
        }
        if last_id:
            params["last_id"] = last_id
            
        result, error = await self.request("GET", "/spot/trades", params=params)
        return result, error

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 100, 
                        from_time: Optional[int] = None, to_time: Optional[int] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取K线数据
        
        Args:
            symbol: 交易对，如 'BTC_USDT'
            interval: K线周期，如 '1m', '5m', '15m', '30m', '1h', '4h', '8h', '1d', '7d'
            limit: 返回数量，默认100，最大1000
            from_time: 开始时间戳
            to_time: 结束时间戳
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {
            "currency_pair": symbol,
            "interval": interval,
            "limit": limit
        }
        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time
            
        result, error = await self.request("GET", "/spot/candlesticks", params=params)
        return result, error

    # ========== 账户接口 ==========

    async def get_accounts(self, currency: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取现货账户余额
        
        Args:
            currency: 币种名称，如 'BTC'，不指定则返回所有币种
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"currency": currency} if currency else {}
        result, error = await self.request("GET", "/spot/accounts", params=params, auth=True)
        return result, error

    # ========== 交易接口 ==========

    async def create_order(self, symbol: str, side: str, amount: str, price: Optional[str] = None,
                          order_type: str = "limit", time_in_force: str = "gtc", 
                          iceberg: Optional[str] = None, auto_borrow: Optional[bool] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """创建订单
        
        Args:
            symbol: 交易对，如 'BTC_USDT'
            side: 买卖方向，'buy' 或 'sell'
            amount: 交易数量
            price: 交易价格（限价单必需）
            order_type: 订单类型，'limit' 或 'market'
            time_in_force: 订单有效期，'gtc', 'ioc', 'poc'
            iceberg: 冰山订单数量
            auto_borrow: 是否自动借贷
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        body = {
            "currency_pair": symbol,
            "side": side,
            "amount": amount,
            "type": order_type
        }
        
        if price:
            body["price"] = price
        if time_in_force != "gtc":
            body["time_in_force"] = time_in_force
        if iceberg:
            body["iceberg"] = iceberg
        if auto_borrow is not None:
            body["auto_borrow"] = auto_borrow
            
        result, error = await self.request("POST", "/spot/orders", body=body, auth=True)
        return result, error

    async def get_orders(self, symbol: str, status: str, page: int = 1, limit: int = 100) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取订单列表
        
        Args:
            symbol: 交易对，如 'BTC_USDT'
            status: 订单状态，'open', 'closed', 'cancelled'
            page: 页码，从1开始
            limit: 每页数量，最大100
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        # 按照旧版本实现，只传递必要参数
        params = {
            "currency_pair": symbol,
            "status": status
        }
        # 只有当page和limit不是默认值时才添加
        if page != 1:
            params["page"] = page
        if limit != 100:
            params["limit"] = limit
            
        result, error = await self.request("GET", "/spot/orders", params=params, auth=True)
        return result, error

    async def get_open_orders(self, page: int = 1, limit: int = 100) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取所有交易对的当前挂单列表
        
        Args:
            page: 页码，从1开始
            limit: 每页数量，最大100
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        # 按照旧版本实现，不传递任何参数
        result, error = await self.request("GET", "/spot/open_orders", auth=True)
        return result, error

    async def cancel_orders(self, symbol: str, side: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """批量取消订单
        
        Args:
            symbol: 交易对，如 'BTC_USDT'
            side: 买卖方向，'buy' 或 'sell'，不指定则取消所有方向
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"currency_pair": symbol}
        if side:
            params["side"] = side
            
        result, error = await self.request("DELETE", "/spot/orders", params=params, auth=True)
        return result, error

    async def cancel_order(self, order_id: str, symbol: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """取消单个订单
        
        Args:
            order_id: 订单ID
            symbol: 交易对，如 'BTC_USDT'
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"currency_pair": symbol}
        result, error = await self.request("DELETE", f"/spot/orders/{order_id}", params=params, auth=True)
        return result, error

    async def get_order(self, order_id: str, symbol: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取单个订单详情
        
        Args:
            order_id: 订单ID
            symbol: 交易对，如 'BTC_USDT'
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"currency_pair": symbol}
        result, error = await self.request("GET", f"/spot/orders/{order_id}", params=params, auth=True)
        return result, error

    async def get_my_trades(self, symbol: str, limit: int = 100, page: int = 1, 
                           order_id: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取个人成交记录
        
        Args:
            symbol: 交易对，如 'BTC_USDT'
            limit: 返回数量，默认100，最大1000
            page: 页码，从1开始
            order_id: 订单ID，指定则只返回该订单的成交记录
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {
            "currency_pair": symbol,
            "limit": limit,
            "page": page
        }
        if order_id:
            params["order_id"] = order_id
            
        result, error = await self.request("GET", "/spot/my_trades", params=params, auth=True)
        return result, error

    # ========== 辅助方法 ==========

    def _generate_signature(self, method: str, uri: str, query_string: str, payload: str, timestamp: str) -> str:
        """生成API签名
        
        完全按照旧版本成功的实现方式
        
        Args:
            method: HTTP方法（大写）
            uri: 请求URI（如 /api/v4/spot/currencies）
            query_string: 查询字符串（如 status=finished&limit=50）
            payload: 请求体字符串
            timestamp: 时间戳
            
        Returns:
            str: 签名字符串
        """
        # 计算payload的SHA512哈希（与旧版本完全一致）
        m = hashlib.sha512()
        m.update((payload or "").encode('utf-8'))
        hashed_payload = m.hexdigest()
        
        # 构建签名字符串（与旧版本格式完全一致）
        sign_string = '%s\n%s\n%s\n%s\n%s' % (method, uri, query_string or "", hashed_payload, timestamp)
        
        # 生成HMAC-SHA512签名
        signature = hmac.new(
            self._secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return signature

    async def request(self, method: str, uri: str, params: Optional[Dict] = None, 
                     body: Optional[Dict] = None, headers: Optional[Dict] = None, 
                     auth: bool = False) -> Tuple[Optional[Dict], Optional[Exception]]:
        """发起HTTP请求
        
        Args:
            method: HTTP方法
            uri: 请求URI
            params: 查询参数
            body: 请求体数据
            headers: 请求头
            auth: 是否需要认证
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        # 构建完整URL（self._host已包含/api/v4）
        url = self._host + uri
        # 签名时需要使用完整路径（包含/api/v4）
        sign_url = "/api/v4" + uri
        
        # 设置默认请求头
        if headers is None:
            headers = {}
        
        headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        # 处理认证
        if auth:
            if not self._key or not self._secret:
                error = Exception("API密钥和密码是必需的")
                logger.error(f"认证失败: {error}")
                return None, error
            
            # 构建查询字符串（参数需要排序，值需要转为字符串）
            query_string = ""
            if params:
                query_string = "&".join(["=".join([str(k), str(v)]) for k, v in sorted(params.items())])
            
            # 构建请求体字符串
            payload_string = ""
            if body:
                payload_string = json.dumps(body)
            
            # 生成时间戳
            timestamp = time.time()
            
            # 生成签名（使用完整路径）
            signature = self._generate_signature(method.upper(), sign_url, query_string, payload_string, str(timestamp))
            
            # 添加认证头
            headers.update({
                "KEY": self._key,
                "Timestamp": str(timestamp),
                "SIGN": signature
            })
        
        try:
            # 发起请求
            _, result, error = await AsyncHttpRequest.fetch(
                method=method,
                url=url,
                params=params,
                data=json.dumps(body) if body else None,
                headers=headers,
                timeout=30,
                proxy=self._proxy
            )
            
            if error:
                logger.error(f"请求失败: {method} {uri}, 错误: {error}")
                return None, error
            
            return result, None
            
        except Exception as e:
            logger.error(f"请求异常: {method} {uri}, 异常: {e}")
            return None, e


# 向后兼容的类名别名
GateSpot = GateSpotExchange