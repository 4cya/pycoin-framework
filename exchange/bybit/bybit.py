# -*- coding: utf-8 -*-
"""
Bybit 统一账户 REST API实现 (V5)

支持现货(spot)和合约(linear)交易，使用统一账户体系。
API文档: https://bybit-exchange.github.io/docs/v5/intro

"""

import time
import hmac
import hashlib
import json
from typing import Optional, Dict, Any, List, Tuple, Literal
from urllib.parse import urlencode
from utils.http_client import AsyncHttpRequest
from utils.settings import settings
from utils.log import logger


# API配置
REST_HOST = "https://api.bybit.com"

# WebSocket配置 - 根据交易类型动态选择
WEBSOCKET_HOSTS = {
    'spot': "wss://stream.bybit.com/v5/public/spot",
    'linear': "wss://stream.bybit.com/v5/public/linear"
}
WEBSOCKET_TRADE_HOST = "wss://stream.bybit.com/v5/private"

# 交易类型定义
CategoryType = Literal['spot', 'linear']


class BybitExchange:
    """Bybit 统一账户 REST API (V5)
    
    提供Bybit现货和合约交易的完整API接口，包括市场数据、交易、账户管理等功能。
    使用Bybit V5 API规范和统一账户体系。
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, 
                 category: CategoryType = 'linear', proxy: bool = False):
        """初始化Bybit统一账户API客户端
        
        Args:
            api_key: API密钥（可选，仅在需要访问私有接口时提供）
            api_secret: API密钥密码（可选，仅在需要访问私有接口时提供）
            category: 默认交易类型 ('spot': 现货, 'linear': 合约)，默认为合约交易
            proxy: 是否使用代理
            
        Note:
            - 如果只使用公开的行情接口，可以不提供API密钥
            - 访问账户信息、交易等私有接口时必须提供有效的API密钥
            - 默认使用合约交易(linear)，可在方法调用时临时指定其他交易类型
        """
        self._host = REST_HOST
        self._key = api_key
        self._secret = api_secret
        self._default_category = category
        self._proxy = settings.get_proxy_config() if proxy else None
        self.recv_window = 5000

    def _get_category(self, category: Optional[CategoryType] = None) -> CategoryType:
        """获取交易类型，优先使用传入参数，否则使用默认值"""
        return category if category is not None else self._default_category

    def get_websocket_host(self, category: Optional[CategoryType] = None) -> str:
        """获取WebSocket连接地址"""
        cat = self._get_category(category)
        return WEBSOCKET_HOSTS.get(cat, WEBSOCKET_HOSTS['linear'])

    # ========== 市场数据接口 ==========
    
    async def get_server_time(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取服务器时间"""
        result, error = await self.request("GET", "/v5/market/time")
        return result, error
    
    async def get_symbols(self, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取所有交易对信息
        
        Args:
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        params = {'category': self._get_category(category)}
        result, error = await self.request("GET", "/v5/market/instruments-info", params=params)
        return result, error

    async def get_depth(self, symbol: str, limit: int = 50, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取订单簿深度
        
        Args:
            symbol: 交易对
            limit: 深度档位 (1,50,200)
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        params = {
            'category': self._get_category(category),
            'symbol': symbol,
            'limit': limit
        }
        result, error = await self.request("GET", "/v5/market/orderbook", params=params)
        return result, error

    async def get_trades(self, symbol: str, limit: int = 60, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取最近成交记录
        
        Args:
            symbol: 交易对
            limit: 返回数量，默认60
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        params = {
            'category': self._get_category(category),
            'symbol': symbol,
            'limit': limit
        }
        result, error = await self.request("GET", "/v5/market/recent-trade", params=params)
        return result, error

    async def get_klines(self, symbol: str, interval: str, limit: int = 200, 
                        start_time: Optional[int] = None, end_time: Optional[int] = None, 
                        category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取K线数据
        
        Args:
            symbol: 交易对
            interval: K线周期 (1,3,5,15,30,60,120,240,360,720,D,W,M)
            limit: 返回数量，默认200
            start_time: 开始时间戳(毫秒)
            end_time: 结束时间戳(毫秒)
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        params = {
            'category': self._get_category(category),
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if start_time:
            params['start'] = start_time
        if end_time:
            params['end'] = end_time
            
        result, error = await self.request("GET", "/v5/market/kline", params=params)
        return result, error

    async def get_24h_ticker(self, symbol: Optional[str] = None, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取24小时价格变动统计
        
        Args:
            symbol: 交易对，为空则返回所有交易对
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        params = {'category': self._get_category(category)}
        if symbol:
            params['symbol'] = symbol
        result, error = await self.request("GET", "/v5/market/tickers", params=params)
        return result, error

    async def get_tickers(self, symbol: Optional[str] = None, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取价格行情信息
        
        Args:
            symbol: 交易对，为空则返回所有交易对
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        return await self.get_24h_ticker(symbol, category)

    # ========== 账户接口 ==========
    
    async def get_account_info(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取账户信息"""
        params = {'accountType': 'UNIFIED'}
        result, error = await self.request('GET', '/v5/account/wallet-balance', params=params, auth=True)
        return result, error
    
    # ========== 交易接口 ==========
    
    async def create_order(self, symbol: str, side: str, order_type: str, quantity: float,
                          price: Optional[float] = None, time_in_force: str = 'GTC', 
                          client_order_id: Optional[str] = None, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """创建订单
        
        Args:
            symbol: 交易对
            side: 方向 (Buy/Sell)
            order_type: 订单类型 (Market/Limit)
            quantity: 数量
            price: 价格(限价单必需)
            time_in_force: 时效性 (GTC/IOC/FOK)
            client_order_id: 客户端订单ID
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        body = {
            'category': self._get_category(category),
            'symbol': symbol,
            'side': side,
            'orderType': order_type,
            'qty': str(quantity),
            'timeInForce': time_in_force
        }
        
        if price:
            body['price'] = str(price)
        if client_order_id:
            body['orderLinkId'] = client_order_id
        
        result, error = await self.request('POST', '/v5/order/create', body=body, auth=True)
        return result, error
    
    async def create_limit_order(self, symbol: str, side: str, quantity: float, price: float,
                                time_in_force: str = 'GTC', client_order_id: Optional[str] = None, 
                                category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """创建限价订单
        
        Args:
            symbol: 交易对
            side: 方向 (Buy/Sell)
            quantity: 数量
            price: 价格
            time_in_force: 时效性 (GTC/IOC/FOK)
            client_order_id: 客户端订单ID
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        return await self.create_order(symbol, side, 'Limit', quantity, price, time_in_force, client_order_id, category)

    async def create_market_order(self, symbol: str, side: str, quantity: float,
                                 client_order_id: Optional[str] = None, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """创建市价订单
        
        Args:
            symbol: 交易对
            side: 方向 (Buy/Sell)
            quantity: 数量
            client_order_id: 客户端订单ID
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        return await self.create_order(symbol, side, 'Market', quantity, None, 'GTC', client_order_id, category)

    async def get_order(self, symbol: str, order_id: Optional[str] = None, 
                       orderLinkId: Optional[str] = None, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询订单
        
        Args:
            symbol: 交易对
            order_id: 订单ID
            orderLinkId: 客户端订单ID
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        params = {
            'category': self._get_category(category),
            'symbol': symbol
        }
        
        if order_id:
            params['orderId'] = order_id
        elif orderLinkId:
            params['orderLinkId'] = orderLinkId
        
        result, error = await self.request('GET', '/v5/order/realtime', params=params, auth=True)
        return result, error

    async def cancel_order(self, symbol: str, order_id: Optional[str] = None, 
                          orderLinkId: Optional[str] = None, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """取消订单
        
        Args:
            symbol: 交易对
            order_id: 订单ID
            orderLinkId: 客户端订单ID
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        body = {
            'category': self._get_category(category),
            'symbol': symbol
        }
        
        if order_id:
            body['orderId'] = order_id
        elif orderLinkId:
            body['orderLinkId'] = orderLinkId
        else:
            raise ValueError("必须提供order_id或orderLinkId")
        
        result, error = await self.request('POST', '/v5/order/cancel', body=body, auth=True)
        return result, error
    
    async def cancel_all_orders(self, symbol: Optional[str] = None, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """取消所有订单
        
        Args:
            symbol: 交易对（可选）
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        body = {'category': self._get_category(category)}
        if symbol:
            body['symbol'] = symbol
        
        result, error = await self.request('POST', '/v5/order/cancel-all', body=body, auth=True)
        return result, error

    async def get_open_orders(self, symbol: Optional[str] = None, limit: int = 50, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询当前委托
        
        Args:
            symbol: 交易对
            limit: 数量
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        params = {
            'category': self._get_category(category),
            'limit': limit
        }
        if symbol:
            params['symbol'] = symbol
        
        result, error = await self.request('GET', '/v5/order/realtime', params=params, auth=True)
        return result, error
    
    async def get_order_history(self, symbol: Optional[str] = None, limit: int = 50, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询历史订单
        
        Args:
            symbol: 交易对
            limit: 数量
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        params = {
            'category': self._get_category(category),
            'limit': limit
        }
        if symbol:
            params['symbol'] = symbol
        
        result, error = await self.request('GET', '/v5/order/history', params=params, auth=True)
        return result, error
    
    async def get_trade_history(self, symbol: Optional[str] = None, limit: int = 50, category: Optional[CategoryType] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询成交历史
        
        Args:
            symbol: 交易对
            limit: 数量
            category: 交易类型 ('spot': 现货, 'linear': 合约)，默认使用初始化时的设置
        """
        params = {
            'category': self._get_category(category),
            'limit': limit
        }
        if symbol:
            params['symbol'] = symbol
        
        result, error = await self.request('GET', '/v5/execution/list', params=params, auth=True)
        return result, error

    async def request(self, method: str, uri: str, params: Optional[Dict[str, Any]] = None,
                     body: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, 
                     auth: bool = False) -> Tuple[Optional[Dict], Optional[Exception]]:
        """发起HTTP请求 (V5 API)
        
        Args:
            method: 请求方法 (GET/POST/PUT/DELETE)
            uri: API端点
            params: URL查询参数
            body: 请求体数据
            headers: 请求头
            auth: 是否需要签名认证
            
        Returns:
            (response_data, error)
        """
        # 构建完整URL
        url = self._host + uri
        
        # 初始化请求头
        if headers is None:
            headers = {}
        
        headers['Content-Type'] = 'application/json'
        
        # 如果需要认证，添加V5 API签名
        if auth:
            if not self._key or not self._secret:
                error = Exception("需要API密钥才能进行签名请求")
                logger.error(str(error))
                return None, error
            
            # V5 API签名逻辑
            timestamp = str(int(time.time() * 1000))
            headers['X-BAPI-API-KEY'] = self._key
            headers['X-BAPI-TIMESTAMP'] = timestamp
            headers['X-BAPI-RECV-WINDOW'] = str(self.recv_window)
            
            # 生成签名
            if method.upper() == 'GET':
                param_str = urlencode(sorted(params.items())) if params else ''
            else:
                param_str = json.dumps(body) if body else ''
            
            sign_str = f"{timestamp}{self._key}{self.recv_window}{param_str}"
            signature = hmac.new(
                self._secret.encode('utf-8'),
                sign_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            headers['X-BAPI-SIGN'] = signature
        
        # 发起请求
        try:
            if method.upper() == 'GET':
                status, response, error = await AsyncHttpRequest.fetch(
                    method=method, 
                    url=url, 
                    params=params,
                    headers=headers, 
                    timeout=10, 
                    proxy=self._proxy
                )
            else:
                status, response, error = await AsyncHttpRequest.fetch(
                    method=method, 
                    url=url, 
                    json=body,
                    headers=headers, 
                    timeout=10, 
                    proxy=self._proxy
                )
            
            if error:
                logger.error(
                    f"Bybit API请求失败: {method} {uri}",
                    status=status,
                    error=str(error)
                )
                return None, error
            
            # 检查API响应是否成功
            if isinstance(response, dict):
                ret_code = response.get('retCode')
                if ret_code and ret_code != 0:
                    error_msg = response.get('retMsg', f'API错误代码: {ret_code}')
                    api_error = Exception(f"Bybit API错误: {error_msg}")
                    logger.error(f"Bybit API业务错误: {method} {uri}", error=error_msg)
                    return None, api_error
            
            return response, None
            
        except Exception as e:
            logger.error(f"Bybit API请求异常: {method} {uri}", error=str(e))
            return None, e

    def get_timestamp(self) -> int:
        """获取当前时间戳（毫秒）"""
        return int(time.time() * 1000)
    
    async def close(self):
        """关闭HTTP连接"""
        try:
            await AsyncHttpRequest.close_all()
        except Exception as e:
            logger.warning(f"关闭HTTP连接时出错: {e}")
