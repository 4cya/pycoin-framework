# -*- coding: utf-8 -*-
"""
WebSocket异步客户端工具模块

提供WebSocket连接的异步封装，支持：
- 自动重连机制
- 心跳保持
- 连接状态管理
- 消息自动解析（JSON/Text/Binary）
- 优雅的错误处理

"""

import json
import asyncio
from typing import Optional, Dict, Any, Union, Callable
from enum import Enum
import aiohttp
from aiohttp import ClientSession, WSMsgType, ClientWebSocketResponse

from utils.log import logger
from utils.heartbeat import heartbeat


class ConnectionState(Enum):
    """WebSocket连接状态枚举"""
    DISCONNECTED = "disconnected"  # 未连接
    CONNECTING = "connecting"      # 连接中
    CONNECTED = "connected"        # 已连接
    RECONNECTING = "reconnecting"  # 重连中
    CLOSED = "closed"              # 已关闭


class WebSocketClient:
    """
    WebSocket异步客户端基类
    
    提供WebSocket连接管理、自动重连、心跳保持等功能。
    子类需要实现 process() 和 process_binary() 方法来处理消息。
    """

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        check_conn_interval: int = 10,
        send_hb_interval: int = 10,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 0  # 0表示无限重连
    ):
        """
        初始化WebSocket客户端
        
        Args:
            url: WebSocket服务器地址
            headers: 连接请求头
            proxy: 代理服务器地址
            check_conn_interval: 检查连接状态的时间间隔（秒）
            send_hb_interval: 发送心跳的时间间隔（秒）
            auto_reconnect: 是否自动重连
            max_reconnect_attempts: 最大重连次数，0表示无限重连
        """
        self._url = url
        self._headers = headers or {}
        self._proxy = proxy
        self._check_conn_interval = check_conn_interval
        self._send_hb_interval = send_hb_interval
        self._auto_reconnect = auto_reconnect
        self._max_reconnect_attempts = max_reconnect_attempts
        
        # 连接相关
        self._session: Optional[ClientSession] = None
        self._ws: Optional[ClientWebSocketResponse] = None
        self._state = ConnectionState.DISCONNECTED
        self._reconnect_count = 0
        
        # 心跳相关
        self.heartbeat_msg: Optional[Union[str, Dict[str, Any]]] = None
        self._check_task_id: Optional[str] = None
        self._heartbeat_task_id: Optional[str] = None

    @property
    def state(self) -> ConnectionState:
        """获取当前连接状态"""
        return self._state

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._state == ConnectionState.CONNECTED and self._ws and not self._ws.closed

    async def connect(self) -> bool:
        """
        建立WebSocket连接
        
        Returns:
            bool: 连接成功返回True，失败返回False
        """
        if self._state in (ConnectionState.CONNECTING, ConnectionState.CONNECTED):
            logger.warning(f"WebSocket已处于{self._state.value}状态")
            return False
        
        self._state = ConnectionState.CONNECTING
        logger.info(f"正在连接WebSocket: {self._url}")
        
        try:
            # 创建Session
            if not self._session:
                self._session = ClientSession()
            
            # 建立WebSocket连接
            self._ws = await self._session.ws_connect(
                self._url,
                headers=self._headers,
                proxy=self._proxy,
                heartbeat=30  # aiohttp内置心跳
            )
            
            self._state = ConnectionState.CONNECTED
            self._reconnect_count = 0
            logger.info(f"WebSocket连接成功: {self._url}")
            
            # 触发连接成功回调
            await self.on_connect()
            
            # 启动消息接收循环
            asyncio.create_task(self._receive_loop())
            
            return True
            
        except aiohttp.ClientError as e:
            self._state = ConnectionState.DISCONNECTED
            logger.error(f"WebSocket连接失败: {e}", url=self._url)
            return False
        except Exception as e:
            self._state = ConnectionState.DISCONNECTED
            logger.error(f"WebSocket连接异常: {e}", url=self._url)
            return False

    async def disconnect(self) -> None:
        """
        断开WebSocket连接
        """
        logger.info("正在断开WebSocket连接...")
        self._state = ConnectionState.CLOSED
        
        # 注销心跳任务
        if self._check_task_id:
            heartbeat.unregister(self._check_task_id)
            self._check_task_id = None
        if self._heartbeat_task_id:
            heartbeat.unregister(self._heartbeat_task_id)
            self._heartbeat_task_id = None
        
        # 关闭WebSocket
        if self._ws and not self._ws.closed:
            await self._ws.close()
        
        # 关闭Session
        if self._session and not self._session.closed:
            await self._session.close()
        
        logger.info("WebSocket连接已断开")

    def start(self) -> None:
        """
        启动WebSocket客户端
        
        建立连接并注册心跳任务。
        """
        # 注册连接检查任务
        self._check_task_id = heartbeat.register(
            self._check_connection,
            interval=self._check_conn_interval
        )
        logger.info(f"已注册连接检查任务，间隔: {self._check_conn_interval}秒")
        
        # 注册心跳发送任务
        self._heartbeat_task_id = heartbeat.register(
            self._send_heartbeat,
            interval=self._send_hb_interval
        )
        logger.info(f"已注册心跳发送任务，间隔: {self._send_hb_interval}秒")
        
        # 建立连接
        asyncio.create_task(self.connect())

    async def _receive_loop(self) -> None:
        """消息接收循环"""
        try:
            async for msg in self._ws:
                if msg.type == WSMsgType.TEXT:
                    # 处理文本消息
                    await self._handle_text_message(msg.data)
                    
                elif msg.type == WSMsgType.BINARY:
                    # 处理二进制消息
                    await self._handle_binary_message(msg.data)
                    
                elif msg.type == WSMsgType.CLOSED:
                    logger.warning("WebSocket连接已关闭")
                    await self._handle_disconnect()
                    break
                    
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket错误: {self._ws.exception()}")
                    await self._handle_disconnect()
                    break
                    
                else:
                    logger.warning(f"未知消息类型: {msg.type}")
                    
        except Exception as e:
            logger.error(f"消息接收循环异常: {e}")
            await self._handle_disconnect()

    async def _handle_text_message(self, data: str) -> None:
        """处理文本消息"""
        try:
            # 尝试解析为JSON
            try:
                parsed_data = json.loads(data)
            except json.JSONDecodeError:
                parsed_data = data
            
            # 调用子类实现的处理方法
            await self.process(parsed_data)
            
        except Exception as e:
            logger.error(f"处理文本消息异常: {e}", data=data[:200])

    async def _handle_binary_message(self, data: bytes) -> None:
        """处理二进制消息"""
        try:
            await self.process_binary(data)
        except Exception as e:
            logger.error(f"处理二进制消息异常: {e}")

    async def _handle_disconnect(self) -> None:
        """处理断开连接"""
        if self._state == ConnectionState.CLOSED:
            return
        
        self._state = ConnectionState.DISCONNECTED
        
        # 触发断开连接回调
        await self.on_disconnect()
        
        # 自动重连
        if self._auto_reconnect:
            await self._reconnect()

    async def _reconnect(self) -> None:
        """重新连接"""
        if self._state == ConnectionState.RECONNECTING:
            return
        
        # 检查重连次数限制
        if self._max_reconnect_attempts > 0 and self._reconnect_count >= self._max_reconnect_attempts:
            logger.error(f"已达到最大重连次数: {self._max_reconnect_attempts}")
            return
        
        self._state = ConnectionState.RECONNECTING
        self._reconnect_count += 1
        
        # 等待一段时间后重连
        wait_time = min(self._reconnect_count * 2, 30)  # 最多等待30秒
        logger.info(f"将在{wait_time}秒后进行第{self._reconnect_count}次重连...")
        await asyncio.sleep(wait_time)
        
        await self.connect()

    async def _check_connection(self, *args, **kwargs) -> None:
        """检查连接状态（心跳任务）"""
        if not self._ws:
            logger.debug("WebSocket未初始化")
            return
        
        if self._ws.closed and self._state == ConnectionState.CONNECTED:
            logger.warning("检测到WebSocket连接已断开")
            await self._handle_disconnect()

    async def _send_heartbeat(self, *args, **kwargs) -> None:
        """发送心跳消息（心跳任务）"""
        if not self.is_connected or not self.heartbeat_msg:
            return
        
        try:
            if isinstance(self.heartbeat_msg, dict):
                await self._ws.send_json(self.heartbeat_msg)
                logger.debug("已发送心跳消息（JSON）")
            elif isinstance(self.heartbeat_msg, str):
                await self._ws.send_str(self.heartbeat_msg)
                logger.debug("已发送心跳消息（Text）")
            else:
                logger.warning(f"不支持的心跳消息类型: {type(self.heartbeat_msg)}")
        except Exception as e:
            logger.error(f"发送心跳消息失败: {e}")

    async def send_json(self, data: Dict[str, Any]) -> bool:
        """
        发送JSON消息
        
        Args:
            data: 要发送的字典数据
            
        Returns:
            bool: 发送成功返回True
        """
        if not self.is_connected:
            logger.warning("WebSocket未连接，无法发送消息")
            return False
        
        try:
            await self._ws.send_json(data)
            logger.debug(f"已发送JSON消息: {data}")
            return True
        except Exception as e:
            logger.error(f"发送JSON消息失败: {e}", data=data)
            return False

    async def send_text(self, text: str) -> bool:
        """
        发送文本消息
        
        Args:
            text: 要发送的文本
            
        Returns:
            bool: 发送成功返回True
        """
        if not self.is_connected:
            logger.warning("WebSocket未连接，无法发送消息")
            return False
        
        try:
            await self._ws.send_str(text)
            logger.debug(f"已发送文本消息: {text}")
            return True
        except Exception as e:
            logger.error(f"发送文本消息失败: {e}")
            return False

    # ==================== 子类需要实现的方法 ====================

    async def on_connect(self) -> None:
        """
        连接成功回调
        
        子类可以重写此方法，在连接成功后执行自定义逻辑，
        例如：订阅频道、发送认证信息等。
        """
        pass

    async def on_disconnect(self) -> None:
        """
        断开连接回调
        
        子类可以重写此方法，在断开连接后执行清理工作。
        """
        pass

    async def process(self, data: Union[Dict, str]) -> None:
        """
        处理接收到的文本/JSON消息
        
        子类必须实现此方法来处理业务逻辑。
        
        Args:
            data: 接收到的数据（已解析的JSON字典或原始文本）
        """
        raise NotImplementedError("子类必须实现 process() 方法")

    async def process_binary(self, data: bytes) -> None:
        """
        处理接收到的二进制消息
        
        子类可以重写此方法来处理二进制数据。
        默认实现会记录警告日志。
        
        Args:
            data: 接收到的二进制数据
        """
        logger.warning("收到二进制消息但未实现处理方法")
