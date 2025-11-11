# -*- coding: utf-8 -*-
"""
Binance U本位合约 WebSocket API 实现

支持Binance U本位合约交易的公共数据流和用户数据流WebSocket连接。
基于utils.websocket.WebSocketClient实现，提供优雅的API设计。

API文档: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams

"""

import json
import asyncio
from typing import Optional, Dict, Any, List, Callable, Union, Literal
from utils.websocket import WebSocketClient
from utils.log import logger
from utils.settings import settings

# WebSocket连接地址配置
WEBSOCKET_HOST = "wss://fstream.binance.com"
# 单一数据流
WEBSOCKET_STREAM = f"{WEBSOCKET_HOST}/ws"
# 组合数据流
WEBSOCKET_COMBINED = f"{WEBSOCKET_HOST}/stream"

# 类型定义
StreamType = Literal['aggTrade', 'markPrice', 'kline', 'miniTicker', 'ticker', 'bookTicker', 'liquidation', 'depth', 'forceOrder']


class BinanceFuturesWebSocketBase(WebSocketClient):
    """
    Binance 合约 WebSocket 基础客户端
    
    提供通用的WebSocket连接管理、订阅等功能。
    """
    
    def __init__(
        self,
        stream_names: Optional[List[str]] = None,
        combined: bool = True,
        proxy: bool = False,
        **kwargs
    ):
        """
        初始化Binance合约WebSocket客户端
        
        Args:
            stream_names: 数据流名称列表（如 ['btcusdt@aggTrade', 'ethusdt@markPrice']）
            combined: 是否使用组合流模式
            proxy: 是否使用代理
            **kwargs: 传递给WebSocketClient的其他参数
        """
        self._stream_names = stream_names or []
        self._combined = combined
        self._proxy = settings.get_proxy_config() if proxy else None
        
        # 构建WebSocket URL
        url = self._build_url()
        
        # Binance不需要心跳消息（服务器会主动发送ping）
        # 服务器每3分钟发送一次ping frame
        
        # 初始化父类
        super().__init__(
            url=url,
            proxy=self._proxy,
            send_hb_interval=0,  # Binance不需要客户端发送心跳
            **kwargs
        )
        
        # 订阅管理
        self._subscriptions: Dict[str, Callable] = {}
        self._req_id_counter = 0
    
    def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """获取代理配置信息"""
        return self._proxy
    
    def _build_url(self) -> str:
        """构建WebSocket连接URL"""
        if not self._stream_names:
            # 如果没有指定流，返回基础URL
            return WEBSOCKET_STREAM
        
        if self._combined and len(self._stream_names) > 1:
            # 组合流模式
            streams = "/".join(self._stream_names)
            return f"{WEBSOCKET_COMBINED}?streams={streams}"
        elif len(self._stream_names) == 1:
            # 单一流模式
            return f"{WEBSOCKET_STREAM}/{self._stream_names[0]}"
        else:
            # 多个流但不使用组合模式，使用第一个
            return f"{WEBSOCKET_STREAM}/{self._stream_names[0]}"
    
    def _get_next_req_id(self) -> int:
        """获取下一个请求ID"""
        self._req_id_counter += 1
        return self._req_id_counter
    
    async def start(self):
        """启动WebSocket连接"""
        try:
            logger.info(f"开始连接Binance合约WebSocket: {self._url}")
            logger.info(f"代理配置: {self._proxy}")
            
            # 调用父类的start方法（非异步）
            super().start()
            
            # 等待连接建立
            max_wait = 10
            logger.info("等待WebSocket连接建立...")
            
            for i in range(max_wait * 10):
                if self.is_connected:
                    logger.info("WebSocket连接已建立")
                    break
                await asyncio.sleep(0.1)
                if i % 20 == 0:
                    logger.info(f"等待连接... 状态: {self._state.value} ({i/10:.1f}s)")
            else:
                logger.error(f"WebSocket连接超时，当前状态: {self._state.value}")
                raise Exception("WebSocket连接超时")
                
            logger.info(f"Binance合约WebSocket连接成功: {self._url}")
            
        except Exception as e:
            logger.error(f"启动WebSocket连接失败: {e}")
            raise
    
    async def stop(self):
        """停止WebSocket连接"""
        try:
            # 取消心跳任务（如果有）
            if hasattr(self, '_check_task_id') and self._check_task_id:
                from utils.heartbeat import heartbeat
                heartbeat.unregister(self._check_task_id)
                
            if hasattr(self, '_heartbeat_task_id') and self._heartbeat_task_id:
                from utils.heartbeat import heartbeat
                heartbeat.unregister(self._heartbeat_task_id)
            
            # 断开连接
            await self.disconnect()
            
            logger.info("Binance合约WebSocket连接已停止")
            
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
    
    async def subscribe(self, streams: List[str]) -> bool:
        """
        订阅数据流（动态订阅）
        
        Args:
            streams: 数据流名称列表
            
        Returns:
            bool: 订阅是否成功发送
        """
        try:
            req_id = self._get_next_req_id()
            subscribe_msg = {
                "method": "SUBSCRIBE",
                "params": streams,
                "id": req_id
            }
            
            await self.send_json(subscribe_msg)
            logger.info(f"已发送订阅请求: {streams}")
            return True
            
        except Exception as e:
            logger.error(f"订阅失败: {e}")
            return False
    
    async def unsubscribe(self, streams: List[str]) -> bool:
        """
        取消订阅数据流
        
        Args:
            streams: 数据流名称列表
            
        Returns:
            bool: 取消订阅是否成功发送
        """
        try:
            req_id = self._get_next_req_id()
            unsubscribe_msg = {
                "method": "UNSUBSCRIBE",
                "params": streams,
                "id": req_id
            }
            
            await self.send_json(unsubscribe_msg)
            logger.info(f"已发送取消订阅请求: {streams}")
            return True
            
        except Exception as e:
            logger.error(f"取消订阅失败: {e}")
            return False
    
    async def on_connect(self):
        """连接成功回调（WebSocketClient基类回调）"""
        logger.info(f"Binance合约WebSocket已连接: {self._url}")
    
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
            
            # 处理订阅响应
            if 'result' in message and 'id' in message:
                if message['result'] is None:
                    logger.info(f"订阅操作成功: ID {message['id']}")
                else:
                    logger.error(f"订阅操作失败: {message}")
                return
            
            # 处理错误消息
            if 'error' in message:
                logger.error(f"收到错误消息: {message['error']}")
                return
            
            # 处理组合流数据
            if 'stream' in message and 'data' in message:
                stream_name = message['stream']
                data = message['data']
                
                # 调用订阅的回调函数
                if stream_name in self._subscriptions:
                    callback = self._subscriptions[stream_name]
                    if callback:
                        try:
                            await callback(data)
                        except Exception as e:
                            logger.error(f"回调函数执行失败 {stream_name}: {e}")
                else:
                    logger.debug(f"收到未订阅流的数据: {stream_name}")
            
            # 处理单一流数据（没有stream字段）
            elif 'e' in message:  # event type
                event_type = message['e']
                
                # 调用通用回调
                if 'default' in self._subscriptions:
                    callback = self._subscriptions['default']
                    if callback:
                        try:
                            await callback(message)
                        except Exception as e:
                            logger.error(f"回调函数执行失败: {e}")
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
    
    async def on_disconnect(self):
        """断开连接回调（WebSocketClient基类回调）"""
        logger.warning("Binance合约WebSocket连接已断开")


