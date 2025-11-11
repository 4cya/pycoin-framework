# -*- coding: utf-8 -*-
"""
Binance U本位合约 REST API实现 (USDⓈ-M Futures)

支持Binance U本位永续合约交易的完整API接口，包括市场数据、交易、账户管理等功能。
API文档: https://developers.binance.com/docs/derivatives/usds-margined-futures

"""

import time
import hmac
import hashlib
from typing import Optional, Dict, Any, List, Tuple, Literal
from urllib.parse import urlencode
from utils.http_client import AsyncHttpRequest
from utils.settings import settings
from utils.log import logger


# API配置
REST_HOST = "https://fapi.binance.com"
TESTNET_HOST = "https://testnet.binancefuture.com"

# 类型定义
OrderType = Literal['LIMIT', 'MARKET', 'STOP', 'STOP_MARKET', 'TAKE_PROFIT', 'TAKE_PROFIT_MARKET', 'TRAILING_STOP_MARKET']
OrderSide = Literal['BUY', 'SELL']
PositionSide = Literal['BOTH', 'LONG', 'SHORT']
TimeInForce = Literal['GTC', 'IOC', 'FOK', 'GTX']
WorkingType = Literal['MARK_PRICE', 'CONTRACT_PRICE']
MarginType = Literal['ISOLATED', 'CROSSED']


