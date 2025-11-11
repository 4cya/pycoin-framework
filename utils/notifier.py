# -*- coding: utf-8 -*-
"""
通知服务模块

提供多种消息通知方式的异步接口，包括：
- 企业微信机器人通知（文本、图片、图文、文件）
- 钉钉机器人通知（可选）
- Telegram 通知（可选）
- 邮件通知（可选）

使用示例：
    # 发送文本消息
    await Notifier.send_wxwork_text("bot1", "交易提醒：订单已成交")
    
    # 发送图片
    await Notifier.send_wxwork_image("bot1", "/path/to/image.png")
    
    # 发送图文消息
    await Notifier.send_wxwork_news(
        "bot1",
        title="市场分析",
        description="今日行情总结",
        url="https://example.com",
        picurl="https://example.com/pic.jpg"
    )

"""

import base64
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any

import smtplib
from email.message import EmailMessage

from utils.log import logger
from utils.http_client import AsyncHttpRequest
from utils.settings import settings


class NoticeError(Exception):
    """通知服务异常基类"""
    pass


class ConfigError(NoticeError):
    """配置错误异常"""
    pass


class SendError(NoticeError):
    """发送失败异常"""
    pass


class Notifier:
    """
    通知器类
    
    提供多种消息通知方式的统一接口，所有方法均为异步方法。
    支持企业微信、钉钉、Telegram、邮件等多种通知渠道。
    """

    # 企业微信相关URL
    WXWORK_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
    WXWORK_UPLOAD_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={key}&type=file"
    
    # 其他服务URL（可选）
    TELEGRAM_URL = "https://api.telegram.org"
    DING_URL = "https://oapi.dingtalk.com/robot/send?access_token={token}"
    
    # 配置缓存
    _wxwork_config: Optional[Dict[str, str]] = None
    _telegram_config: Optional[Dict[str, Any]] = None
    _ding_config: Optional[Dict[str, Any]] = None
    _email_config: Optional[Dict[str, str]] = None
    _proxy: Optional[str] = None
    
    @classmethod
    def _load_config(cls) -> None:
        """加载配置（延迟加载，避免初始化时配置不存在报错）"""
        if cls._wxwork_config is None:
            try:
                # 从应用配置加载企业微信配置
                cls._wxwork_config = settings.get_notification_config('wxwork')
            except (KeyError, Exception):
                cls._wxwork_config = {}
                logger.warning("企业微信配置未找到")
        
        if cls._proxy is None:
            # 从新配置结构加载代理配置
            cls._proxy = settings.get_proxy_config()


    @classmethod
    def _get_wxwork_webhook(cls, bot_name: str) -> str:
        """
        获取企业微信机器人的Webhook URL
        
        Args:
            bot_name: 机器人名称（配置文件中的key）
            
        Returns:
            str: 完整的Webhook URL
            
        Raises:
            ConfigError: 配置不存在或机器人未配置
        """
        cls._load_config()
        
        if not cls._wxwork_config:
            raise ConfigError("企业微信配置未找到，请检查配置文件")
        
        if bot_name not in cls._wxwork_config:
            raise ConfigError(f"企业微信机器人 '{bot_name}' 未配置")
        
        bot_key = cls._wxwork_config[bot_name]
        return cls.WXWORK_WEBHOOK_URL.format(key=bot_key)
    
    # ==================== 企业微信通知 ====================
    
    @classmethod
    async def send_wxwork_text(cls, bot_name: str, content: str) -> Dict[str, Any]:
        """
        发送企业微信文本消息
        
        Args:
            bot_name: 机器人名称（配置文件中的key）
            content: 文本内容
            
        Returns:
            Dict[str, Any]: 发送结果
            
        Raises:
            ConfigError: 配置错误
            SendError: 发送失败
            
        Example:
            result = await Notifier.send_wxwork_text("bot1", "订单已成交")
        """
        try:
            url = cls._get_wxwork_webhook(bot_name)
            
            body = {
                "msgtype": "text",
                "text": {"content": content}
            }
            
            headers = {"Content-Type": "application/json"}
            result = await AsyncHttpRequest.post(url, data=body, headers=headers)
            
            # 检查返回结果
            if isinstance(result, dict) and result.get("errcode") == 0:
                logger.info(f"企业微信文本消息发送成功: bot={bot_name}")
                return result
            else:
                error_msg = result.get("errmsg", "未知错误") if isinstance(result, dict) else str(result)
                logger.error(f"企业微信文本消息发送失败: {error_msg}")
                raise SendError(f"发送失败: {error_msg}")
                
        except ConfigError:
            raise
        except Exception as e:
            logger.error(f"发送企业微信文本消息异常: {e}")
            raise SendError(f"发送异常: {e}")

    @classmethod
    async def send_wxwork_image(cls, bot_name: str, image_path: str) -> Dict[str, Any]:
        """
        发送企业微信图片消息
        
        Args:
            bot_name: 机器人名称（配置文件中的key）
            image_path: 图片文件路径
            
        Returns:
            Dict[str, Any]: 发送结果
            
        Raises:
            ConfigError: 配置错误
            SendError: 发送失败
            FileNotFoundError: 图片文件不存在
            
        Example:
            result = await Notifier.send_wxwork_image("bot1", "/path/to/chart.png")
        """
        try:
            # 验证文件存在
            image_file = Path(image_path)
            if not image_file.exists():
                raise FileNotFoundError(f"图片文件不存在: {image_path}")
            
            # 读取图片并编码
            with open(image_file, "rb") as f:
                image_data = f.read()
                
                # Base64编码
                b64_data = base64.b64encode(image_data).decode("utf-8")
                
                # 计算MD5
                md5_hash = hashlib.md5(image_data).hexdigest()
            
            url = cls._get_wxwork_webhook(bot_name)
            
            body = {
                "msgtype": "image",
                "image": {
                    "base64": b64_data,
                    "md5": md5_hash
                }
            }
            
            headers = {"Content-Type": "application/json"}
            result = await AsyncHttpRequest.post(url, data=body, headers=headers)
            
            # 检查返回结果
            if isinstance(result, dict) and result.get("errcode") == 0:
                logger.info(f"企业微信图片消息发送成功: bot={bot_name}, file={image_file.name}")
                return result
            else:
                error_msg = result.get("errmsg", "未知错误") if isinstance(result, dict) else str(result)
                logger.error(f"企业微信图片消息发送失败: {error_msg}")
                raise SendError(f"发送失败: {error_msg}")
                
        except (ConfigError, FileNotFoundError):
            raise
        except Exception as e:
            logger.error(f"发送企业微信图片消息异常: {e}")
            raise SendError(f"发送异常: {e}")

    @classmethod
    async def send_wxwork_news(
        cls,
        bot_name: str,
        title: str,
        description: str,
        url: str,
        picurl: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送企业微信图文消息
        
        Args:
            bot_name: 机器人名称（配置文件中的key）
            title: 标题（不超过128字节）
            description: 描述（不超过512字节）
            url: 点击后跳转的链接
            picurl: 图文消息的图片链接（可选）
            
        Returns:
            Dict[str, Any]: 发送结果
            
        Raises:
            ConfigError: 配置错误
            SendError: 发送失败
            
        Example:
            result = await Notifier.send_wxwork_news(
                "bot1",
                title="市场分析报告",
                description="今日BTC行情总结",
                url="https://example.com/report",
                picurl="https://example.com/chart.jpg"
            )
        """
        try:
            webhook_url = cls._get_wxwork_webhook(bot_name)
            
            article = {
                "title": title,
                "description": description,
                "url": url
            }
            
            if picurl:
                article["picurl"] = picurl
            
            body = {
                "msgtype": "news",
                "news": {
                    "articles": [article]
                }
            }
            
            headers = {"Content-Type": "application/json"}
            result = await AsyncHttpRequest.post(webhook_url, data=body, headers=headers)
            
            # 检查返回结果
            if isinstance(result, dict) and result.get("errcode") == 0:
                logger.info(f"企业微信图文消息发送成功: bot={bot_name}, title={title}")
                return result
            else:
                error_msg = result.get("errmsg", "未知错误") if isinstance(result, dict) else str(result)
                logger.error(f"企业微信图文消息发送失败: {error_msg}")
                raise SendError(f"发送失败: {error_msg}")
                
        except ConfigError:
            raise
        except Exception as e:
            logger.error(f"发送企业微信图文消息异常: {e}")
            raise SendError(f"发送异常: {e}")

    @classmethod
    async def send_wxwork_file(cls, bot_name: str, file_path: str) -> Dict[str, Any]:
        """
        发送企业微信文件消息
        
        注意：文件大小必须在 5B ~ 20MB 之间
        
        Args:
            bot_name: 机器人名称（配置文件中的key）
            file_path: 文件路径
            
        Returns:
            Dict[str, Any]: 发送结果
            
        Raises:
            ConfigError: 配置错误
            SendError: 发送失败
            FileNotFoundError: 文件不存在
            ValueError: 文件大小不符合要求
            
        Example:
            result = await Notifier.send_wxwork_file("bot1", "/path/to/report.pdf")
        """
        try:
            # 验证文件存在
            file = Path(file_path)
            if not file.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 验证文件大小（5B ~ 20MB）
            file_size = file.stat().st_size
            if file_size < 5:
                raise ValueError(f"文件太小（< 5B）: {file_size} bytes")
            if file_size > 20 * 1024 * 1024:
                raise ValueError(f"文件太大（> 20MB）: {file_size / 1024 / 1024:.2f} MB")
            
            cls._load_config()
            
            if not cls._wxwork_config or bot_name not in cls._wxwork_config:
                raise ConfigError(f"企业微信机器人 '{bot_name}' 未配置")
            
            webhook_key = cls._wxwork_config[bot_name]
            
            # 步骤1: 上传文件获取 media_id（使用异步HTTP）
            upload_url = cls.WXWORK_UPLOAD_URL.format(key=webhook_key)
            
            with open(file, "rb") as f:
                file_data = f.read()
            
            # 使用 AsyncHttpRequest 上传文件
            upload_result = await AsyncHttpRequest.upload_file(
                upload_url,
                file_data=file_data,
                file_name=file.name,
                timeout=30
            )
            
            if not isinstance(upload_result, dict):
                raise SendError(f"文件上传失败: 返回格式错误")
            
            if upload_result.get("errcode") != 0:
                error_msg = upload_result.get("errmsg", "未知错误")
                raise SendError(f"文件上传失败: {error_msg}")
            
            media_id = upload_result.get("media_id")
            if not media_id:
                raise SendError("文件上传失败: 未获取到 media_id")
            
            logger.info(f"文件上传成功: file={file.name}, media_id={media_id}")
            
            # 步骤2: 发送文件消息
            webhook_url = cls.WXWORK_WEBHOOK_URL.format(key=webhook_key)
            
            body = {
                "msgtype": "file",
                "file": {"media_id": media_id}
            }
            
            headers = {"Content-Type": "application/json"}
            result = await AsyncHttpRequest.post(webhook_url, data=body, headers=headers)
            
            # 检查返回结果
            if isinstance(result, dict) and result.get("errcode") == 0:
                logger.info(f"企业微信文件消息发送成功: bot={bot_name}, file={file.name}")
                return result
            else:
                error_msg = result.get("errmsg", "未知错误") if isinstance(result, dict) else str(result)
                logger.error(f"企业微信文件消息发送失败: {error_msg}")
                raise SendError(f"发送失败: {error_msg}")
                
        except (ConfigError, FileNotFoundError, ValueError):
            raise
        except Exception as e:
            logger.error(f"发送企业微信文件消息异常: {e}")
            raise SendError(f"发送异常: {e}")

    # ==================== 其他通知方式（可选实现） ====================
    
    @classmethod
    async def send_telegram_text(
        cls,
        group: str,
        content: str,
        use_proxy: bool = False
    ) -> Dict[str, Any]:
        """
        发送Telegram文本消息
        
        Args:
            group: 群组名称（配置文件中的key）
            content: 文本内容
            use_proxy: 是否使用代理
            
        Returns:
            Dict[str, Any]: 发送结果
            
        Raises:
            ConfigError: 配置错误
            SendError: 发送失败
        """
        try:
            # 加载Telegram配置
            if cls._telegram_config is None:
                try:
                    cls._telegram_config = settings.get_notification_config('telegram')
                except (KeyError, Exception):
                    raise ConfigError("Telegram配置未找到")
            
            if group not in cls._telegram_config:
                raise ConfigError(f"Telegram群组 '{group}' 未配置")
            
            group_data = cls._telegram_config[group]
            bot_token = group_data.get("bot")
            chat_id = group_data.get("chat")
            
            if not bot_token or not chat_id:
                raise ConfigError(f"Telegram群组 '{group}' 配置不完整")
            
            url = f"{cls.TELEGRAM_URL}/bot{bot_token}/sendMessage"
            params = {
                "chat_id": chat_id,
                "text": content
            }
            
            proxy = cls._proxy if use_proxy else None
            result = await AsyncHttpRequest.get(url, params=params, proxy=proxy, timeout=10)
            
            if isinstance(result, dict) and result.get("ok"):
                logger.info(f"Telegram消息发送成功: group={group}")
                return result
            else:
                error_msg = result.get("description", "未知错误") if isinstance(result, dict) else str(result)
                raise SendError(f"发送失败: {error_msg}")
                
        except ConfigError:
            raise
        except Exception as e:
            logger.error(f"发送Telegram消息异常: {e}")
            raise SendError(f"发送异常: {e}")
    
    @classmethod
    async def send_ding_text(cls, content: str, at_all: bool = False) -> Dict[str, Any]:
        """
        发送钉钉文本消息
        
        Args:
            content: 文本内容
            at_all: 是否@所有人
            
        Returns:
            Dict[str, Any]: 发送结果
            
        Raises:
            ConfigError: 配置错误
            SendError: 发送失败
        """
        try:
            # 加载钉钉配置
            if cls._ding_config is None:
                try:
                    cls._ding_config = settings.get_notification_config('dingding')
                except (KeyError, Exception):
                    raise ConfigError("钉钉配置未找到")
            
            token = cls._ding_config.get("access_token")
            if not token:
                raise ConfigError("钉钉token未配置")
            
            url = cls.DING_URL.format(token=token)
            
            body = {
                "msgtype": "text",
                "text": {"content": content},
                "at": {"isAtAll": at_all}
            }
            
            headers = {"Content-Type": "application/json"}
            result = await AsyncHttpRequest.post(url, data=body, headers=headers)
            
            if isinstance(result, dict) and result.get("errcode") == 0:
                logger.info("钉钉消息发送成功")
                return result
            else:
                error_msg = result.get("errmsg", "未知错误") if isinstance(result, dict) else str(result)
                raise SendError(f"发送失败: {error_msg}")
                
        except ConfigError:
            raise
        except Exception as e:
            logger.error(f"发送钉钉消息异常: {e}")
            raise SendError(f"发送异常: {e}")
    
    @classmethod
    async def send_email(cls, subject: str, content: str, to: Optional[str] = None) -> None:
        """
        发送邮件
        
        Args:
            subject: 邮件主题
            content: 邮件内容
            to: 收件人邮箱（可选，默认使用配置中的receiver）
            
        Raises:
            ConfigError: 配置错误
            SendError: 发送失败
        """
        try:
            # 加载邮件配置
            if cls._email_config is None:
                try:
                    cls._email_config = settings.get_notification_config('email')
                except (KeyError, Exception):
                    raise ConfigError("邮件配置未找到")
            
            sender = cls._email_config.get("sender")
            # 支持多个接收者
            receivers = cls._email_config.get("receivers", [])
            receiver = to or (receivers[0] if receivers else None)
            server = cls._email_config.get("smtp_server")
            port = cls._email_config.get("smtp_port")
            username = cls._email_config.get("username")
            password = cls._email_config.get("password")
            
            if not all([sender, receiver, server, port, username, password]):
                raise ConfigError("邮件配置不完整")
            
            # 构建邮件
            msg = EmailMessage()
            msg["From"] = sender
            msg["To"] = receiver
            msg["Subject"] = subject
            msg.set_content(content)
            
            # 发送邮件（同步操作，在异步环境中执行）
            with smtplib.SMTP_SSL(server, int(port)) as smtp:
                smtp.login(username, password)
                smtp.send_message(msg)
            
            logger.info(f"邮件发送成功: to={receiver}, subject={subject}")
            
        except ConfigError:
            raise
        except Exception as e:
            logger.error(f"发送邮件异常: {e}")
            raise SendError(f"发送异常: {e}")
