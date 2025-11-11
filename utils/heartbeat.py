# -*- coding: utf-8 -*-
"""
心跳机制模块

提供应用程序的心跳服务，支持：
- 定时任务调度：按指定间隔执行异步任务
- 心跳计数：记录运行时长
- 心跳打印：可配置的心跳日志输出
- 存活广播：可选的服务存活状态广播

"""

import asyncio
from typing import Dict, Any, Callable, Optional, Tuple
from collections.abc import Coroutine

from utils import tools
from utils.log import logger
from utils.settings import settings


class HeartBeat:
    """
    心跳服务类
    
    提供定时任务调度和心跳监控功能。每秒触发一次心跳，
    执行注册的定时任务，并根据配置打印心跳信息。
    """

    def __init__(self):
        """初始化心跳服务"""
        self._count: int = 0  # 心跳计数器
        self._interval: int = 1  # 心跳执行间隔（秒）
        self._is_running: bool = False  # 运行状态标志
        self._tasks: Dict[str, Dict[str, Any]] = {}  # 注册的任务字典
        
        # 从新的配置结构加载心跳参数
        heartbeat_config = settings.get_heartbeat_config()
        
        # 心跳打印间隔（秒），0表示不打印
        self._print_interval: int = heartbeat_config.get("interval", 0)
        
        # 心跳广播间隔（秒），0表示不广播
        self._broadcast_interval: int = heartbeat_config.get("broadcast", 0)

    @property
    def count(self) -> int:
        """
        获取心跳计数
        
        Returns:
            int: 当前心跳次数
        """
        return self._count

    @property
    def is_running(self) -> bool:
        """
        获取心跳运行状态
        
        Returns:
            bool: 心跳是否正在运行
        """
        return self._is_running

    def start(self) -> None:
        """
        启动心跳服务
        
        开始心跳循环，每秒触发一次ticker。
        """
        if self._is_running:
            logger.warning("心跳服务已经在运行中")
            return
        
        self._is_running = True
        self._count = 0
        logger.info("心跳服务已启动")
        self.ticker()

    def stop(self) -> None:
        """
        停止心跳服务
        
        停止心跳循环，但不清除已注册的任务。
        """
        self._is_running = False
        logger.info(f"心跳服务已停止，总计运行 {self._count} 秒")

    def ticker(self) -> None:
        """
        心跳tick函数，每秒执行一次
        
        负责：
        1. 心跳计数递增
        2. 打印心跳信息（如果配置）
        3. 执行注册的定时任务
        4. 广播存活状态（如果配置）
        5. 调度下一次心跳
        """
        if not self._is_running:
            return
        
        # 心跳计数递增
        self._count += 1

        # 打印心跳信息
        if self._print_interval > 0 and self._count % self._print_interval == 0:
            logger.info(f"服务心跳 count={self._count}, tasks={len(self._tasks)}")

        # 执行注册的定时任务
        self._execute_tasks()

        # 广播服务存活状态
        if self._broadcast_interval > 0 and self._count % self._broadcast_interval == 0:
            self._broadcast_alive()

        # 调度下一次心跳
        asyncio.get_event_loop().call_later(self._interval, self.ticker)

    def _execute_tasks(self) -> None:
        """执行所有到期的定时任务"""
        for task_id, task in self._tasks.items():
            interval = task["interval"]
            # 检查是否到达执行时间
            if self._count % interval != 0:
                continue
            
            func = task["func"]
            args = task["args"]
            kwargs = task["kwargs"]
            
            # 创建异步任务执行
            try:
                asyncio.get_event_loop().create_task(func(*args, **kwargs))
            except Exception as e:
                logger.error(f"执行心跳任务失败: {e}", task_id=task_id, func=func.__name__)

    def _broadcast_alive(self) -> None:
        """
        广播服务存活状态
        
        可以在这里实现具体的广播逻辑，例如：
        - 向Redis写入存活标记
        - 发送HTTP请求到监控服务
        - 更新数据库状态等
        """
        logger.debug(f"服务存活广播 count={self._count}")
        # TODO: 实现具体的广播逻辑

    def register(
        self,
        func: Callable[..., Coroutine],
        interval: int = 1,
        *args,
        **kwargs
    ) -> str:
        """
        注册一个定时任务
        
        Args:
            func: 要执行的异步函数
            interval: 执行间隔（秒），必须大于0
            *args: 传递给函数的位置参数
            **kwargs: 传递给函数的关键字参数
            
        Returns:
            str: 任务ID，用于后续注销任务
            
        Raises:
            ValueError: 如果interval小于等于0
        """
        if interval <= 0:
            raise ValueError(f"任务执行间隔必须大于0，当前值: {interval}")
        
        task_id = tools.get_uuid1()
        self._tasks[task_id] = {
            "func": func,
            "interval": interval,
            "args": args,
            "kwargs": kwargs
        }
        logger.info(f"注册心跳任务成功: {func.__name__}, interval={interval}s, task_id={task_id}")
        return task_id

    def unregister(self, task_id: str) -> bool:
        """
        注销一个定时任务
        
        Args:
            task_id: 任务ID（由register返回）
            
        Returns:
            bool: 注销成功返回True，任务不存在返回False
        """
        if task_id in self._tasks:
            task = self._tasks.pop(task_id)
            logger.info(f"注销心跳任务成功: {task['func'].__name__}, task_id={task_id}")
            return True
        else:
            logger.warning(f"任务不存在，无法注销: task_id={task_id}")
            return False

    def get_task_count(self) -> int:
        """
        获取已注册的任务数量
        
        Returns:
            int: 任务数量
        """
        return len(self._tasks)

    def clear_tasks(self) -> None:
        """清除所有已注册的任务"""
        count = len(self._tasks)
        self._tasks.clear()
        logger.info(f"已清除所有心跳任务，共 {count} 个")


# 全局心跳实例
heartbeat = HeartBeat()