class BinanceFuturesExchange:
    """Binance U本位合约 REST API
    
    提供Binance U本位永续合约交易的完整API接口。
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, 
                 proxy: bool = False, testnet: bool = False):
        """初始化Binance合约API客户端"""
        self._host = TESTNET_HOST if testnet else REST_HOST
        self._key = api_key
        self._secret = api_secret
        self._proxy = settings.get_proxy_config() if proxy else None
        self.recv_window = 5000

    # ========== 通用接口 ==========
    
    async def ping(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """测试连接"""
        return await self.request("GET", "/fapi/v1/ping")
    
    async def get_server_time(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取服务器时间"""
        return await self.request("GET", "/fapi/v1/time")
    
    async def get_exchange_info(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取交易规则和交易对信息"""
        return await self.request("GET", "/fapi/v1/exchangeInfo")
    
    # ========== 市场数据接口 ==========
    
    async def get_depth(self, symbol: str, limit: int = 500) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取订单簿深度"""
        params = {'symbol': symbol, 'limit': limit}
        return await self.request("GET", "/fapi/v1/depth", params=params)
    
    async def get_trades(self, symbol: str, limit: int = 500) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取最近成交记录"""
        params = {'symbol': symbol, 'limit': limit}
        return await self.request("GET", "/fapi/v1/trades", params=params)
    
    async def get_agg_trades(self, symbol: str, limit: int = 500,
                            from_id: Optional[int] = None,
                            start_time: Optional[int] = None,
                            end_time: Optional[int] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取归集成交记录"""
        params = {'symbol': symbol, 'limit': limit}
        if from_id:
            params['fromId'] = from_id
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        return await self.request("GET", "/fapi/v1/aggTrades", params=params)
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 500,
                        start_time: Optional[int] = None, 
                        end_time: Optional[int] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取K线数据"""
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        return await self.request("GET", "/fapi/v1/klines", params=params)
    
    async def get_mark_price(self, symbol: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取标记价格"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return await self.request("GET", "/fapi/v1/premiumIndex", params=params)
    
    async def get_funding_rate(self, symbol: Optional[str] = None, limit: int = 100) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取资金费率历史"""
        params = {'limit': limit}
        if symbol:
            params['symbol'] = symbol
        return await self.request("GET", "/fapi/v1/fundingRate", params=params)
    
    async def get_24h_ticker(self, symbol: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取24小时价格变动统计"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return await self.request("GET", "/fapi/v1/ticker/24hr", params=params)
    
    async def get_price(self, symbol: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取最新价格"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return await self.request("GET", "/fapi/v1/ticker/price", params=params)
    
    async def get_book_ticker(self, symbol: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取最优挂单"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return await self.request("GET", "/fapi/v1/ticker/bookTicker", params=params)
    
    # ========== 账户接口 ==========
    
    async def change_leverage(self, symbol: str, leverage: int) -> Tuple[Optional[Dict], Optional[Exception]]:
        """调整杠杆倍数"""
        params = {'symbol': symbol, 'leverage': leverage, 'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        return await self.request("POST", "/fapi/v1/leverage", params=params, auth=True)
    
    async def change_margin_type(self, symbol: str, margin_type: MarginType) -> Tuple[Optional[Dict], Optional[Exception]]:
        """变换逐全仓模式"""
        params = {'symbol': symbol, 'marginType': margin_type, 'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        return await self.request("POST", "/fapi/v1/marginType", params=params, auth=True)
    
    async def get_position_risk(self, symbol: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询持仓风险"""
        params = {'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        if symbol:
            params['symbol'] = symbol
        return await self.request("GET", "/fapi/v2/positionRisk", params=params, auth=True)
    
    async def get_account(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取账户信息"""
        params = {'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        return await self.request("GET", "/fapi/v2/account", params=params, auth=True)
    
    async def get_balance(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取账户余额"""
        params = {'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        return await self.request("GET", "/fapi/v2/balance", params=params, auth=True)
    
    # ========== 交易接口 ==========
    
    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                          quantity: Optional[float] = None, price: Optional[float] = None,
                          position_side: PositionSide = 'BOTH',
                          time_in_force: Optional[TimeInForce] = None,
                          reduce_only: bool = False,
                          stop_price: Optional[float] = None,
                          new_client_order_id: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """创建订单"""
        body = {
            'symbol': symbol, 'side': side, 'type': order_type,
            'positionSide': position_side,
            'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window
        }
        if quantity:
            body['quantity'] = self._format_number(quantity)
        if price:
            body['price'] = self._format_number(price)
        if time_in_force:
            body['timeInForce'] = time_in_force
        if reduce_only:
            body['reduceOnly'] = 'true'
        if stop_price:
            body['stopPrice'] = self._format_number(stop_price)
        if new_client_order_id:
            body['newClientOrderId'] = new_client_order_id
        return await self.request("POST", "/fapi/v1/order", body=body, auth=True)
    
    async def create_limit_order(self, symbol: str, side: OrderSide, quantity: float, price: float,
                                position_side: PositionSide = 'BOTH',
                                time_in_force: TimeInForce = 'GTC') -> Tuple[Optional[Dict], Optional[Exception]]:
        """创建限价订单"""
        return await self.create_order(symbol, side, 'LIMIT', quantity, price, position_side, time_in_force)
    
    async def create_market_order(self, symbol: str, side: OrderSide, quantity: float,
                                 position_side: PositionSide = 'BOTH') -> Tuple[Optional[Dict], Optional[Exception]]:
        """创建市价订单"""
        return await self.create_order(symbol, side, 'MARKET', quantity, position_side=position_side)
    
    async def get_order(self, symbol: str, order_id: Optional[int] = None,
                       orig_client_order_id: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询订单"""
        params = {'symbol': symbol, 'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        if order_id:
            params['orderId'] = order_id
        elif orig_client_order_id:
            params['origClientOrderId'] = orig_client_order_id
        else:
            raise ValueError("必须提供order_id或orig_client_order_id")
        return await self.request("GET", "/fapi/v1/order", params=params, auth=True)
    
    async def cancel_order(self, symbol: str, order_id: Optional[int] = None,
                          orig_client_order_id: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """取消订单"""
        params = {'symbol': symbol, 'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        if order_id:
            params['orderId'] = order_id
        elif orig_client_order_id:
            params['origClientOrderId'] = orig_client_order_id
        else:
            raise ValueError("必须提供order_id或orig_client_order_id")
        return await self.request("DELETE", "/fapi/v1/order", params=params, auth=True)
    
    async def cancel_all_orders(self, symbol: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """取消所有挂单"""
        params = {'symbol': symbol, 'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        return await self.request("DELETE", "/fapi/v1/allOpenOrders", params=params, auth=True)
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询当前挂单"""
        params = {'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        if symbol:
            params['symbol'] = symbol
        return await self.request("GET", "/fapi/v1/openOrders", params=params, auth=True)
    
    async def get_all_orders(self, symbol: str, limit: int = 500) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询所有订单"""
        params = {'symbol': symbol, 'limit': limit, 'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        return await self.request("GET", "/fapi/v1/allOrders", params=params, auth=True)
    
    async def get_my_trades(self, symbol: str, limit: int = 500) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询成交历史"""
        params = {'symbol': symbol, 'limit': limit, 'timestamp': self._get_timestamp(), 'recvWindow': self.recv_window}
        return await self.request("GET", "/fapi/v1/userTrades", params=params, auth=True)
    
    # ========== User Data Stream ==========
    
    async def create_listen_key(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """创建listenKey"""
        return await self.request("POST", "/fapi/v1/listenKey")
    
    async def keepalive_listen_key(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """延长listenKey有效期"""
        return await self.request("PUT", "/fapi/v1/listenKey")
    
    async def close_listen_key(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """关闭listenKey"""
        return await self.request("DELETE", "/fapi/v1/listenKey")
    
    # ========== 工具方法 ==========
    
    def _get_timestamp(self) -> int:
        """获取当前时间戳（毫秒）"""
        return int(time.time() * 1000)
    
    def _format_number(self, num: float) -> str:
        """格式化数字"""
        return f"{num:.8f}".rstrip('0').rstrip('.')
    
    def _generate_signature(self, query_string: str) -> str:
        """生成签名"""
        if not self._secret:
            raise ValueError("API密钥密码是必需的")
        return hmac.new(self._secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    
    async def request(self, method: str, uri: str, params: Optional[Dict] = None,
                     body: Optional[Dict] = None, headers: Optional[Dict] = None,
                     auth: bool = False) -> Tuple[Optional[Dict], Optional[Exception]]:
        """发起HTTP请求"""
        url = self._host + uri
        data = {}
        if params:
            data.update(params)
        if body:
            data.update(body)
        
        query_string = ""
        if data:
            query_string = urlencode(data)
        
        if auth:
            if not self._key or not self._secret:
                error = Exception("API密钥和密码是必需的")
                logger.error(f"认证失败: {error}")
                return None, error
            signature = self._generate_signature(query_string)
            query_string += f"&signature={signature}"
        
        if query_string:
            url += f"?{query_string}"
        
        if headers is None:
            headers = {}
        headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        })
        if self._key:
            headers["X-MBX-APIKEY"] = self._key
        
        try:
            _, result, error = await AsyncHttpRequest.fetch(
                method=method, url=url, headers=headers, timeout=30, proxy=self._proxy
            )
            if error:
                logger.error(f"请求失败: {method} {uri}, error: {error}")
                return None, error
            return result, None
        except Exception as e:
            logger.error(f"请求异常: {method} {uri}, exception: {e}")
            return None, e
