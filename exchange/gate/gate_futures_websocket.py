# -*- coding: utf-8 -*-
"""
Gate.io 永续合约 WebSocket API 实现 (V4)

支持永续合约交易的公共频道和私有频道WebSocket连接。
基于utils.websocket.WebSocketClient实现，提供优雅的API设计。

API文档: https://www.gate.com/docs/developers/apiv4/ws/zh_CN/

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
    'btc': 'wss://fx-ws.gateio.ws/v4/ws/btc',
    'usdt': 'wss://fx-ws.gateio.ws/v4/ws/usdt',
    'usd': 'wss://fx-ws.gateio.ws/v4/ws/usd'
}

# 类型定义
ChannelType = Literal['public', 'private']
SettleType = Literal['btc', 'usdt', 'usd']


class GateFuturesWebSocketBase(WebSocketClient):
    """
    Gate.io 永续合约 WebSocket 基础客户端
    
    提供通用的WebSocket连接管理、认证、心跳等功能。
    """
    
    def __init__(
        self,
        channel_type: ChannelType,
        settle: SettleType = 'usdt',
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        proxy: bool = False,
        **kwargs
    ):
        """
        初始化Gate.io合约WebSocket客户端
        
        Args:
            channel_type: 频道类型 ('public': 公共频道, 'private': 私有频道)
            settle: 结算货币 ('btc', 'usdt', 'usd')
            api_key: API密钥（私有频道必需）
            api_secret: API密钥密码（私有频道必需）
            proxy: 是否使用代理
            **kwargs: 传递给WebSocketClient的其他参数
        """
        self._channel_type = channel_type
        self._settle = settle
        self._api_key = api_key
        self._api_secret = api_secret
        self._proxy = settings.get_proxy_config() if proxy else None
        
        # 构建 WebSocket URL
        url = WEBSOCKET_HOSTS.get(settle, WEBSOCKET_HOSTS['usdt'])
        
        # 初始化父类
        super().__init__(
            url=url,
            proxy=self._proxy,
            send_hb_interval=30,  # Gate.io推荐30秒心跳
            **kwargs
        )
        
        # 设置心跳消息（Gate.io使用futures.ping）
        # 注意：心跳消息的时间戳需要动态生成
        self.heartbeat_msg = None
        
        # 订阅管理
        self._subscriptions: Dict[str, Callable] = {}
        self._req_id_counter = 0
        
        # 认证状态
        self._authenticated = False
    
    def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """获取代理配置信息"""
        return self._proxy
    
    def _generate_auth_signature(self, channel: str, event: str, timestamp: int) -> str:
        """
        生成认证签名
        
        Gate.io WebSocket认证签名格式:
        channel=<channel>&event=<event>&time=<time>
        
        Args:
            channel: 频道名称
            event: 事件类型
            timestamp: 时间戳
            
        Returns:
            str: 签名字符串
        """
        if not self._api_secret:
            raise ValueError("API密钥密码是必需的")
        
        # 构建签名字符串
        sign_string = f"channel={channel}&event={event}&time={timestamp}"
        
        # 生成HMAC-SHA512签名
        signature = hmac.new(
            self._api_secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return signature
    
    def _get_next_req_id(self) -> int:
        """获取下一个请求ID"""
        self._req_id_counter += 1
        return self._req_id_counter
    
    async def _send_heartbeat(self):
        """发送心跳消息（重写基类方法）"""
        try:
            if self._ws and not self._ws.closed:
                # Gate.io心跳消息需要动态时间戳
                heartbeat_msg = {
                    "time": int(time.time()),
                    "channel": "futures.ping",
                    "event": "subscribe"
                }
                await self.send_json(heartbeat_msg)
                logger.debug("已发送心跳消息")
        except Exception as e:
            logger.error(f"发送心跳失败: {e}")
    
    async def _authenticate(self) -> bool:
        """
        执行WebSocket认证
        
        Returns:
            bool: 认证是否成功
        """
        if self._channel_type != 'private':
            return True
            
        if not self._api_key or not self._api_secret:
            logger.error("私有频道需要API密钥和密码")
            return False
        
        try:
            timestamp = int(time.time())
            signature = self._generate_auth_signature("futures.login", "subscribe", timestamp)
            
            auth_msg = {
                "time": timestamp,
                "id": self._get_next_req_id(),
                "channel": "futures.login",
                "event": "subscribe",
                "auth": {
                    "method": "api_key",
                    "KEY": self._api_key,
                    "SIGN": signature
                }
            }
            
            await self.send_json(auth_msg)
            logger.info("已发送认证请求")
            return True
            
        except Exception as e:
            logger.error(f"认证失败: {e}")
            return False
    
    async def start(self):
        """启动WebSocket连接"""
        try:
            logger.info(f"开始连接Gate.io合约WebSocket: {self._url}")
            logger.info(f"结算货币: {self._settle}")
            logger.info(f"代理配置: {self._proxy}")
            
            # 调用父类的start方法（非异步）
            super().start()
            
            # 等待连接建立
            max_wait = 15  # 增加到15秒等待时间
            logger.info("等待WebSocket连接建立...")
            
            for i in range(max_wait * 10):  # 每100ms检查一次
                if self.is_connected:
                    logger.info("WebSocket连接已建立")
                    break
                await asyncio.sleep(0.1)
                if i % 20 == 0:  # 每2秒输出一次状态
                    logger.info(f"等待连接... 状态: {self._state.value} ({i/10:.1f}s)")
            else:
                logger.error(f"WebSocket连接超时，当前状态: {self._state.value}")
                logger.error("可能的原因: 1.网络问题 2.代理配置问题 3.Gate.io服务不可用")
                raise Exception("WebSocket连接超时")
                
            logger.info(f"Gate.io合约WebSocket连接成功: {self._url}")
            
        except Exception as e:
            logger.error(f"启动WebSocket连接失败: {e}")
            raise
    
    async def stop(self):
        """停止WebSocket连接"""
        try:
            # 取消心跳任务
            if hasattr(self, '_check_task_id') and self._check_task_id:
                from utils.heartbeat import heartbeat
                heartbeat.unregister(self._check_task_id)
                
            if hasattr(self, '_heartbeat_task_id') and self._heartbeat_task_id:
                from utils.heartbeat import heartbeat
                heartbeat.unregister(self._heartbeat_task_id)
            
            # 断开连接
            await self.disconnect()
            
            logger.info("Gate.io合约WebSocket连接已停止")
            
        except Exception as e:
            logger.error(f"停止WebSocket连接失败: {e}")
    
    async def send_json(self, data: Dict[str, Any]):
        """发送JSON消息"""
        try:
            if self._ws and not self._ws.closed:
                await self._ws.send_str(json.dumps(data))
            else:
                logger.warning("WebSocket未连接，无法发送消息")
        except Exception as e:
            logger.error(f"发送JSON消息失败: {e}")
    
    async def on_connect(self):
        """连接成功回调（WebSocketClient基类回调）"""
        logger.info(f"Gate.io合约WebSocket已连接: {self._url}")
        
        # 如果是私有频道，执行认证
        if self._channel_type == 'private':
            await self._authenticate()
    
    async def process(self, message: Union[Dict[str, Any], str]):
        """处理接收到的消息（WebSocketClient基类要求实现）"""
        try:
            # 如果是字符串，尝试解析为字典
            if isinstance(message, str):
                try:
                    message = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning(f"无法解析消息: {message}")
                    return
            
            # 确保message是字典类型
            if not isinstance(message, dict):
                logger.warning(f"消息格式不正确: {type(message)}")
                return
            
            # 处理认证响应
            if message.get('channel') == 'futures.login':
                if message.get('error'):
                    logger.error(f"认证失败: {message['error']}")
                    self._authenticated = False
                else:
                    logger.info("认证成功")
                    self._authenticated = True
                return
            
            # 处理心跳响应
            if message.get('channel') == 'futures.pong':
                logger.debug("收到心跳响应")
                return
            
            # 处理订阅响应
            if message.get('event') in ['subscribe', 'unsubscribe']:
                if message.get('error'):
                    logger.error(f"订阅操作失败: {message['error']}")
                else:
                    logger.info(f"订阅操作成功: {message.get('channel')}")
                return
            
            # 处理数据更新
            if message.get('event') == 'update':
                channel = message.get('channel')
                if channel in self._subscriptions:
                    callback = self._subscriptions[channel]
                    if callback:
                        try:
                            await callback(message.get('result'))
                        except Exception as e:
                            logger.error(f"回调函数执行失败 {channel}: {e}")
                else:
                    logger.debug(f"收到未订阅频道的数据: {channel}")
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
    
    async def on_disconnect(self):
        """断开连接回调（WebSocketClient基类回调）"""
        logger.warning("Gate.io合约WebSocket连接已断开")
        self._authenticated = False
    
    async def subscribe(
        self, 
        channel: str, 
        payload: Optional[List] = None,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅频道
        
        Args:
            channel: 频道名称
            payload: 订阅参数
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功发送
        """
        try:
            # 检查私有频道认证状态
            if self._channel_type == 'private' and not self._authenticated:
                logger.error("私有频道未认证，无法订阅")
                return False
            
            timestamp = int(time.time())
            req_id = self._get_next_req_id()
            
            subscribe_msg = {
                "time": timestamp,
                "id": req_id,
                "channel": channel,
                "event": "subscribe"
            }
            
            # 添加payload参数
            if payload is not None:
                subscribe_msg["payload"] = payload
            
            # 私有频道需要认证信息
            if self._channel_type == 'private':
                signature = self._generate_auth_signature(channel, "subscribe", timestamp)
                subscribe_msg["auth"] = {
                    "method": "api_key",
                    "KEY": self._api_key,
                    "SIGN": signature
                }
            
            # 注册回调函数
            if callback:
                self._subscriptions[channel] = callback
            
            await self.send_json(subscribe_msg)
            logger.info(f"已发送订阅请求: {channel}")
            return True
            
        except Exception as e:
            logger.error(f"订阅失败 {channel}: {e}")
            return False
    
    async def unsubscribe(
        self, 
        channel: str, 
        payload: Optional[List] = None
    ) -> bool:
        """
        取消订阅频道
        
        Args:
            channel: 频道名称
            payload: 取消订阅参数
            
        Returns:
            bool: 取消订阅是否成功发送
        """
        try:
            timestamp = int(time.time())
            req_id = self._get_next_req_id()
            
            unsubscribe_msg = {
                "time": timestamp,
                "id": req_id,
                "channel": channel,
                "event": "unsubscribe"
            }
            
            # 添加payload参数
            if payload is not None:
                unsubscribe_msg["payload"] = payload
            
            # 私有频道需要认证信息
            if self._channel_type == 'private':
                signature = self._generate_auth_signature(channel, "unsubscribe", timestamp)
                unsubscribe_msg["auth"] = {
                    "method": "api_key",
                    "KEY": self._api_key,
                    "SIGN": signature
                }
            
            # 移除回调函数
            if channel in self._subscriptions:
                del self._subscriptions[channel]
            
            await self.send_json(unsubscribe_msg)
            logger.info(f"已发送取消订阅请求: {channel}")
            return True
            
        except Exception as e:
            logger.error(f"取消订阅失败 {channel}: {e}")
            return False


