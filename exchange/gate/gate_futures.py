# -*- coding: utf-8 -*-
"""
Gate.io 永续合约交易 REST API实现 (V4)

提供Gate.io永续合约交易的完整API接口，包括市场数据、交易、账户管理等功能。
API文档: https://www.gate.com/docs/developers/apiv4/zh_CN/#futures

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
REST_HOST = 'https://api.gateio.ws/api/v4'

# 结算货币类型
SettleType = Literal['btc', 'usdt', 'usd']


class GateFuturesExchange:
    """Gate.io 永续合约交易 REST API (V4)
    
    提供Gate.io永续合约交易的完整API接口，包括市场数据、交易、账户管理等功能。
    使用Gate.io V4 API规范。
    
    支持的结算货币：
    - btc: BTC结算
    - usdt: USDT结算 
    - usd: USD结算
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, 
                 proxy: bool = False, settle: SettleType = 'usdt'):
        """初始化Gate.io合约API客户端
        
        Args:
            api_key: API密钥（可选，仅在需要访问私有接口时提供）
            api_secret: API密钥密码（可选，仅在需要访问私有接口时提供）
            proxy: 是否使用代理
            settle: 结算货币类型，'btc', 'usdt' 或 'usd'，默认'usdt'
            
        Note:
            - 如果只使用公开的行情接口，可以不提供API密钥
            - 访问账户信息、交易等私有接口时必须提供有效的API密钥
            - 不同结算货币的合约账户是独立的
        """
        self._host = REST_HOST
        self._key = api_key
        self._secret = api_secret
        self._proxy = settings.get_proxy_config() if proxy else None
        self._settle = settle
        self.recv_window = 5000

    # ========== 市场数据接口 ==========
    
    async def get_contracts(self, contract: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取合约列表或单个合约信息
        
        Args:
            contract: 合约名称，如 'BTC_USD'，None则返回所有合约
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        if contract:
            result, error = await self.request("GET", f"/futures/{self._settle}/contracts/{contract}")
        else:
            result, error = await self.request("GET", f"/futures/{self._settle}/contracts")
        return result, error
    
    async def get_order_book(self, contract: str, interval: str = '0', limit: int = 10, 
                            with_id: bool = False) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取合约订单簿
        
        Args:
            contract: 合约名称
            interval: 订单簿深度间隔，'0'表示不合并
            limit: 返回深度数量，最大100
            with_id: 是否返回订单簿ID
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {
            "contract": contract,
            "interval": interval,
            "limit": limit
        }
        if with_id:
            params["with_id"] = "true"
            
        result, error = await self.request("GET", f"/futures/{self._settle}/order_book", params=params)
        return result, error
    
    async def get_trades(self, contract: str, limit: int = 100, last_id: Optional[str] = None,
                        from_timestamp: Optional[int] = None, to_timestamp: Optional[int] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取合约成交记录
        
        Args:
            contract: 合约名称
            limit: 返回数量，最大1000
            last_id: 指定列表从某个ID之后开始
            from_timestamp: 起始时间戳
            to_timestamp: 结束时间戳
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"contract": contract, "limit": limit}
        if last_id:
            params["last_id"] = last_id
        if from_timestamp:
            params["from"] = from_timestamp
        if to_timestamp:
            params["to"] = to_timestamp
            
        result, error = await self.request("GET", f"/futures/{self._settle}/trades", params=params)
        return result, error
    
    async def get_candlesticks(self, contract: str, interval: str = '1m', from_timestamp: Optional[int] = None,
                               to_timestamp: Optional[int] = None, limit: int = 100) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取K线数据
        
        Args:
            contract: 合约名称
            interval: K线周期，如 '1m', '5m', '15m', '30m', '1h', '4h', '1d'
            from_timestamp: 起始时间戳
            to_timestamp: 结束时间戳
            limit: 返回数量，最大10000
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"contract": contract, "interval": interval, "limit": limit}
        if from_timestamp:
            params["from"] = from_timestamp
        if to_timestamp:
            params["to"] = to_timestamp
            
        result, error = await self.request("GET", f"/futures/{self._settle}/candlesticks", params=params)
        return result, error
    
    async def get_tickers(self, contract: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取合约ticker信息
        
        Args:
            contract: 合约名称，None则返回所有合约
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {}
        if contract:
            params["contract"] = contract
            
        result, error = await self.request("GET", f"/futures/{self._settle}/tickers", params=params)
        return result, error
    
    async def get_funding_rate(self, contract: str, limit: int = 100) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取资金费率历史
        
        Args:
            contract: 合约名称
            limit: 返回数量
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"contract": contract, "limit": limit}
        result, error = await self.request("GET", f"/futures/{self._settle}/funding_rate", params=params)
        return result, error
    
    async def get_insurance(self, limit: int = 100) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取保险基金历史
        
        Args:
            limit: 返回数量
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"limit": limit}
        result, error = await self.request("GET", f"/futures/{self._settle}/insurance", params=params)
        return result, error
    
    async def get_contract_stats(self, contract: str, from_timestamp: Optional[int] = None,
                                 interval: str = '5m', limit: int = 30) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取合约统计信息
        
        Args:
            contract: 合约名称
            from_timestamp: 起始时间戳
            interval: 统计周期
            limit: 返回数量
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"contract": contract, "interval": interval, "limit": limit}
        if from_timestamp:
            params["from"] = from_timestamp
            
        result, error = await self.request("GET", f"/futures/{self._settle}/contract_stats", params=params)
        return result, error

    # ========== 账户接口 ==========
    
    async def get_account(self) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询合约账户信息"""
        result, error = await self.request("GET", f"/futures/{self._settle}/accounts", auth=True)
        return result, error
    
    async def get_account_book(self, limit: int = 100, offset: int = 0, 
                               from_timestamp: Optional[int] = None, to_timestamp: Optional[int] = None,
                               type_filter: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询账户流水
        
        Args:
            limit: 返回数量
            offset: 偏移量
            from_timestamp: 起始时间戳
            to_timestamp: 结束时间戳
            type_filter: 类型筛选
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"limit": limit, "offset": offset}
        if from_timestamp:
            params["from"] = from_timestamp
        if to_timestamp:
            params["to"] = to_timestamp
        if type_filter:
            params["type"] = type_filter
            
        result, error = await self.request("GET", f"/futures/{self._settle}/account_book", params=params, auth=True)
        return result, error
    
    async def get_positions(self, contract: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询所有持仓或指定合约持仓
        
        Args:
            contract: 合约名称，None则返回所有持仓
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {}
        if contract:
            params["contract"] = contract
            
        result, error = await self.request("GET", f"/futures/{self._settle}/positions", params=params, auth=True)
        return result, error
    
    async def update_position_margin(self, contract: str, change: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """更新持仓保证金
        
        Args:
            contract: 合约名称
            change: 保证金变化量，正数表示增加，负数表示减少
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        body = {"change": change}
        result, error = await self.request("POST", f"/futures/{self._settle}/positions/{contract}/margin", 
                                          body=body, auth=True)
        return result, error
    
    async def update_position_leverage(self, contract: str, leverage: str, 
                                       cross_leverage_limit: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """更新持仓杠杆
        
        Args:
            contract: 合约名称
            leverage: 杠杆倍数，0表示全仓
            cross_leverage_limit: 全仓最大可用保证金
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        body = {"leverage": leverage}
        if cross_leverage_limit:
            body["cross_leverage_limit"] = cross_leverage_limit
            
        result, error = await self.request("POST", f"/futures/{self._settle}/positions/{contract}/leverage",
                                          body=body, auth=True)
        return result, error
    
    async def update_position_risk_limit(self, contract: str, risk_limit: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """更新持仓风险限额
        
        Args:
            contract: 合约名称
            risk_limit: 风险限额
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        body = {"risk_limit": risk_limit}
        result, error = await self.request("POST", f"/futures/{self._settle}/positions/{contract}/risk_limit",
                                          body=body, auth=True)
        return result, error

    # ========== 交易接口 ==========
    
    async def create_order(self, contract: str, size: int, price: Optional[str] = None, 
                          iceberg: int = 0, tif: str = 'gtc', text: Optional[str] = None,
                          reduce_only: bool = False, close: bool = False, 
                          auto_size: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """创建合约订单
        
        Args:
            contract: 合约名称
            size: 数量，正数做多，负数做空
            price: 价格，None表示市价单
            iceberg: 冰山委托显示数量，0表示普通订单
            tif: Time in force，'gtc', 'ioc', 'poc'等
            text: 用户自定义信息
            reduce_only: 是否只减仓
            close: 是否平仓
            auto_size: 自动调整数量模式
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        body = {
            "contract": contract,
            "size": size,
            "iceberg": iceberg,
            "tif": tif
        }
        
        if price is not None:
            body["price"] = price
        if text:
            body["text"] = text
        if reduce_only:
            body["reduce_only"] = reduce_only
        if close:
            body["close"] = close
        if auto_size:
            body["auto_size"] = auto_size
            
        result, error = await self.request("POST", f"/futures/{self._settle}/orders", body=body, auth=True)
        return result, error
    
    async def get_orders(self, contract: str, status: str = 'open', limit: int = 100,
                        offset: int = 0, last_id: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询订单列表
        
        Args:
            contract: 合约名称
            status: 订单状态，'open' 或 'finished'
            limit: 返回数量
            offset: 偏移量
            last_id: 指定列表从某个ID之后开始
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {
            "contract": contract,
            "status": status,
            "limit": limit,
            "offset": offset
        }
        if last_id:
            params["last_id"] = last_id
            
        result, error = await self.request("GET", f"/futures/{self._settle}/orders", params=params, auth=True)
        return result, error
    
    async def cancel_orders(self, contract: str, side: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """批量取消订单
        
        Args:
            contract: 合约名称
            side: 方向，'ask' 或 'bid'，None则取消所有
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"contract": contract}
        if side:
            params["side"] = side
            
        result, error = await self.request("DELETE", f"/futures/{self._settle}/orders", params=params, auth=True)
        return result, error
    
    async def get_order(self, order_id: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取单个订单详情
        
        Args:
            order_id: 订单ID
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        result, error = await self.request("GET", f"/futures/{self._settle}/orders/{order_id}", auth=True)
        return result, error
    
    async def cancel_order(self, order_id: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """取消单个订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        result, error = await self.request("DELETE", f"/futures/{self._settle}/orders/{order_id}", auth=True)
        return result, error
    
    async def amend_order(self, order_id: str, price: Optional[str] = None,
                         size: Optional[int] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """修改订单
        
        Args:
            order_id: 订单ID
            price: 新价格
            size: 新数量
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        body = {}
        if price:
            body["price"] = price
        if size:
            body["size"] = size
            
        result, error = await self.request("PUT", f"/futures/{self._settle}/orders/{order_id}",
                                          body=body, auth=True)
        return result, error
    
    async def get_my_trades(self, contract: Optional[str] = None, order_id: Optional[str] = None,
                           limit: int = 100, offset: int = 0, last_id: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询个人成交记录
        
        Args:
            contract: 合约名称
            order_id: 订单ID
            limit: 返回数量
            offset: 偏移量
            last_id: 指定列表从某个ID之后开始
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"limit": limit, "offset": offset}
        if contract:
            params["contract"] = contract
        if order_id:
            params["order"] = order_id
        if last_id:
            params["last_id"] = last_id
            
        result, error = await self.request("GET", f"/futures/{self._settle}/my_trades", params=params, auth=True)
        return result, error
    
    async def get_position_close_history(self, contract: Optional[str] = None, limit: int = 100) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询持仓平仓历史
        
        Args:
            contract: 合约名称
            limit: 返回数量
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"limit": limit}
        if contract:
            params["contract"] = contract
            
        result, error = await self.request("GET", f"/futures/{self._settle}/position_close", params=params, auth=True)
        return result, error
    
    async def get_liquidates(self, contract: Optional[str] = None, limit: int = 100) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询强平委托历史
        
        Args:
            contract: 合约名称
            limit: 返回数量
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"limit": limit}
        if contract:
            params["contract"] = contract
            
        result, error = await self.request("GET", f"/futures/{self._settle}/liquidates", params=params, auth=True)
        return result, error

    # ========== 自动订单接口 ==========
    
    async def create_price_triggered_order(self, initial: Dict[str, Any], trigger: Dict[str, Any]) -> Tuple[Optional[Dict], Optional[Exception]]:
        """创建价格触发自动订单
        
        Args:
            initial: 初始订单信息
            trigger: 触发条件
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        body = {
            "initial": initial,
            "trigger": trigger
        }
        result, error = await self.request("POST", f"/futures/{self._settle}/price_orders", body=body, auth=True)
        return result, error
    
    async def get_price_triggered_orders(self, status: str = 'open', contract: Optional[str] = None,
                                        limit: int = 100, offset: int = 0) -> Tuple[Optional[Dict], Optional[Exception]]:
        """查询价格触发订单列表
        
        Args:
            status: 订单状态
            contract: 合约名称
            limit: 返回数量
            offset: 偏移量
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"status": status, "limit": limit, "offset": offset}
        if contract:
            params["contract"] = contract
            
        result, error = await self.request("GET", f"/futures/{self._settle}/price_orders", params=params, auth=True)
        return result, error
    
    async def cancel_price_triggered_orders(self, contract: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """取消所有价格触发订单
        
        Args:
            contract: 合约名称
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        params = {"contract": contract}
        result, error = await self.request("DELETE", f"/futures/{self._settle}/price_orders", params=params, auth=True)
        return result, error
    
    async def get_price_triggered_order(self, order_id: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """获取单个价格触发订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        result, error = await self.request("GET", f"/futures/{self._settle}/price_orders/{order_id}", auth=True)
        return result, error
    
    async def cancel_price_triggered_order(self, order_id: str) -> Tuple[Optional[Dict], Optional[Exception]]:
        """取消单个价格触发订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            Tuple[Optional[Dict], Optional[Exception]]: (结果数据, 错误信息)
        """
        result, error = await self.request("DELETE", f"/futures/{self._settle}/price_orders/{order_id}", auth=True)
        return result, error

    # ========== 内部方法 ==========
    
    def _generate_signature(self, method: str, uri: str, query_string: str, 
                           payload: str, timestamp: str) -> str:
        """生成请求签名
        
        Gate.io签名算法：
        1. 计算payload的SHA512哈希
        2. 构建签名字符串：{METHOD}\n{URI}\n{QUERY_STRING}\n{HASHED_PAYLOAD}\n{TIMESTAMP}
        3. 使用HMAC-SHA512生成签名
        
        Args:
            method: HTTP方法
            uri: 请求URI
            query_string: 查询字符串
            payload: 请求体
            timestamp: 时间戳
            
        Returns:
            str: 签名字符串
        """
        # 计算payload的SHA512哈希
        m = hashlib.sha512()
        m.update((payload or "").encode('utf-8'))
        hashed_payload = m.hexdigest()
        
        # 构建签名字符串
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
            
            # 添加认证请求头
            headers.update({
                "KEY": self._key,
                "SIGN": signature,
                "Timestamp": str(timestamp)
            })
        
        # 发起请求
        try:
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
                logger.error(f"请求失败: {method} {url}, error: {error}")
                return None, error
            
            # 处理返回结果
            if isinstance(result, dict) and 'label' in result:
                # Gate.io错误响应
                error_msg = result.get('message', result.get('detail', 'Unknown error'))
                error = Exception(f"{result['label']}: {error_msg}")
                logger.error(f"API错误: {error}")
                return None, error
            
            return result, None
            
        except Exception as e:
            logger.error(f"请求异常: {method} {url}, exception: {e}")
            return None, e


# 向后兼容的别名
GateFutures = GateFuturesExchange
