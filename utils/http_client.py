# -*- coding: utf-8 -*-
"""
HTTP异步请求工具模块

提供基于aiohttp的异步HTTP请求封装，支持：
- GET/POST/PUT/DELETE等常用HTTP方法
- JSON和表单数据提交
- 文件下载（图片、文档等）
- 自动连接池管理
- 智能响应解析（JSON/HTML/Text）

"""

from typing import Optional, Dict, Any, Tuple, Union
from pathlib import Path
import aiohttp
from urllib.parse import urlparse
from aiohttp import ClientTimeout, ClientError

from utils.log import logger


# HTTP成功状态码集合
SUCCESS_CODES = {200, 201, 202, 203, 204, 205, 206}

# 类型别名
HttpResponse = Tuple[Optional[int], Optional[Union[Dict, str, bytes]], Optional[Exception]]


class AsyncHttpRequest:
    """
    异步HTTP请求类
    
    提供异步HTTP请求功能，每个域名维护独立的session连接池，
    提高请求效率并节省资源。
    """

    _SESSIONS: Dict[str, aiohttp.ClientSession] = {}  # 域名 -> Session映射

    @classmethod
    async def get(
        cls,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        **kwargs
    ) -> HttpResponse:
        """
        发起HTTP GET请求
        
        Args:
            url: 请求URL
            params: URL查询参数
            headers: 请求头
            timeout: 超时时间（秒）
            **kwargs: 其他aiohttp参数
            
        Returns:
            Tuple[status_code, response_data, error]
        """
        return await cls.fetch("GET", url, params=params, headers=headers, timeout=timeout, **kwargs)

    @classmethod
    async def post(
        cls,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        **kwargs
    ) -> HttpResponse:
        """
        发起HTTP POST请求
        
        Args:
            url: 请求URL
            params: URL查询参数
            data: 表单数据或字符串数据
            json: JSON数据（自动序列化）
            headers: 请求头
            timeout: 超时时间（秒）
            **kwargs: 其他aiohttp参数
            
        Returns:
            Tuple[status_code, response_data, error]
        """
        return await cls.fetch("POST", url, params=params, data=data, json=json, 
                              headers=headers, timeout=timeout, **kwargs)

    @classmethod
    async def put(
        cls,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        **kwargs
    ) -> HttpResponse:
        """
        发起HTTP PUT请求
        
        Args:
            url: 请求URL
            params: URL查询参数
            data: 表单数据或字符串数据
            json: JSON数据（自动序列化）
            headers: 请求头
            timeout: 超时时间（秒）
            **kwargs: 其他aiohttp参数
            
        Returns:
            Tuple[status_code, response_data, error]
        """
        return await cls.fetch("PUT", url, params=params, data=data, json=json,
                              headers=headers, timeout=timeout, **kwargs)

    @classmethod
    async def delete(
        cls,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        **kwargs
    ) -> HttpResponse:
        """
        发起HTTP DELETE请求
        
        Args:
            url: 请求URL
            params: URL查询参数
            data: 表单数据或字符串数据
            json: JSON数据（自动序列化）
            headers: 请求头
            timeout: 超时时间（秒）
            **kwargs: 其他aiohttp参数
            
        Returns:
            Tuple[status_code, response_data, error]
        """
        return await cls.fetch("DELETE", url, params=params, data=data, json=json,
                              headers=headers, timeout=timeout, **kwargs)

    @classmethod
    async def fetch(
        cls,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        **kwargs
    ) -> HttpResponse:
        """
        发起HTTP请求（通用方法）
        
        Args:
            method: HTTP方法（GET/POST/PUT/DELETE/PATCH等）
            url: 请求URL
            params: URL查询参数
            data: 表单数据或字符串数据
            json: JSON数据（自动序列化）
            headers: 请求头
            timeout: 超时时间（秒）
            **kwargs: 其他aiohttp参数
            
        Returns:
            Tuple[status_code, response_data, error]:
                - 成功: (status_code, response_data, None)
                - 失败: (status_code/None, None, error)
        """
        session = cls._get_session(url)
        timeout_obj = ClientTimeout(total=timeout)
        
        try:
            # 发起请求
            async with session.request(
                method=method.upper(),
                url=url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                timeout=timeout_obj,
                **kwargs
            ) as response:
                status_code = response.status
                
                # 检查状态码
                if status_code not in SUCCESS_CODES:
                    error_text = await response.text()
                    logger.error(
                        f"HTTP请求失败: {method} {url}",
                        status=status_code,
                        params=params,
                        response=error_text[:200]  # 只记录前200字符
                    )
                    return status_code, None, error_text
                
                # 解析响应
                result = await cls._parse_response(response)
                
                logger.debug(
                    f"HTTP请求成功: {method} {url}",
                    status=status_code,
                    params=params,
                    response_type=type(result).__name__
                )
                
                return status_code, result, None
                
        except ClientError as e:
            logger.error(f"HTTP请求异常: {method} {url}", error=str(e), params=params)
            return None, None, e
        except Exception as e:
            logger.error(f"HTTP请求未知异常: {method} {url}", error=str(e), params=params)
            return None, None, e

    @classmethod
    async def download_file(
        cls,
        url: str,
        save_path: Union[str, Path],
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 60,
        **kwargs
    ) -> HttpResponse:
        """
        下载文件（图片、文档等）
        
        Args:
            url: 文件URL
            save_path: 保存路径
            params: URL查询参数
            headers: 请求头
            timeout: 超时时间（秒）
            **kwargs: 其他aiohttp参数
            
        Returns:
            Tuple[status_code, file_path, error]:
                - 成功: (status_code, file_path, None)
                - 失败: (status_code/None, None, error)
        """
        session = cls._get_session(url)
        timeout_obj = ClientTimeout(total=timeout)
        save_path = Path(save_path)
        
        try:
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout_obj,
                **kwargs
            ) as response:
                status_code = response.status
                
                if status_code not in SUCCESS_CODES:
                    error_text = await response.text()
                    logger.error(f"文件下载失败: {url}", status=status_code, error=error_text[:200])
                    return status_code, None, error_text
                
                # 确保目录存在
                save_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 写入文件
                content = await response.read()
                save_path.write_bytes(content)
                
                logger.info(f"文件下载成功: {save_path}", url=url, size=f"{len(content)} bytes")
                return status_code, str(save_path), None
                
        except Exception as e:
            logger.error(f"文件下载异常: {url}", error=str(e), save_path=str(save_path))
            return None, None, e

    @classmethod
    async def upload_file(
        cls,
        url: str,
        file_data: bytes,
        file_name: str,
        field_name: str = "media",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        **kwargs
    ) -> Union[Dict, str]:
        """
        上传文件
        
        Args:
            url: 上传URL
            file_data: 文件字节数据
            file_name: 文件名
            field_name: 表单字段名（默认: media）
            params: URL查询参数
            headers: 请求头
            timeout: 超时时间（秒）
            **kwargs: 其他aiohttp参数
            
        Returns:
            Union[Dict, str]: 上传结果（JSON或文本）
            
        Raises:
            Exception: 上传失败
            
        Example:
            with open("file.pdf", "rb") as f:
                data = f.read()
            result = await AsyncHttpRequest.upload_file(
                "https://api.example.com/upload",
                file_data=data,
                file_name="file.pdf"
            )
        """
        try:
            session = cls._get_session(url)
            
            # 构建multipart/form-data
            form_data = aiohttp.FormData()
            form_data.add_field(
                field_name,
                file_data,
                filename=file_name,
                content_type='application/octet-stream'
            )
            
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            
            async with session.post(
                url,
                data=form_data,
                params=params,
                headers=headers,
                timeout=timeout_obj,
                **kwargs
            ) as response:
                status_code = response.status
                
                if status_code not in SUCCESS_CODES:
                    error_text = await response.text()
                    logger.error(
                        f"文件上传失败: {url}",
                        status=status_code,
                        file=file_name,
                        response=error_text[:200]
                    )
                    raise Exception(f"上传失败: HTTP {status_code}")
                
                # 解析响应
                result = await cls._parse_response(response)
                
                logger.info(
                    f"文件上传成功: {file_name}",
                    url=url,
                    size=f"{len(file_data)} bytes",
                    status=status_code
                )
                
                return result
                
        except Exception as e:
            logger.error(f"文件上传异常: {url}", error=str(e), file=file_name)
            raise

    @classmethod
    async def _parse_response(cls, response: aiohttp.ClientResponse) -> Union[Dict, str, bytes]:
        """
        智能解析响应内容
        
        根据Content-Type自动选择解析方式：
        - application/json -> JSON字典
        - text/* -> 文本字符串
        - 其他 -> 字节数据
        
        Args:
            response: aiohttp响应对象
            
        Returns:
            解析后的响应数据
        """
        content_type = response.headers.get('Content-Type', '').lower()
        
        try:
            # 尝试解析为JSON
            if 'application/json' in content_type:
                return await response.json()
            
            # 解析为文本
            if 'text/' in content_type or 'application/xml' in content_type:
                return await response.text()
            
            # 默认返回字节
            return await response.read()
            
        except Exception:
            # 解析失败，返回文本
            return await response.text()

    @classmethod
    def _get_session(cls, url: str) -> aiohttp.ClientSession:
        """
        获取URL对应的Session连接
        
        每个域名维护一个独立的Session，复用连接池提高性能。
        
        Args:
            url: 请求URL
            
        Returns:
            aiohttp.ClientSession: Session对象
        """
        parsed_url = urlparse(url)
        key = parsed_url.netloc or parsed_url.hostname
        
        if key not in cls._SESSIONS:
            # 创建新的Session，配置连接池参数
            connector = aiohttp.TCPConnector(
                limit=100,  # 最大连接数
                limit_per_host=30,  # 每个主机最大连接数
                ttl_dns_cache=300  # DNS缓存时间（秒）
            )
            cls._SESSIONS[key] = aiohttp.ClientSession(connector=connector)
            logger.debug(f"创建新的HTTP Session: {key}")
        
        return cls._SESSIONS[key]

    @classmethod
    async def close_all(cls) -> None:
        """
        关闭所有Session连接
        
        应在程序退出时调用，释放资源。
        """
        for key, session in cls._SESSIONS.items():
            await session.close()
            logger.debug(f"关闭HTTP Session: {key}")
        cls._SESSIONS.clear()
        logger.info("所有HTTP Session已关闭")


# 便捷的全局实例
http = AsyncHttpRequest()