class GateFuturesPublicWebSocket(GateFuturesWebSocketBase):
    """
    Gate.io 永续合约公共频道 WebSocket 客户端
    
    支持ticker、深度、成交记录、K线等公共数据订阅。
    """
    
    def __init__(self, settle: SettleType = 'usdt', proxy: bool = False, **kwargs):
        """
        初始化公共频道WebSocket客户端
        
        Args:
            settle: 结算货币
            proxy: 是否使用代理
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(
            channel_type='public',
            settle=settle,
            proxy=proxy,
            **kwargs
        )
    
    async def subscribe_tickers(
        self, 
        contracts: List[str], 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅ticker数据
        
        Args:
            contracts: 合约列表，如 ['BTC_USD', 'ETH_USD']
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        return await self.subscribe("futures.tickers", contracts, callback)
    
    async def subscribe_trades(
        self, 
        contracts: List[str], 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅成交记录
        
        Args:
            contracts: 合约列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        return await self.subscribe("futures.trades", contracts, callback)
    
    async def subscribe_candlesticks(
        self, 
        interval: str,
        contract: str,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅K线数据
        
        Args:
            interval: K线周期，如 '1m', '5m', '15m', '1h', '4h', '1d'
            contract: 合约名称
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [interval, contract]
        return await self.subscribe("futures.candlesticks", payload, callback)
    
    async def subscribe_order_book(
        self, 
        contract: str,
        level: str = "20",
        interval: str = "100ms",
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅订单簿深度
        
        Args:
            contract: 合约名称
            level: 深度层级 ('5', '10', '20', '50', '100')
            interval: 更新频率 ('100ms', '1000ms')
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [contract, level, interval]
        return await self.subscribe("futures.order_book", payload, callback)
    
    async def subscribe_order_book_update(
        self, 
        contract: str,
        interval: str = "100ms",
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅订单簿增量更新
        
        Args:
            contract: 合约名称
            interval: 更新频率 ('100ms', '1000ms')
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [contract, interval]
        return await self.subscribe("futures.order_book_update", payload, callback)
    
    async def subscribe_book_ticker(
        self, 
        contracts: List[str], 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅最优买卖价
        
        Args:
            contracts: 合约列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        return await self.subscribe("futures.book_ticker", contracts, callback)


class GateFuturesPrivateWebSocket(GateFuturesWebSocketBase):
    """
    Gate.io 永续合约私有频道 WebSocket 客户端
    
    支持订单、余额、持仓等私有数据订阅。
    """
    
    def __init__(
        self, 
        api_key: str, 
        api_secret: str, 
        settle: SettleType = 'usdt',
        proxy: bool = False,
        **kwargs
    ):
        """
        初始化私有频道WebSocket客户端
        
        Args:
            api_key: API密钥
            api_secret: API密钥密码
            settle: 结算货币
            proxy: 是否使用代理
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(
            channel_type='private',
            settle=settle,
            api_key=api_key,
            api_secret=api_secret,
            proxy=proxy,
            **kwargs
        )
    
    async def subscribe_orders(
        self, 
        user_id: str,
        contracts: Optional[List[str]] = None, 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅订单更新
        
        Args:
            user_id: 用户ID
            contracts: 合约列表，None表示订阅所有合约（使用['!all']）
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [user_id] + (contracts if contracts else ["!all"])
        return await self.subscribe("futures.orders", payload, callback)
    
    async def subscribe_user_trades(
        self, 
        user_id: str,
        contracts: Optional[List[str]] = None, 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅用户成交记录
        
        Args:
            user_id: 用户ID
            contracts: 合约列表，None表示订阅所有合约
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [user_id] + (contracts if contracts else ["!all"])
        return await self.subscribe("futures.usertrades", payload, callback)
    
    async def subscribe_liquidates(
        self, 
        user_id: str,
        contracts: Optional[List[str]] = None, 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅强平通知
        
        Args:
            user_id: 用户ID
            contracts: 合约列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [user_id] + (contracts if contracts else ["!all"])
        return await self.subscribe("futures.liquidates", payload, callback)
    
    async def subscribe_auto_deleverages(
        self, 
        user_id: str,
        contracts: Optional[List[str]] = None, 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅自动减仓通知
        
        Args:
            user_id: 用户ID
            contracts: 合约列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [user_id] + (contracts if contracts else ["!all"])
        return await self.subscribe("futures.auto_deleverages", payload, callback)
    
    async def subscribe_position_closes(
        self, 
        user_id: str,
        contracts: Optional[List[str]] = None, 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅平仓通知
        
        Args:
            user_id: 用户ID
            contracts: 合约列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [user_id] + (contracts if contracts else ["!all"])
        return await self.subscribe("futures.position_closes", payload, callback)
    
    async def subscribe_balances(
        self, 
        user_id: str,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅账户余额更新
        
        Args:
            user_id: 用户ID
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        return await self.subscribe("futures.balances", [user_id], callback)
    
    async def subscribe_reduce_risk_limits(
        self, 
        user_id: str,
        contracts: Optional[List[str]] = None, 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅风险限额调整通知
        
        Args:
            user_id: 用户ID
            contracts: 合约列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [user_id] + (contracts if contracts else ["!all"])
        return await self.subscribe("futures.reduce_risk_limits", payload, callback)
    
    async def subscribe_positions(
        self, 
        user_id: str,
        contracts: Optional[List[str]] = None, 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅持仓更新
        
        Args:
            user_id: 用户ID
            contracts: 合约列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [user_id] + (contracts if contracts else ["!all"])
        return await self.subscribe("futures.positions", payload, callback)
    
    async def subscribe_autoorders(
        self, 
        user_id: str,
        contracts: Optional[List[str]] = None, 
        callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅自动订单更新
        
        Args:
            user_id: 用户ID
            contracts: 合约列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        payload = [user_id] + (contracts if contracts else ["!all"])
        return await self.subscribe("futures.autoorders", payload, callback)


class GateFuturesWebSocketManager:
    """
    Gate.io 永续合约 WebSocket 管理器
    
    统一管理公共和私有WebSocket连接，提供简化的API接口。
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        settle: SettleType = 'usdt',
        proxy: bool = False
    ):
        """
        初始化WebSocket管理器
        
        Args:
            api_key: API密钥（私有频道需要）
            api_secret: API密钥密码（私有频道需要）
            settle: 结算货币
            proxy: 是否使用代理
        """
        self._api_key = api_key
        self._api_secret = api_secret
        self._settle = settle
        self._proxy = proxy
        
        # WebSocket客户端实例
        self._public_client: Optional[GateFuturesPublicWebSocket] = None
        self._private_client: Optional[GateFuturesPrivateWebSocket] = None
        
        # 连接状态
        self._public_connected = False
        self._private_connected = False
    
    async def start_public_client(self) -> GateFuturesPublicWebSocket:
        """
        启动公共频道客户端
        
        Returns:
            GateFuturesPublicWebSocket: 公共频道客户端实例
        """
        if not self._public_client:
            self._public_client = GateFuturesPublicWebSocket(
                settle=self._settle,
                proxy=self._proxy
            )
        
        if not self._public_connected:
            await self._public_client.start()
            self._public_connected = True
            logger.info("合约公共频道WebSocket已启动")
        
        return self._public_client
    
    async def start_private_client(self) -> GateFuturesPrivateWebSocket:
        """
        启动私有频道客户端
        
        Returns:
            GateFuturesPrivateWebSocket: 私有频道客户端实例
            
        Raises:
            ValueError: 当API密钥未配置时
        """
        if not self._api_key or not self._api_secret:
            raise ValueError("私有频道需要API密钥和密码")
        
        if not self._private_client:
            self._private_client = GateFuturesPrivateWebSocket(
                api_key=self._api_key,
                api_secret=self._api_secret,
                settle=self._settle,
                proxy=self._proxy
            )
        
        if not self._private_connected:
            await self._private_client.start()
            self._private_connected = True
            logger.info("合约私有频道WebSocket已启动")
        
        return self._private_client
    
    async def stop_all(self):
        """停止所有WebSocket连接"""
        if self._public_client and self._public_connected:
            await self._public_client.stop()
            self._public_connected = False
            logger.info("合约公共频道WebSocket已停止")
        
        if self._private_client and self._private_connected:
            await self._private_client.stop()
            self._private_connected = False
            logger.info("合约私有频道WebSocket已停止")
    
    @property
    def public_client(self) -> Optional[GateFuturesPublicWebSocket]:
        """获取公共频道客户端"""
        return self._public_client
    
    @property
    def private_client(self) -> Optional[GateFuturesPrivateWebSocket]:
        """获取私有频道客户端"""
        return self._private_client
    
    def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """获取代理配置信息"""
        return settings.get_proxy_config() if self._proxy else None


# 向后兼容的别名
GateFuturesWebsocket = GateFuturesWebSocketManager
