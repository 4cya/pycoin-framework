# -*- coding: utf-8 -*-
"""
日志工具模块

提供统一的日志记录功能，支持控制台彩色输出和文件轮转输出。
从配置文件读取日志配置，保持与项目配置管理一致。
"""

import os
import json
from typing import Optional, Dict, Any
import logbook
from logbook import Logger, TimedRotatingFileHandler, lookup_level
from logbook.more import ColorizedStderrHandler

from utils.settings import Settings

# 全局日志记录器实例
logger = Logger()
# 全局配置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置实例（单例模式）"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def init_logger_from_config() -> None:
    """
    从配置文件初始化日志记录器
    
    读取 config/app.yaml 中的 logging 配置项进行初始化
    """
    try:
        settings = get_settings()
        logging_config = settings.get_logging_config()
        
        init_logger(
            level=logging_config.get('level', 'INFO'),
            name='log',  # 固定使用 pycoin 作为日志名称
            path=logging_config.get('path') if logging_config.get('file_enabled', True) else None,
            backup_count=logging_config.get('backup_count', 5),
            console_enabled=logging_config.get('console_enabled', True)
        )
        
        logger.info("日志系统初始化完成", extra={
            'level': logging_config.get('level'),
            'file_enabled': logging_config.get('file_enabled'),
            'console_enabled': logging_config.get('console_enabled'),
            'path': logging_config.get('path')
        })
        
    except Exception as e:
        # 如果配置文件读取失败，使用默认配置
        print(f"⚠️  读取日志配置失败，使用默认配置: {e}")
        init_logger()


def init_logger(
    level: str = 'INFO',
    name: str = 'log',
    path: Optional[str] = './logs',
    backup_count: int = 5,
    console_enabled: bool = True,
    encoding: str = 'utf-8'
) -> None:
    """
    初始化日志记录器
    
    Args:
        level: 日志级别，可选值: DEBUG, INFO, WARNING, ERROR, CRITICAL
        name: 日志文件名称（不含扩展名）
        path: 日志文件保存路径，为 None 时不写入文件
        backup_count: 日志文件备份数量
        console_enabled: 是否启用控制台输出
        encoding: 文件编码
    """
    # 设置日志时间格式为本地时间
    logbook.set_datetime_format("local")
    
    # 配置全局日志记录器
    logger.name = name
    logger.level = lookup_level(level)
    logger.handlers = []

    # 添加控制台彩色输出处理器
    if console_enabled:
        log_std = ColorizedStderrHandler(bubble=True)
        log_std.formatter = log_formatter
        logger.handlers.append(log_std)
    
    # 如果指定了路径，添加文件输出处理器
    if path is not None:
        log_dir = os.path.abspath(path)
        # 确保日志目录存在
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # 创建按日期轮转的文件处理器
        log_file_path = os.path.join(log_dir, f'{name}.log')
        log_file = TimedRotatingFileHandler(
            log_file_path,
            date_format='%Y-%m-%d',
            backup_count=backup_count,
            bubble=True,
            encoding=encoding
        )
        log_file.formatter = log_formatter
        logger.handlers.append(log_file)


def log_formatter(record, handle) -> str:
    """
    格式化日志记录
    
    Args:
        record: 日志记录对象，包含日志的各种信息
        handle: 日志处理器对象（本函数中未使用）
    
    Returns:
        str: 格式化后的日志字符串
    """
    try:
        # 使用固定的时间格式
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # 构建基础日志格式
        log = "[{date}] [{level}] [{filename}:{lineno}] [{func_name}] {msg}".format(
            date=record.time.strftime(date_format),          # 日志时间
            level=record.level_name,                         # 日志等级
            filename=os.path.split(record.filename)[-1],     # 文件名（不含路径）
            func_name=record.func_name,                      # 函数名
            lineno=record.lineno,                            # 行号
            msg=record.msg                                   # 日志内容
        )
        
        # 添加额外的位置参数
        if record.args:
            for arg in record.args:
                log += f" {str(arg)}"
        
        # 添加关键字参数（转换为 JSON 格式）
        if record.kwargs:
            try:
                log += f" {json.dumps(record.kwargs, ensure_ascii=False)}"
            except (TypeError, ValueError):
                log += f" {str(record.kwargs)}"
        
        return log
        
    except Exception as e:
        # 如果格式化失败，返回简单格式
        return f"[{record.time}] [{record.level_name}] {record.msg}"


# 兼容性别名，保持向后兼容
log_type = log_formatter


def get_logger(name: str = None) -> Logger:
    """
    获取日志记录器实例
    
    Args:
        name: 日志记录器名称，为 None 时返回全局记录器
        
    Returns:
        Logger: 日志记录器实例
    """
    if name is None:
        return logger
    else:
        return Logger(name)


def set_log_level(level: str) -> None:
    """
    动态设置日志级别
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    try:
        logger.level = lookup_level(level)
        logger.info(f"日志级别已更改为: {level}")
    except (KeyError, ValueError) as e:
        logger.error(f"无效的日志级别: {level}, 错误: {e}")


# 便捷的日志记录函数
def debug(msg: str, *args, **kwargs) -> None:
    """记录 DEBUG 级别日志"""
    logger.debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs) -> None:
    """记录 INFO 级别日志"""
    logger.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs) -> None:
    """记录 WARNING 级别日志"""
    logger.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs) -> None:
    """记录 ERROR 级别日志"""
    logger.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs) -> None:
    """记录 CRITICAL 级别日志"""
    logger.critical(msg, *args, **kwargs)
