# -*- coding: utf-8 -*-
"""
工具函数模块

提供常用的工具函数，包括：
- 时间处理：时间戳、日期时间转换
- 文件操作：YAML、JSON文件读写
- 其他工具：UUID生成、文件路径处理

"""

import os
import uuid
import json
import yaml
import time
import datetime
from typing import Dict, Any, Optional, Union
from pathlib import Path


# ==================== 时间相关函数 ====================

def get_cur_timestamp() -> int:
    """
    获取当前时间戳（秒）
    
    Returns:
        int: 当前Unix时间戳（秒）
    """
    return int(time.time())


def get_cur_timestamp_ms() -> int:
    """
    获取当前时间戳（毫秒）
    
    Returns:
        int: 当前Unix时间戳（毫秒）
    """
    return int(time.time() * 1000)


def get_utc_timestamp() -> str:
    """
    获取UTC时间字符串（ISO 8601格式）
    
    Returns:
        str: UTC时间字符串，格式如 "2024-01-01T12:00:00.000Z"
    """
    now = datetime.datetime.utcnow()
    t = now.isoformat("T", "milliseconds")
    return t + "Z"


def get_datetime_from_ts(ts: Union[int, float, str]) -> datetime.datetime:
    """
    根据时间戳获取datetime对象
    
    Args:
        ts: Unix时间戳（秒）
        
    Returns:
        datetime.datetime: datetime对象
    """
    return datetime.datetime.fromtimestamp(int(ts))


def get_datetime_from_str(dt_str: str, fmt: str = '%Y-%m-%d %H:%M:%S') -> datetime.datetime:
    """
    根据时间字符串获取datetime对象
    
    Args:
        dt_str: 时间字符串
        fmt: 时间格式，默认 '%Y-%m-%d %H:%M:%S'
        
    Returns:
        datetime.datetime: datetime对象
    """
    return datetime.datetime.strptime(dt_str, fmt)


def get_datetime_str(ts: Optional[Union[int, float]] = None, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    将时间戳转换为日期时间字符串
    
    Args:
        ts: Unix时间戳（秒），为None时使用当前时间
        fmt: 时间格式，默认 '%Y-%m-%d %H:%M:%S'
        
    Returns:
        str: 格式化的时间字符串
    """
    if not ts:
        ts = get_cur_timestamp()
    dt = datetime.datetime.fromtimestamp(int(ts))
    return dt.strftime(fmt)


def get_ot_datetime_from_str(dt_str: str, fmt: str = '%Y-%m-%dT%H:%M:%SZ') -> datetime.datetime:
    """
    解析时间字符串并转换为东八区时间（UTC+8）
    
    Args:
        dt_str: UTC时间字符串
        fmt: 时间格式，默认 '%Y-%m-%dT%H:%M:%SZ'
        
    Returns:
        datetime.datetime: 东八区时间的datetime对象
    """
    dt = datetime.datetime.strptime(dt_str, fmt)
    dt = dt + datetime.timedelta(hours=8)
    return dt


def get_ot_datetime_from_str2(dt_str: str, fmt: str = '%Y-%m-%dT%H:%M:%S') -> datetime.datetime:
    """
    解析时间字符串并转换为东八区时间（UTC+8）
    
    Args:
        dt_str: UTC时间字符串（不带Z后缀）
        fmt: 时间格式，默认 '%Y-%m-%dT%H:%M:%S'
        
    Returns:
        datetime.datetime: 东八区时间的datetime对象
    """
    dt = datetime.datetime.strptime(dt_str, fmt)
    dt = dt + datetime.timedelta(hours=8)
    return dt


# ==================== 其他工具函数 ====================

def get_uuid1() -> str:
    """
    生成UUID1字符串
    
    Returns:
        str: UUID1字符串
    """
    return str(uuid.uuid1())


def get_file_path(filename: str) -> Path:
    """
    获取文件的完整路径
    
    Args:
        filename: 相对于项目根目录的文件路径
        
    Returns:
        Path: 文件的完整Path对象
    """
    # 获取项目根目录（utils目录的上级目录）
    current_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = current_path.joinpath(filename)
    return file_path


# ==================== 文件操作函数 ====================

def load_yaml(filename: str) -> Dict[str, Any]:
    """
    加载YAML文件
    
    Args:
        filename: 相对于项目根目录的文件路径
        
    Returns:
        Dict[str, Any]: YAML文件内容的字典，文件不存在时返回空字典
    """
    file_path = get_file_path(filename)
    if file_path.exists():
        with open(file_path, mode="r", encoding="UTF-8") as f:
            data = yaml.load(f.read(), Loader=yaml.FullLoader)
        return data if data else {}
    else:
        return {}


def dump_yaml(data: Dict[str, Any], filename: str) -> None:
    """
    保存数据到YAML文件
    
    Args:
        data: 要保存的数据字典
        filename: 相对于项目根目录的文件路径
    """
    file_path = get_file_path(filename)
    with open(file_path, mode="w+", encoding="UTF-8") as f:
        yaml.dump(data, f, indent=4, allow_unicode=True)


def load_json(filename: str) -> Dict[str, Any]:
    """
    加载JSON文件
    
    Args:
        filename: 相对于项目根目录的文件路径
        
    Returns:
        Dict[str, Any]: JSON文件内容的字典，文件不存在时返回空字典
    """
    file_path = get_file_path(filename)
    if file_path.exists():
        with open(file_path, mode="r", encoding="UTF-8") as f:
            data = json.load(f)
        return data
    else:
        return {}


def dump_json(data: Dict[str, Any], filename: str) -> None:
    """
    保存数据到JSON文件
    
    Args:
        data: 要保存的数据字典
        filename: 相对于项目根目录的文件路径
    """
    file_path = get_file_path(filename)
    with open(file_path, mode="w+", encoding="UTF-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
