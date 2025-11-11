# -*- coding: utf-8 -*-
"""
应用配置管理模块

提供统一的配置文件加载和访问功能，支持应用配置和敏感信息分离。
"""

from typing import Dict, Any, Optional, List
import os
from pathlib import Path

from utils import tools


class Settings:
    """
    应用配置管理类
    
    负责加载和管理配置文件：
    - config/app.yaml: 应用配置（非敏感信息）
    - secrets/accounts.yaml: 账户密钥配置（敏感信息）
    
    配置文件允许不存在，但访问不存在的配置项会抛出 KeyError。
    """

    def __init__(self):
        """初始化配置管理器，加载所有配置文件"""
        # 加载应用配置（非敏感）
        self._app_config: Dict[str, Any] = tools.load_yaml("config/app.yaml")
        
        # 加载账户密钥配置（敏感）
        self._accounts: Dict[str, Any] = tools.load_yaml("secrets/accounts.yaml")
        
        # 支持环境变量覆盖
        self._load_env_overrides()
    
    def _load_env_overrides(self) -> None:
        """从环境变量加载配置覆盖（可选功能）"""
        # 示例：支持通过环境变量覆盖 Redis 配置
        # if os.getenv('REDIS_HOST'):
        #     self._app_config.setdefault('redis', {})['host'] = os.getenv('REDIS_HOST')
        pass
    
    # ==================== 应用配置访问 ====================
    
    def get_config(self, key: Optional[str] = None, default: Any = None) -> Any:
        """
        获取应用配置
        
        Args:
            key: 配置键名（支持点号分隔的多级键，如 'redis.host'）
                 为 None 时返回所有配置
            default: 默认值，如果配置不存在则返回此值（为 None 时抛出异常）
            
        Returns:
            Any: 配置值
            
        Raises:
            KeyError: 配置项不存在且未提供默认值时抛出
            
        Examples:
            >>> config.get_config('redis')
            {'host': 'localhost', 'port': 6379}
            
            >>> config.get_config('redis.host')
            'localhost'
            
            >>> config.get_config('not_exist', default='default_value')
            'default_value'
        """
        if key is None:
            return self._app_config
        
        # 支持点号分隔的多级键
        keys = key.split('.')
        value = self._app_config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            if default is not None:
                return default
            raise KeyError(f"配置项不存在: {key}")
    
    def get_redis_config(self) -> Dict[str, Any]:
        """
        获取 Redis 配置
        
        Returns:
            Dict[str, Any]: Redis 配置字典
        """
        return self.get_config('redis', default={})
    
    def get_heartbeat_config(self) -> Dict[str, Any]:
        """
        获取心跳配置
        
        Returns:
            Dict[str, Any]: 心跳配置字典
        """
        return self.get_config('heartbeat', default={})
    
    def get_proxy_config(self) -> Optional[str]:
        """
        获取代理配置
        
        Returns:
            Optional[str]: 代理地址，如 'http://127.0.0.1:7890'，未启用时返回 None
        """
        proxy_config = self.get_config('proxy', default={})
        if not proxy_config or not proxy_config.get('enabled'):
            return None
        return proxy_config.get('http') or proxy_config.get('https')
    
    def get_logging_config(self) -> Dict[str, Any]:
        """
        获取日志配置
        
        Returns:
            Dict[str, Any]: 日志配置字典，包含默认值
        """
        default_logging = {
            'level': 'INFO',
            'file_enabled': True,
            'console_enabled': True,
            'path': './logs',
            'file_size': '10MB',
            'backup_count': 5
        }
        
        logging_config = self.get_config('logging', default={})
        # 合并默认配置和用户配置
        default_logging.update(logging_config)
        return default_logging
    
    # ==================== 账户配置访问 ====================
    
    def get_account(self, exchange: str, account_name: str = None) -> Dict[str, Any]:
        """
        获取交易所账户配置
        
        Args:
            exchange: 交易所名称（binance/okex/huobi等）
            account_name: 账户名称（可选，用于多账户场景）
            
        Returns:
            Dict[str, Any]: 账户配置，包含 api_key, secret_key 等
            
        Raises:
            KeyError: 账户配置不存在时抛出
            
        Examples:
            >>> config.get_account('binance')
            {'api_key': '...', 'secret_key': '...'}
        """
        exchanges = self._accounts.get('exchanges', {})
        
        if exchange not in exchanges:
            raise KeyError(f"交易所账户配置不存在: {exchange}")
        
        account = exchanges[exchange]
        
        # 支持多账户场景
        if account_name and isinstance(account, dict) and 'accounts' in account:
            accounts = account['accounts']
            if account_name not in accounts:
                raise KeyError(f"账户配置不存在: {exchange}.{account_name}")
            return accounts[account_name]
        
        return account
    
    def get_notification_config(self, service: Optional[str] = None, key_name: Optional[str] = None) -> Any:
        """
        获取通知服务配置
        
        Args:
            service: 服务名称（wxwork/telegram/dingding/email），为 None 时返回所有通知配置
            key_name: 配置项名称（可选），为 None 时返回该服务的所有配置
            
        Returns:
            Any: 配置值或配置字典
            
        Raises:
            KeyError: 配置不存在时抛出
            
        Examples:
            >>> settings.get_notification_config('wxwork', 'lyy')
            '2c3a1482-50a9-430a-80f5-abdc9ef90e20'
            
            >>> settings.get_notification_config('wxwork')
            {'lyy': '...', 'xhr': '...', 'doraemon': '...'}
            
            >>> settings.get_notification_config()
            {'wxwork': {...}, 'telegram': {...}}
        """
        notifications = self.get_config('notifications', default={})
        
        if service is None:
            return notifications
        
        if service not in notifications:
            raise KeyError(f"通知服务配置不存在: {service}")
        
        service_config = notifications[service]
        
        if key_name is None:
            return service_config
        
        if key_name not in service_config:
            raise KeyError(f"配置项不存在: {service}.{key_name}")
        
        return service_config[key_name]
    
    def get_api_key(self, service: str, key_name: str = 'api_key') -> str:
        """
        获取 API 密钥
        
        Args:
            service: 服务名称
            key_name: 密钥字段名，默认为 'api_key'
            
        Returns:
            str: API 密钥
            
        Raises:
            KeyError: 密钥不存在时抛出
        """
        api_keys = self._accounts.get('api_keys', {})
        
        if service not in api_keys:
            raise KeyError(f"API 密钥配置不存在: {service}")
        
        service_keys = api_keys[service]
        
        if key_name not in service_keys:
            raise KeyError(f"密钥字段不存在: {service}.{key_name}")
        
        return service_keys[key_name]
    
    # ==================== 辅助方法 ====================
    
    def has_config(self, key: str) -> bool:
        """
        检查配置项是否存在
        
        Args:
            key: 配置键名（支持点号分隔）
            
        Returns:
            bool: 配置项存在返回 True，否则返回 False
        """
        try:
            self.get_config(key)
            return True
        except KeyError:
            return False
    
    def has_account(self, exchange: str) -> bool:
        """
        检查交易所账户配置是否存在
        
        Args:
            exchange: 交易所名称
            
        Returns:
            bool: 账户配置存在返回 True，否则返回 False
        """
        try:
            self.get_account(exchange)
            return True
        except KeyError:
            return False
    
    def list_exchanges(self) -> List[str]:
        """
        列出所有已配置的交易所
        
        Returns:
            List[str]: 交易所名称列表
        """
        exchanges = self._accounts.get('exchanges', {})
        return list(exchanges.keys())
    
    def list_notification_services(self) -> List[str]:
        """
        列出所有已配置的通知服务
        
        Returns:
            List[str]: 通知服务名称列表
        """
        notifications = self.get_config('notifications', default={})
        return list(notifications.keys())
    
    def reload(self) -> None:
        """重新加载所有配置文件"""
        self._app_config = tools.load_yaml("config/app.yaml")
        self._accounts = tools.load_yaml("secrets/accounts.yaml")
        self._load_env_overrides()
    
    def __repr__(self) -> str:
        """返回配置对象的字符串表示（隐藏敏感信息）"""
        return (
            f"Settings("
            f"app_sections={list(self._app_config.keys())}, "
            f"exchanges={self.list_exchanges()}, "
            f"notifications={self.list_notification_services()}"
            f")"
        )


# 全局配置实例
settings = Settings()