class BinanceFuturesPublicWebSocket(BinanceFuturesWebSocketBase):
    """
    Binance 合约公共数据流 WebSocket 客户端
    
    支持交易数据、K线、Ticker、深度、标记价格等公共数据订阅。
    """
    
    def __init__(self, proxy: bool = False, **kwargs):
        """
        初始化公共数据流WebSocket客户端
        
        Args:
            proxy: 是否使用代理
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(
            stream_names=[],
            combined=True,
            proxy=proxy,
            **kwargs
        )
    
    async def subscribe_agg_trade(self, symbols: List[str], callback: Optional[Callable] = None) -> bool:
        """
        订阅归集交易流
        
        Args:
            symbols: 交易对列表，如 ['btcusdt', 'ethusdt']
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        streams = [f"{symbol.lower()}@aggTrade" for symbol in symbols]
        
        # 注册回调
        if callback:
            for stream in streams:
                self._subscriptions[stream] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_mark_price(self, symbols: List[str], update_speed: str = '1s',
                                   callback: Optional[Callable] = None) -> bool:
        """
        订阅标记价格流
        
        Args:
            symbols: 交易对列表
            update_speed: 更新速度 ('1s' 或 '3s')
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        if update_speed == '3s':
            streams = [f"{symbol.lower()}@markPrice@3s" for symbol in symbols]
        else:
            streams = [f"{symbol.lower()}@markPrice" for symbol in symbols]
        
        # 注册回调
        if callback:
            for stream in streams:
                self._subscriptions[stream] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_all_mark_price(self, update_speed: str = '1s',
                                      callback: Optional[Callable] = None) -> bool:
        """
        订阅所有标记价格流
        
        Args:
            update_speed: 更新速度 ('1s' 或 '3s')
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        if update_speed == '3s':
            streams = ['!markPrice@arr@3s']
        else:
            streams = ['!markPrice@arr']
        
        # 注册回调
        if callback:
            self._subscriptions[streams[0]] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_kline(self, symbols: List[str], interval: str, 
                             callback: Optional[Callable] = None) -> bool:
        """
        订阅K线流
        
        Args:
            symbols: 交易对列表
            interval: K线周期 (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        streams = [f"{symbol.lower()}@kline_{interval}" for symbol in symbols]
        
        # 注册回调
        if callback:
            for stream in streams:
                self._subscriptions[stream] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_mini_ticker(self, symbols: List[str], callback: Optional[Callable] = None) -> bool:
        """
        订阅简化Ticker流
        
        Args:
            symbols: 交易对列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        streams = [f"{symbol.lower()}@miniTicker" for symbol in symbols]
        
        # 注册回调
        if callback:
            for stream in streams:
                self._subscriptions[stream] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_all_mini_ticker(self, callback: Optional[Callable] = None) -> bool:
        """
        订阅所有简化Ticker流
        
        Args:
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        streams = ['!miniTicker@arr']
        
        # 注册回调
        if callback:
            self._subscriptions['!miniTicker@arr'] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_ticker(self, symbols: List[str], callback: Optional[Callable] = None) -> bool:
        """
        订阅完整Ticker流
        
        Args:
            symbols: 交易对列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        streams = [f"{symbol.lower()}@ticker" for symbol in symbols]
        
        # 注册回调
        if callback:
            for stream in streams:
                self._subscriptions[stream] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_all_ticker(self, callback: Optional[Callable] = None) -> bool:
        """
        订阅所有Ticker流
        
        Args:
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        streams = ['!ticker@arr']
        
        # 注册回调
        if callback:
            self._subscriptions['!ticker@arr'] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_book_ticker(self, symbols: List[str], callback: Optional[Callable] = None) -> bool:
        """
        订阅最优挂单信息流
        
        Args:
            symbols: 交易对列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        streams = [f"{symbol.lower()}@bookTicker" for symbol in symbols]
        
        # 注册回调
        if callback:
            for stream in streams:
                self._subscriptions[stream] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_all_book_ticker(self, callback: Optional[Callable] = None) -> bool:
        """
        订阅所有最优挂单信息流
        
        Args:
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        streams = ['!bookTicker']
        
        # 注册回调
        if callback:
            self._subscriptions['!bookTicker'] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_liquidation(self, symbols: List[str], callback: Optional[Callable] = None) -> bool:
        """
        订阅强平订单流
        
        Args:
            symbols: 交易对列表
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        streams = [f"{symbol.lower()}@forceOrder" for symbol in symbols]
        
        # 注册回调
        if callback:
            for stream in streams:
                self._subscriptions[stream] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_all_liquidation(self, callback: Optional[Callable] = None) -> bool:
        """
        订阅所有强平订单流
        
        Args:
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        streams = ['!forceOrder@arr']
        
        # 注册回调
        if callback:
            self._subscriptions['!forceOrder@arr'] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_depth(self, symbols: List[str], levels: int = 20, 
                             update_speed: str = '250ms', 
                             callback: Optional[Callable] = None) -> bool:
        """
        订阅深度信息流
        
        Args:
            symbols: 交易对列表
            levels: 深度档位 (5, 10, 20)
            update_speed: 更新速度 ('100ms', '250ms', '500ms')
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        if update_speed == '100ms':
            streams = [f"{symbol.lower()}@depth{levels}@100ms" for symbol in symbols]
        elif update_speed == '500ms':
            streams = [f"{symbol.lower()}@depth{levels}@500ms" for symbol in symbols]
        else:
            streams = [f"{symbol.lower()}@depth{levels}" for symbol in symbols]
        
        # 注册回调
        if callback:
            for stream in streams:
                self._subscriptions[stream] = callback
        
        return await self.subscribe(streams)
    
    async def subscribe_depth_update(self, symbols: List[str], 
                                    update_speed: str = '250ms',
                                    callback: Optional[Callable] = None) -> bool:
        """
        订阅深度增量更新流
        
        Args:
            symbols: 交易对列表
            update_speed: 更新速度 ('100ms', '250ms', '500ms')
            callback: 数据回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        if update_speed == '100ms':
            streams = [f"{symbol.lower()}@depth@100ms" for symbol in symbols]
        elif update_speed == '500ms':
            streams = [f"{symbol.lower()}@depth@500ms" for symbol in symbols]
        else:
            streams = [f"{symbol.lower()}@depth" for symbol in symbols]
        
        # 注册回调
        if callback:
            for stream in streams:
                self._subscriptions[stream] = callback
        
        return await self.subscribe(streams)


class BinanceFuturesUserDataWebSocket(BinanceFuturesWebSocketBase):
    """
    Binance 合约用户数据流 WebSocket 客户端
    
    支持账户更新、订单更新、持仓更新等私有数据订阅。
    需要通过REST API获取listenKey。
    """
    
    def __init__(self, listen_key: str, proxy: bool = False, **kwargs):
        """
        初始化用户数据流WebSocket客户端
        
        Args:
            listen_key: 通过REST API获取的listenKey
            proxy: 是否使用代理
            **kwargs: 传递给基类的其他参数
        """
        self._listen_key = listen_key
        
        # 用户数据流使用特殊的URL
        super().__init__(
            stream_names=[listen_key],
            combined=False,
            proxy=proxy,
            **kwargs
        )
        
        # 用户数据回调
        self._margin_call_callback: Optional[Callable] = None
        self._account_update_callback: Optional[Callable] = None
        self._order_update_callback: Optional[Callable] = None
        self._account_config_callback: Optional[Callable] = None
    
    def set_margin_call_callback(self, callback: Callable):
        """设置追加保证金通知回调"""
        self._margin_call_callback = callback
    
    def set_account_update_callback(self, callback: Callable):
        """设置账户更新回调"""
        self._account_update_callback = callback
    
    def set_order_update_callback(self, callback: Callable):
        """设置订单更新回调"""
        self._order_update_callback = callback
    
    def set_account_config_callback(self, callback: Callable):
        """设置账户配置更新回调"""
        self._account_config_callback = callback
    
    async def process(self, message: Union[Dict[str, Any], str]):
        """处理用户数据流消息"""
        try:
            # 如果是字符串，尝试解析为字典
            if isinstance(message, str):
                try:
                    message = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning(f"无法解析消息: {message}")
                    return
            
            if not isinstance(message, dict):
                return
            
            # 获取事件类型
            event_type = message.get('e')
            
            if event_type == 'MARGIN_CALL':
                # 追加保证金通知
                if self._margin_call_callback:
                    await self._margin_call_callback(message)
                    
            elif event_type == 'ACCOUNT_UPDATE':
                # 账户更新（包括余额和持仓）
                if self._account_update_callback:
                    await self._account_update_callback(message)
                    
            elif event_type == 'ORDER_TRADE_UPDATE':
                # 订单/成交更新
                if self._order_update_callback:
                    await self._order_update_callback(message)
                    
            elif event_type == 'ACCOUNT_CONFIG_UPDATE':
                # 账户配置更新（杠杆、持仓模式等）
                if self._account_config_callback:
                    await self._account_config_callback(message)
            
            else:
                logger.debug(f"收到未处理的事件类型: {event_type}")
            
        except Exception as e:
            logger.error(f"处理用户数据失败: {e}")


class BinanceFuturesWebSocketManager:
    """
    Binance 合约 WebSocket 管理器
    
    统一管理公共数据流和用户数据流WebSocket连接。
    """
    
    def __init__(self, listen_key: Optional[str] = None, proxy: bool = False):
        """
        初始化WebSocket管理器
        
        Args:
            listen_key: 用户数据流listenKey（可选）
            proxy: 是否使用代理
        """
        self._listen_key = listen_key
        self._proxy = proxy
        
        # WebSocket客户端实例
        self._public_client: Optional[BinanceFuturesPublicWebSocket] = None
        self._user_client: Optional[BinanceFuturesUserDataWebSocket] = None
        
        # 连接状态
        self._public_connected = False
        self._user_connected = False
    
    async def start_public_client(self) -> BinanceFuturesPublicWebSocket:
        """
        启动公共数据流客户端
        
        Returns:
            BinanceFuturesPublicWebSocket: 公共数据流客户端实例
        """
        if not self._public_client:
            self._public_client = BinanceFuturesPublicWebSocket(proxy=self._proxy)
        
        if not self._public_connected:
            await self._public_client.start()
            self._public_connected = True
            logger.info("合约公共数据流WebSocket已启动")
        
        return self._public_client
    
    async def start_user_client(self, listen_key: Optional[str] = None) -> BinanceFuturesUserDataWebSocket:
        """
        启动用户数据流客户端
        
        Args:
            listen_key: listenKey（如果未在初始化时提供）
            
        Returns:
            BinanceFuturesUserDataWebSocket: 用户数据流客户端实例
            
        Raises:
            ValueError: 当listenKey未提供时
        """
        key = listen_key or self._listen_key
        if not key:
            raise ValueError("需要提供listenKey")
        
        if not self._user_client:
            self._user_client = BinanceFuturesUserDataWebSocket(listen_key=key, proxy=self._proxy)
        
        if not self._user_connected:
            await self._user_client.start()
            self._user_connected = True
            logger.info("合约用户数据流WebSocket已启动")
        
        return self._user_client
    
    async def stop_all(self):
        """停止所有WebSocket连接"""
        if self._public_client and self._public_connected:
            await self._public_client.stop()
            self._public_connected = False
            logger.info("合约公共数据流WebSocket已停止")
        
        if self._user_client and self._user_connected:
            await self._user_client.stop()
            self._user_connected = False
            logger.info("合约用户数据流WebSocket已停止")
    
    @property
    def public_client(self) -> Optional[BinanceFuturesPublicWebSocket]:
        """获取公共数据流客户端"""
        return self._public_client
    
    @property
    def user_client(self) -> Optional[BinanceFuturesUserDataWebSocket]:
        """获取用户数据流客户端"""
        return self._user_client
    
    def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """获取代理配置信息"""
        return settings.get_proxy_config() if self._proxy else None
