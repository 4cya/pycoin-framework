# -*- coding: utf-8 -*-
"""
Redis异步操作工具模块

提供Redis的异步操作封装，支持字符串、列表、集合、哈希等数据类型的操作。
使用 redis-py 库（v4.0+）的异步支持。

注意：需要安装 redis[asyncio]
    pip install redis[asyncio]
"""

from typing import Optional, List, Dict, Any, Union
import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from utils.settings import settings
from utils.log import logger


class AioRedis:
    """
    异步Redis操作类
    
    提供Redis常用操作的异步封装，包括：
    - 基础操作：keys, delete
    - 字符串操作：set, get, getset
    - 列表操作：lpush, rpop, llen, lrem
    - 集合操作：sadd, spop, srem, scard
    - 哈希操作：hset, hget, hdel, hmset, hexists, hkeys, hvals
    """

    _pool: Optional[Redis] = None
    _instance = None

    def __new__(cls):
        """单例模式：确保整个应用只有一个Redis连接池实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_redis_pool(self) -> Redis:
        """
        获取Redis连接池
        
        Returns:
            Redis: Redis异步连接池实例
            
        Raises:
            RedisError: Redis连接失败时抛出
        """
        # 创建连接池（如果不存在）
        if not self._pool:
            try:
                # 从新的配置结构加载 Redis 配置
                redis_config = settings.get_redis_config()
                
                # 如果配置为空，使用默认配置
                if not redis_config:
                    redis_config = {
                        'host': 'localhost',
                        'port': 6379,
                        'decode_responses': True
                    }
                    logger.warning("未找到Redis配置，使用默认配置")
                
                # 构建 Redis URL
                host = redis_config.get('host', 'localhost')
                port = redis_config.get('port', 6379)
                db = redis_config.get('db', 0)
                
                self._pool = await aioredis.from_url(
                    f"redis://{host}:{port}/{db}",
                    password=redis_config.get('password'),
                    encoding='utf-8',
                    decode_responses=redis_config.get('decode_responses', True),
                    max_connections=redis_config.get('max_connections', 10)
                )
                logger.info(f"Redis连接池创建成功: {host}:{port}/{db}")
            except RedisError as e:
                logger.error(f"Redis连接失败: {e}")
                raise
        
        return self._pool

    # ------------- 基础操作 ------------------

    async def keys(self, pattern: str = "*") -> Optional[List[str]]:
        """
        查询匹配的键名列表
        
        Args:
            pattern: 匹配模式，支持通配符，默认"*"表示所有键
            
        Returns:
            Optional[List[str]]: 匹配的键名列表，失败返回None
        """
        try:
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.keys(pattern)
        except RedisError as e:
            logger.error(f"Redis查询键值集合失败: {e}", pattern=pattern)
            return None

    async def delete(self, *keys: str) -> Optional[int]:
        """
        删除一个或多个键
        
        Args:
            *keys: 要删除的键名（可变参数）
            
        Returns:
            Optional[int]: 成功删除的键数量，失败返回None
        """
        try:
            if not keys:
                logger.warning("删除操作未提供任何键名")
                return 0
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.delete(*keys)
        except RedisError as e:
            logger.error(f"Redis删除键失败: {e}", keys=keys)
            return None

    # ------------- 字符串操作 ------------------

    async def set(
        self, 
        key: str, 
        value: Union[str, int, float], 
        ex: Optional[int] = None
    ) -> Optional[bool]:
        """
        设置键值对
        
        Args:
            key: 键名
            value: 值
            ex: 过期时间（秒），None表示不过期
            
        Returns:
            Optional[bool]: 成功返回True，失败返回None
        """
        try:
            if not key:
                logger.warning("set操作键名为空")
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.set(key, value, ex=ex)
        except RedisError as e:
            logger.error(f"Redis写入失败: {e}", key=key)
            return None

    async def get(self, key: str) -> Optional[str]:
        """
        获取键对应的值
        
        Args:
            key: 键名
            
        Returns:
            Optional[str]: 键对应的值，不存在或失败返回None
        """
        try:
            if not key:
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.get(key)
        except RedisError as e:
            logger.error(f"Redis读取失败: {e}", key=key)
            return None

    async def getset(self, key: str, new_value: Union[str, int, float]) -> Optional[str]:
        """
        设置新值并返回旧值
        
        Args:
            key: 键名
            new_value: 新值
            
        Returns:
            Optional[str]: 旧值，不存在或失败返回None
        """
        try:
            if not key:
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.getset(key, new_value)
        except RedisError as e:
            logger.error(f"Redis getset失败: {e}", key=key)
            return None

    # ------------- 列表操作 ------------------

    async def lpush(self, key: str, *values: Union[str, int, float]) -> Optional[int]:
        """
        从列表左侧插入一个或多个值
        
        Args:
            key: 键名
            *values: 要插入的值（可变参数）
            
        Returns:
            Optional[int]: 插入后列表长度，失败返回None
        """
        try:
            if not key or not values:
                logger.warning("lpush操作键名或值为空")
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.lpush(key, *values)
        except RedisError as e:
            logger.error(f"Redis lpush失败: {e}", key=key)
            return None

    async def rpop(self, key: str) -> Optional[str]:
        """
        从列表右侧弹出一个元素
        
        Args:
            key: 键名
            
        Returns:
            Optional[str]: 弹出的元素值，列表为空或失败返回None
        """
        try:
            if not key:
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.rpop(key)
        except RedisError as e:
            logger.error(f"Redis rpop失败: {e}", key=key)
            return None

    async def llen(self, key: str) -> Optional[int]:
        """
        获取列表长度
        
        Args:
            key: 键名
            
        Returns:
            Optional[int]: 列表长度，失败返回None
        """
        try:
            if not key:
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.llen(key)
        except RedisError as e:
            logger.error(f"Redis llen失败: {e}", key=key)
            return None

    async def lrem(self, key: str, value: Union[str, int, float], count: int = 0) -> Optional[int]:
        """
        从列表中删除元素
        
        Args:
            key: 键名
            value: 要删除的值
            count: 删除数量，0表示删除所有匹配项
            
        Returns:
            Optional[int]: 删除的元素数量，失败返回None
        """
        try:
            if not key:
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.lrem(key, count, value)
        except RedisError as e:
            logger.error(f"Redis lrem失败: {e}", key=key)
            return None

    # ------------- 集合操作 ------------------

    async def scard(self, key: str) -> Optional[int]:
        """
        获取集合中元素数量
        
        Args:
            key: 键名
            
        Returns:
            Optional[int]: 集合元素数量，失败返回None
        """
        try:
            if not key:
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.scard(key)
        except RedisError as e:
            logger.error(f"Redis scard失败: {e}", key=key)
            return None

    async def sadd(self, key: str, *values: Union[str, int, float]) -> Optional[int]:
        """
        向集合中添加一个或多个元素
        
        Args:
            key: 键名
            *values: 要添加的值（可变参数）
            
        Returns:
            Optional[int]: 成功添加的元素数量，失败返回None
        """
        try:
            if not key or not values:
                logger.warning("sadd操作键名或值为空")
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.sadd(key, *values)
        except RedisError as e:
            logger.error(f"Redis sadd失败: {e}", key=key)
            return None

    async def spop(self, key: str, count: Optional[int] = None) -> Optional[Union[str, List[str]]]:
        """
        从集合中随机弹出一个或多个元素
        
        Args:
            key: 键名
            count: 弹出数量，None表示弹出1个
            
        Returns:
            Optional[Union[str, List[str]]]: 弹出的元素，失败返回None
        """
        try:
            if not key:
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.spop(key, count)
        except RedisError as e:
            logger.error(f"Redis spop失败: {e}", key=key)
            return None

    async def srem(self, key: str, *values: Union[str, int, float]) -> Optional[int]:
        """
        从集合中移除一个或多个元素
        
        Args:
            key: 键名
            *values: 要移除的值（可变参数）
            
        Returns:
            Optional[int]: 成功移除的元素数量，失败返回None
        """
        try:
            if not key or not values:
                logger.warning("srem操作键名或值为空")
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.srem(key, *values)
        except RedisError as e:
            logger.error(f"Redis srem失败: {e}", key=key)
            return None

    # ------------- 哈希操作 ------------------

    async def hset(
        self, 
        key: str, 
        field: str, 
        value: Union[str, int, float]
    ) -> Optional[int]:
        """
        设置哈希表字段的值
        
        Args:
            key: 键名
            field: 字段名
            value: 字段值
            
        Returns:
            Optional[int]: 1表示新字段，0表示更新已有字段，失败返回None
        """
        try:
            if not key or not field:
                logger.warning("hset操作键名或字段名为空")
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.hset(key, field, value)
        except RedisError as e:
            logger.error(f"Redis hset失败: {e}", key=key, field=field)
            return None

    async def hmset(self, key: str, mapping: Dict[str, Any]) -> Optional[bool]:
        """
        批量设置哈希表多个字段
        
        Args:
            key: 键名
            mapping: 字段-值字典
            
        Returns:
            Optional[bool]: 成功返回True，失败返回None
        """
        try:
            if not key or not mapping:
                logger.warning("hmset操作键名或映射为空")
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.hset(key, mapping=mapping)
        except RedisError as e:
            logger.error(f"Redis hmset失败: {e}", key=key)
            return None

    async def hget(self, key: str, field: str) -> Optional[str]:
        """
        获取哈希表字段的值
        
        Args:
            key: 键名
            field: 字段名
            
        Returns:
            Optional[str]: 字段值，不存在或失败返回None
        """
        try:
            if not key or not field:
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.hget(key, field)
        except RedisError as e:
            logger.error(f"Redis hget失败: {e}", key=key, field=field)
            return None

    async def hexists(self, key: str, field: str) -> Optional[bool]:
        """
        检查哈希表字段是否存在
        
        Args:
            key: 键名
            field: 字段名
            
        Returns:
            Optional[bool]: 存在返回True，不存在返回False，失败返回None
        """
        try:
            if not key or not field:
                return False
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.hexists(key, field)
        except RedisError as e:
            logger.error(f"Redis hexists失败: {e}", key=key, field=field)
            return None

    async def hkeys(self, key: str) -> Optional[List[str]]:
        """
        获取哈希表所有字段名
        
        Args:
            key: 键名
            
        Returns:
            Optional[List[str]]: 字段名列表，失败返回None
        """
        try:
            if not key:
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.hkeys(key)
        except RedisError as e:
            logger.error(f"Redis hkeys失败: {e}", key=key)
            return None

    async def hvals(self, key: str) -> Optional[List[str]]:
        """
        获取哈希表所有字段值
        
        Args:
            key: 键名
            
        Returns:
            Optional[List[str]]: 字段值列表，失败返回None
        """
        try:
            if not key:
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.hvals(key)
        except RedisError as e:
            logger.error(f"Redis hvals失败: {e}", key=key)
            return None

    async def hdel(self, key: str, *fields: str) -> Optional[int]:
        """
        删除哈希表一个或多个字段
        
        Args:
            key: 键名
            *fields: 要删除的字段名（可变参数）
            
        Returns:
            Optional[int]: 成功删除的字段数量，失败返回None
        """
        try:
            if not key or not fields:
                logger.warning("hdel操作键名或字段名为空")
                return None
            if not self._pool:
                await self.get_redis_pool()
            return await self._pool.hdel(key, *fields)
        except RedisError as e:
            logger.error(f"Redis hdel失败: {e}", key=key, fields=fields)
            return None

    async def close(self) -> None:
        """
        关闭Redis连接池
        """
        try:
            if self._pool:
                await self._pool.close()
                logger.info("Redis连接池已关闭")
        except Exception as e:
            logger.error(f"关闭Redis连接池失败: {e}")


# 创建全局Redis实例（单例）
redis_client = AioRedis()
