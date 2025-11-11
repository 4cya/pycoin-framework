# -*- coding: utf-8 -*-
"""
Bybit WebSocket API 实现 (V5)

支持现货和合约的公共频道和私有频道WebSocket连接。
基于utils.websocket.WebSocketClient实现，提供优雅的API设计。

API文档: https://bybit-exchange.github.io/docs/zh-TW/v5/ws/connect

"""

import time
import hmac
import hashlib
import json
import asyncio
from typing import Optional, Dict, Any, List, Callable, Union, Literal, Tuple
from utils.websocket import WebSocketClient
from utils.log import logger
from utils.settings import settings

# WebSocket连接地址配置
WEBSOCKET_HOSTS = {
    # 公共频道
    'public': {
        'spot': 'wss://stream.bybit.com/v5/public/spot',
        'linear': 'wss://stream.bybit.com/v5/public/linear',
        'inverse': 'wss://stream.bybit.com/v5/public/inverse',
        'option': 'wss://stream.bybit.com/v5/public/option'
    },
    # 私有频道
    'private': 'wss://stream.bybit.com/v5/private'
}

# 类型定义
CategoryType = Literal['spot', 'linear', 'inverse', 'option']
ChannelType = Literal['public', 'private']


class BybitWebSocketBase(WebSocketClient):
    """
    Bybit WebSocket 基础客户端
    
    提供通用的WebSocket连接管理、认证、心跳等功能。
    """
    
    def __init__(
        self,
        channel_type: ChannelType,
        category: Optional[CategoryType] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        proxy: bool = False,
        **kwargs
    ):
        """
        初始化Bybit WebSocket客户端
        
        Args:
            channel_type: 频道类型 ('public': 公共频道, 'private': 私有频道)
            category: 交易类型 ('spot': 现货, 'linear': 合约, 'inverse': 反向合约, 'option': 期权)
            api_key: API密钥（私有频道必需）
            api_secret: API密钥密码（私有频道必需）
            proxy: 是否使用代理
            **kwargs: 传递给WebSocketClient的其他参数
        """
        self._channel_type = channel_type
        self._category = category
        self._api_key = api_key
        self._api_secret = api_secret
        self._proxy = settings.get_proxy_config() if proxy else None
        
        # 构建WebSocket URL
        url = self._build_url()
        
        # 设置心跳消息
        heartbeat_msg = {"op": "ping"}
        
        # 初始化父类
        super().__init__(
            url=url,
            proxy=self._proxy,
            send_hb_interval=20,  # Bybit推荐20秒心跳
            **kwargs
        )
        
        # 设置心跳消息
        self.heartbeat_msg = heartbeat_msg
        
        # 订阅管理
        self._subscriptions: Dict[str, Callable] = {}
        self._req_id_counter = 0
    
    def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """获取代理配置信息"""
        return self._proxy
        
    def _build_url(self) -> str:
        """构建WebSocket连接URL"""
        if self._channel_type == 'private':
            return WEBSOCKET_HOSTS['private']
        else:
            if not self._category:
                raise ValueError("公共频道必须指定category参数")
            return WEBSOCKET_HOSTS['public'][self._category]
    
    def _generate_req_id(self) -> str:
        """生成请求ID"""
        self._req_id_counter += 1
        return f"req_{int(time.time())}_{self._req_id_counter}"
    
    def _generate_signature(self) -> Tuple[str, str]:
        """
        生成认证签名
        
        Returns:
            tuple: (expires, signature)
        """
        if not self._api_key or not self._api_secret:
            raise ValueError("认证需要API密钥和密码")
        
        # 生成过期时间（当前时间 + 1秒）
        expires = str(int((time.time() + 1) * 1000))
        
        # 生成签名
        signature_payload = f"GET/realtime{expires}"
        signature = hmac.new(
            self._api_secret.encode('utf-8'),
            signature_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return expires, signature
    
    async def authenticate(self) -> bool:
        """
        进行WebSocket认证
        
        Returns:
            bool: 认证成功返回True
        """
        if self._channel_type != 'private':
            logger.info("公共频道无需认证")
            return True
        
        if not self._api_key or not self._api_secret:
            logger.error("私有频道认证需要API密钥")
            return False
        
        try:
            expires, signature = self._generate_signature()
            
            auth_msg = {
                "req_id": self._generate_req_id(),
                "op": "auth",
                "args": [self._api_key, expires, signature]
            }
            
            logger.info("正在进行WebSocket认证...")
            success = await self.send_json(auth_msg)
            
            if success:
                logger.info("认证请求已发送，等待响应...")
                return True
            else:
                logger.error("认证请求发送失败")
                return False
                
        except Exception as e:
            logger.error(f"WebSocket认证异常: {e}")
            return False
    
    async def subscribe(self, topics: Union[str, List[str]], callback: Optional[Callable] = None) -> bool:
        """
        订阅频道
        
        Args:
            topics: 要订阅的主题（字符串或列表）
            callback: 数据回调函数
            
        Returns:
            bool: 订阅成功返回True
        """
        if isinstance(topics, str):
            topics = [topics]
        
        # 记录订阅回调
        if callback:
            for topic in topics:
                self._subscriptions[topic] = callback
        
        subscribe_msg = {
            "req_id": self._generate_req_id(),
            "op": "subscribe",
            "args": topics
        }
        
        logger.info(f"订阅频道: {topics}")
        success = await self.send_json(subscribe_msg)
        
        if success:
            logger.info(f"订阅请求已发送: {topics}")
        else:
            logger.error(f"订阅请求发送失败: {topics}")
        
        return success
    
    async def unsubscribe(self, topics: Union[str, List[str]]) -> bool:
        """
        取消订阅频道
        
        Args:
            topics: 要取消订阅的主题（字符串或列表）
            
        Returns:
            bool: 取消订阅成功返回True
        """
        if isinstance(topics, str):
            topics = [topics]
        
        # 移除订阅回调
        for topic in topics:
            self._subscriptions.pop(topic, None)
        
        unsubscribe_msg = {
            "req_id": self._generate_req_id(),
            "op": "unsubscribe",
            "args": topics
        }
        
        logger.info(f"取消订阅频道: {topics}")
        success = await self.send_json(unsubscribe_msg)
        
        if success:
            logger.info(f"取消订阅请求已发送: {topics}")
        else:
            logger.error(f"取消订阅请求发送失败: {topics}")
        
        return success
    
    async def on_connect(self) -> None:
        """连接成功回调"""
        logger.info(f"Bybit WebSocket连接成功: {self._channel_type}")
        
        # 私有频道需要认证
        if self._channel_type == 'private':
            await self.authenticate()
    
    async def process(self, data: Union[Dict, str]) -> None:
        """
        处理接收到的消息
        
        Args:
            data: 接收到的数据
        """
        try:
            if isinstance(data, str):
                data = json.loads(data)
            
            # 处理不同类型的消息
            if 'op' in data:
                await self._handle_operation_message(data)
            elif 'topic' in data:
                await self._handle_topic_message(data)
            else:
                logger.warning(f"未知消息格式: {data}")
                
        except Exception as e:
            logger.error(f"处理WebSocket消息异常: {e}", data=str(data)[:200])
    
    async def _handle_operation_message(self, data: Dict[str, Any]) -> None:
        """处理操作响应消息"""
        op = data.get('op')
        success = data.get('success', False)
        ret_msg = data.get('ret_msg', '')
        
        if op == 'ping':
            # 心跳响应
            logger.debug("收到心跳响应")
        elif op == 'pong':
            # 心跳响应
            logger.debug("收到心跳响应")
        elif op == 'auth':
            # 认证响应
            if success:
                logger.info("WebSocket认证成功")
            else:
                logger.error(f"WebSocket认证失败: {ret_msg}")
        elif op == 'subscribe':
            # 订阅响应
            if success:
                logger.info(f"订阅成功: {data.get('req_id', '')}")
            else:
                logger.error(f"订阅失败: {ret_msg}")
        elif op == 'unsubscribe':
            # 取消订阅响应
            if success:
                logger.info(f"取消订阅成功: {data.get('req_id', '')}")
            else:
                logger.error(f"取消订阅失败: {ret_msg}")
        else:
            logger.info(f"收到操作响应: {op}, 成功: {success}, 消息: {ret_msg}")
    
    async def _handle_topic_message(self, data: Dict[str, Any]) -> None:
        """处理主题数据消息"""
        topic = data.get('topic', '')
        
        # 查找匹配的订阅回调
        callback = None
        for subscribed_topic, cb in self._subscriptions.items():
            if topic.startswith(subscribed_topic) or subscribed_topic in topic:
                callback = cb
                break
        
        if callback:
            try:
                await callback(data)
            except Exception as e:
                logger.error(f"执行订阅回调异常: {e}", topic=topic)
        else:
            logger.debug(f"收到未订阅的主题数据: {topic}")


class BybitPublicWebSocket(BybitWebSocketBase):
    """
    Bybit 公共频道 WebSocket 客户端
    
    用于订阅行情数据，如K线、深度、成交等。
    """
    
    def __init__(
        self,
        category: CategoryType = 'linear',
        proxy: bool = False,
        **kwargs
    ):
        """
        初始化公共频道WebSocket客户端
        
        Args:
            category: 交易类型，默认为linear（合约）
            proxy: 是否使用代理
            **kwargs: 其他参数
        """
        super().__init__(
            channel_type='public',
            category=category,
            proxy=proxy,
            **kwargs
        )
    
    async def subscribe_orderbook(self, symbol: str, depth: int = 1, callback: Optional[Callable] = None) -> bool:
        """
        订阅订单簿数据
        
        Args:
            symbol: 交易对，如 'BTCUSDT'
            depth: 深度档位 (1, 50, 200)
            callback: 数据回调函数
            
        Returns:
            bool: 订阅成功返回True
        """
        topic = f"orderbook.{depth}.{symbol}"
        return await self.subscribe(topic, callback)
    
    async def subscribe_trades(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        订阅公共成交数据
        
        Args:
            symbol: 交易对，如 'BTCUSDT'
            callback: 数据回调函数
            
        Returns:
            bool: 订阅成功返回True
        """
        topic = f"publicTrade.{symbol}"
        return await self.subscribe(topic, callback)
    
    async def subscribe_kline(self, symbol: str, interval: str, callback: Optional[Callable] = None) -> bool:
        """
        订阅K线数据
        
        Args:
            symbol: 交易对，如 'BTCUSDT'
            interval: K线周期，如 '1', '5', '15', '30', '60', '240', 'D'
            callback: 数据回调函数
            
        Returns:
            bool: 订阅成功返回True
        """
        topic = f"kline.{interval}.{symbol}"
        return await self.subscribe(topic, callback)
    
    async def subscribe_ticker(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        订阅24小时价格统计
        
        Args:
            symbol: 交易对，如 'BTCUSDT'
            callback: 数据回调函数
            
        Returns:
            bool: 订阅成功返回True
        """
        topic = f"tickers.{symbol}"
        return await self.subscribe(topic, callback)


class BybitPrivateWebSocket(BybitWebSocketBase):
    """
    Bybit 私有频道 WebSocket 客户端
    
    用于订阅账户相关数据，如订单更新、持仓变化、余额变动等。
    需要API密钥进行认证。
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        proxy: bool = False,
        **kwargs
    ):
        """
        初始化私有频道WebSocket客户端
        
        Args:
            api_key: API密钥
            api_secret: API密钥密码
            proxy: 是否使用代理
            **kwargs: 其他参数
        """
        super().__init__(
            channel_type='private',
            api_key=api_key,
            api_secret=api_secret,
            proxy=proxy,
            **kwargs
        )
    
    async def subscribe_order(self, callback: Optional[Callable] = None) -> bool:
        """
        订阅订单更新
        
        Args:
            callback: 数据回调函数
            
        Returns:
            bool: 订阅成功返回True
        """
        topic = "order"
        return await self.subscribe(topic, callback)
    
    async def subscribe_position(self, callback: Optional[Callable] = None) -> bool:
        """
        订阅持仓更新
        
        Args:
            callback: 数据回调函数
            
        Returns:
            bool: 订阅成功返回True
        """
        topic = "position"
        return await self.subscribe(topic, callback)
    
    async def subscribe_execution(self, callback: Optional[Callable] = None) -> bool:
        """
        订阅成交更新
        
        Args:
            callback: 数据回调函数
            
        Returns:
            bool: 订阅成功返回True
        """
        topic = "execution"
        return await self.subscribe(topic, callback)
    
    async def subscribe_wallet(self, callback: Optional[Callable] = None) -> bool:
        """
        订阅钱包余额更新
        
        Args:
            callback: 数据回调函数
            
        Returns:
            bool: 订阅成功返回True
        """
        topic = "wallet"
        return await self.subscribe(topic, callback)


class BybitWebSocketManager:
    """
    Bybit WebSocket 管理器
    
    统一管理多个WebSocket连接，提供便捷的API。
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, proxy: bool = False):
        """
        初始化WebSocket管理器
        
        Args:
            api_key: API密钥（私有频道需要）
            api_secret: API密钥密码（私有频道需要）
            proxy: 是否使用代理
        """
        self._api_key = api_key
        self._api_secret = api_secret
        self._proxy = settings.get_proxy_config() if proxy else None
        self._connections: Dict[str, BybitWebSocketBase] = {}
    
    def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """获取代理配置信息"""
        return self._proxy
    
    def create_public_client(self, category: CategoryType = 'linear') -> BybitPublicWebSocket:
        """
        创建公共频道客户端
        
        Args:
            category: 交易类型
            
        Returns:
            BybitPublicWebSocket: 公共频道客户端
        """
        client_key = f"public_{category}"
        
        if client_key not in self._connections:
            client = BybitPublicWebSocket(
                category=category,
                proxy=bool(self._proxy)
            )
            self._connections[client_key] = client
        
        return self._connections[client_key]
    
    def create_private_client(self) -> BybitPrivateWebSocket:
        """
        创建私有频道客户端
        
        Returns:
            BybitPrivateWebSocket: 私有频道客户端
        """
        if not self._api_key or not self._api_secret:
            raise ValueError("私有频道需要API密钥")
        
        client_key = "private"
        
        if client_key not in self._connections:
            client = BybitPrivateWebSocket(
                api_key=self._api_key,
                api_secret=self._api_secret,
                proxy=bool(self._proxy)
            )
            self._connections[client_key] = client
        
        return self._connections[client_key]
    
    async def start_all(self) -> None:
        """启动所有WebSocket连接"""
        for client in self._connections.values():
            client.start()
        logger.info(f"已启动 {len(self._connections)} 个WebSocket连接")
    
    async def stop_all(self) -> None:
        """停止所有WebSocket连接"""
        for client in self._connections.values():
            await client.disconnect()
        self._connections.clear()
        logger.info("已停止所有WebSocket连接")
    
    def get_client(self, client_key: str) -> Optional[BybitWebSocketBase]:
        """
        获取指定的客户端
        
        Args:
            client_key: 客户端键名
            
        Returns:
            Optional[BybitWebSocketBase]: 客户端实例或None
        """
        return self._connections.get(client_key)


# 兼容旧版本的类名
Websocket = BybitWebSocketBase  # 向后兼容