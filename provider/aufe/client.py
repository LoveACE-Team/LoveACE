import re
import httpx
import binascii
import asyncio
import time
import random
from typing import Optional, Dict, Any, Type, Callable, Union, List
from contextvars import ContextVar
from functools import wraps
from enum import Enum
from dataclasses import dataclass
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as symmetric_padding
from base64 import b64encode
from bs4 import BeautifulSoup
from loguru import logger
from typing import TypeVar

from pydantic import BaseModel


# 用于存储学生ID和VPN连接上下文的上下文变量
student_id_var: ContextVar[Optional[str]] = ContextVar("student_id", default=None)
vpn_context_var: ContextVar[Dict[str, Any]] = ContextVar("vpn_context", default={})

# 全局AUFE连接池
_aufe_connections: Dict[str, "AUFEConnection"] = {}

T_BaseModel = TypeVar("T_BaseModel", bound=Type[BaseModel])


# 导入配置管理器
from config import config_manager

def get_aufe_config():
    """获取AUFE配置"""
    return config_manager.get_settings().aufe

# 保留常量类以保持向后兼容性，但从配置文件读取值
class AUFEConfig:
    """AUFE连接配置常量（从配置文件读取）"""
    
    @property
    def DEFAULT_TIMEOUT(self):
        return get_aufe_config().default_timeout
    
    @property
    def MAX_RETRIES(self):
        return get_aufe_config().max_retries
    
    @property
    def MAX_RECONNECT_RETRIES(self):
        return get_aufe_config().max_reconnect_retries
    
    @property
    def ACTIVITY_TIMEOUT(self):
        return get_aufe_config().activity_timeout
    
    @property
    def MONITOR_INTERVAL(self):
        return get_aufe_config().monitor_interval
    
    @property
    def RETRY_BASE_DELAY(self):
        return get_aufe_config().retry_base_delay
    
    @property
    def RETRY_MAX_DELAY(self):
        return get_aufe_config().retry_max_delay
    
    @property
    def RETRY_EXPONENTIAL_BASE(self):
        return get_aufe_config().retry_exponential_base
    
    @property
    def UAAP_BASE_URL(self):
        return get_aufe_config().uaap_base_url
    
    @property
    def UAAP_LOGIN_URL(self):
        return get_aufe_config().uaap_login_url
    
    @property
    def DEFAULT_HEADERS(self):
        return get_aufe_config().default_headers

# 创建全局实例以保持向后兼容性
AUFEConfig = AUFEConfig()


class AUFEError(Exception):
    """AUFE基础异常类"""
    pass


class AUFELoginError(AUFEError):
    """登录失败异常"""
    pass


class AUFEConnectionError(AUFEError):
    """连接异常"""
    pass


class AUFETimeoutError(AUFEError):
    """超时异常"""
    pass


class AUFEParseError(AUFEError):
    """数据解析异常"""
    pass


class RetryStrategy(Enum):
    """重试策略枚举"""
    IMMEDIATE = "immediate"
    FIXED_DELAY = "fixed_delay" 
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = AUFEConfig.MAX_RETRIES
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = AUFEConfig.RETRY_BASE_DELAY
    max_delay: float = AUFEConfig.RETRY_MAX_DELAY
    exponential_base: float = AUFEConfig.RETRY_EXPONENTIAL_BASE
    jitter: bool = True
    retry_on_exceptions: tuple = (AUFEConnectionError, AUFETimeoutError, httpx.RequestError)
    

def activity_tracker(func: Callable) -> Callable:
    """活动跟踪装饰器"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if hasattr(self, '_update_activity'):
            self._update_activity()
        return func(self, *args, **kwargs)
    
    @wraps(func)
    async def async_wrapper(self, *args, **kwargs):
        if hasattr(self, '_update_activity'):
            self._update_activity()
        return await func(self, *args, **kwargs)
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper


def retry_async(config: Optional[RetryConfig] = None):
    """异步重试装饰器"""
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except config.retry_on_exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts - 1:
                        break
                    
                    delay = _calculate_delay(attempt, config)
                    logger.warning(
                        f"第 {attempt + 1} 次调用失败: {str(e)}, "
                        f"{delay:.2f}秒后重试"
                    )
                    await asyncio.sleep(delay)
                except Exception as e:
                    # 非重试异常直接抛出
                    raise e
            
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """计算重试延迟时间"""
    if config.strategy == RetryStrategy.IMMEDIATE:
        delay = 0
    elif config.strategy == RetryStrategy.FIXED_DELAY:
        delay = config.base_delay
    elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        delay = min(
            config.base_delay * (config.exponential_base ** attempt),
            config.max_delay
        )
    elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
        delay = min(config.base_delay * (attempt + 1), config.max_delay)
    else:
        delay = config.base_delay
    
    # 添加随机抖动
    if config.jitter and delay > 0:
        delay = delay * (0.5 + random.random() * 0.5)
    
    return delay


class ConnectionHealth:
    """连接健康状态"""
    def __init__(self):
        self.is_healthy: bool = True
        self.last_error: Optional[Exception] = None
        self.error_count: int = 0
        self.last_check: float = time.time()
        
    def mark_error(self, error: Exception) -> None:
        """标记错误"""
        self.is_healthy = False
        self.last_error = error
        self.error_count += 1
        self.last_check = time.time()
        
    def mark_healthy(self) -> None:
        """标记健康"""
        self.is_healthy = True
        self.last_error = None
        self.error_count = 0
        self.last_check = time.time()
        
    def should_reconnect(self) -> bool:
        """是否应该重连"""
        return not self.is_healthy or self.error_count >= 3


class AUFEConnection:
    """基于Web的VPN身份验证和会话管理，集成大学登录功能的AUFE连接类"""

    userid: str
    password: str

    def __init__(
        self, 
        server: str, 
        student_id: Optional[str] = None,
        timeout: float = AUFEConfig.DEFAULT_TIMEOUT,
        retry_config: Optional[RetryConfig] = None
    ) -> None:
        """
        初始化AUFE连接

        Args:
            server: 服务器主机名（不包含https://）
            student_id: 用于上下文存储的学生ID
            timeout: 请求超时时间
            retry_config: 重试配置
        """
        self.server_url: str = "https://" + server
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        
        # 会话和认证相关
        self.session: httpx.AsyncClient = self._create_session()
        self.twf_id: Optional[str] = None
        self._logged_in: bool = False
        self.student_id: Optional[str] = student_id
        
        # 连接状态管理
        self.last_activity: float = time.time()
        self._auto_close_task: Optional[asyncio.Task[None]] = None
        self._is_closed: bool = False
        self._health = ConnectionHealth()
        
        # 缓存
        self._request_cache: Dict[str, tuple] = {}  # url -> (response, timestamp)
        self._cache_ttl: float = 300  # 5分钟缓存
        
        # 大学登录相关属性
        self.uaap_base_url = AUFEConfig.UAAP_BASE_URL
        self.uaap_login_url = AUFEConfig.UAAP_LOGIN_URL
        self.uaap_cookies: Optional[Dict[str, str]] = None
        self._uaap_logged_in: bool = False

        # 设置上下文变量
        if student_id:
            student_id_var.set(student_id)
            _aufe_connections[student_id] = self

        # 启动自动关闭监控
        self._start_auto_close_monitor()
        
    def _create_session(self) -> httpx.AsyncClient:
        """创建HTTP会话"""
        return httpx.AsyncClient(
            verify=False,
            timeout=self.timeout,
            headers=AUFEConfig.DEFAULT_HEADERS.copy()
        )

    def _update_activity(self) -> None:
        """更新最后活动时间戳"""
        self.last_activity = time.time()

    def _start_auto_close_monitor(self) -> None:
        """启动自动关闭监控任务"""
        if not self._auto_close_task:
            self._auto_close_task = asyncio.create_task(self._monitor_auto_close())

    async def _monitor_auto_close(self) -> None:
        """监控自动关闭和健康检查"""
        try:
            while not self._is_closed:
                await asyncio.sleep(AUFEConfig.MONITOR_INTERVAL)
                
                # 检查不活动超时
                if time.time() - self.last_activity > AUFEConfig.ACTIVITY_TIMEOUT:
                    logger.info(f"由于不活动，自动关闭学生 {self.student_id} 的VPN连接")
                    await self.close()
                    break
                    
                # 健康检查
                await self._health_check()
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"自动关闭监控中出现错误: {str(e)}")
            
    async def _health_check(self) -> None:
        """连接健康检查"""
        try:
            if self._logged_in:
                # 简单的健康检查 - 发送一个轻量级请求
                test_url = f"{self.server_url}/por/index.csp"
                response = await self.session.get(test_url, timeout=5)
                if response.status_code == 200:
                    self._health.mark_healthy()
                else:
                    self._health.mark_error(AUFEConnectionError(f"健康检查失败: {response.status_code}"))
        except Exception as e:
            self._health.mark_error(e)
            
    def _clear_cache(self) -> None:
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            url for url, (_, timestamp) in self._request_cache.items()
            if current_time - timestamp > self._cache_ttl
        ]
        for key in expired_keys:
            del self._request_cache[key]
            
    def _get_cached_response(self, url: str) -> Optional[Any]:
        """获取缓存的响应"""
        if url in self._request_cache:
            response, timestamp = self._request_cache[url]
            if time.time() - timestamp < self._cache_ttl:
                return response
            else:
                del self._request_cache[url]
        return None
        
    def _cache_response(self, url: str, response: Any) -> None:
        """缓存响应"""
        self._request_cache[url] = (response, time.time())
        # 定期清理缓存
        if len(self._request_cache) % 10 == 0:
            self._clear_cache()

    @activity_tracker
    @retry_async()
    async def login(self, username: str, password: str) -> bool:
        """
        使用用户名和密码登录VPN服务器

        Args:
            username: 登录用户名
            password: 登录密码

        Returns:
            bool: 登录成功返回True，否则返回False
            
        Raises:
            AUFELoginError: 登录失败
            AUFEConnectionError: 连接失败
        """
        try:
            # 初始请求获取认证参数
            addr = f"{self.server_url}/por/login_auth.csp?apiversion=1"
            logger.info(f"登录请求: {addr}")

            resp = await self.session.get(addr)
            content = resp.text

            # 从响应中提取参数
            if twfid_g := re.search(r"<TwfID>(.*)</TwfID>", content):
                self.twf_id = twfid_g.group(1)
            else:
                logger.error("错误: 响应中未找到TwfID。")
                return False
            logger.info(f"Twf Id: {self.twf_id}")

            if rsa_key_g := re.search(
                r"<RSA_ENCRYPT_KEY>(.*)</RSA_ENCRYPT_KEY>", content
            ):
                rsa_key = rsa_key_g.group(1)
            else:
                logger.error("错误: 响应中未找到RSA_ENCRYPT_KEY。")
                return False
            logger.info(f"RSA密钥: {rsa_key}")

            rsa_exp_match = re.search(
                r"<RSA_ENCRYPT_EXP>(.*)</RSA_ENCRYPT_EXP>", content
            )
            if rsa_exp_match:
                rsa_exp = rsa_exp_match.group(1)
            else:
                logger.warning("警告: 未找到RSA_ENCRYPT_EXP，使用默认值。")
                rsa_exp = "65537"
            logger.info(f"RSA指数: {rsa_exp}")

            csrf_match = re.search(r"<CSRF_RAND_CODE>(.*)</CSRF_RAND_CODE>", content)
            csrf_code = ""
            if csrf_match:
                csrf_code = csrf_match.group(1)
                logger.info(f"CSRF代码: {csrf_code}")
                password_to_encrypt = password + "_" + csrf_code
            else:
                password_to_encrypt = password
                logger.warning(
                    "警告: 未匹配到CSRF代码。可能您连接的是较旧的服务器？继续执行..."
                )
            logger.info(f"待加密密码: {password_to_encrypt}")

            # 创建RSA密钥并加密密码
            rsa_exp_int = int(rsa_exp)
            rsa_modulus = int(rsa_key, 16)

            public_numbers = rsa.RSAPublicNumbers(e=rsa_exp_int, n=rsa_modulus)
            public_key = public_numbers.public_key(default_backend())

            encrypted_password = public_key.encrypt(
                password_to_encrypt.encode("utf-8"), padding.PKCS1v15()
            )
            encrypted_password_hex = binascii.hexlify(encrypted_password).decode(
                "ascii"
            )
            logger.info(f"加密后密码: {encrypted_password_hex}")

            # 提交登录凭据
            addr = (
                f"{self.server_url}/por/login_psw.csp?anti_replay=1&encrypt=1&type=cs"
            )
            logger.info(f"登录请求: {addr}")

            form_data = {
                "svpn_rand_code": "",
                "mitm": "",
                "svpn_req_randcode": csrf_code,
                "svpn_name": username,
                "svpn_password": encrypted_password_hex,
            }

            cookies = {"TWFID": self.twf_id or ""}
            resp = await self.session.post(addr, data=form_data, cookies=cookies)
            content = resp.text

            # 检查登录结果
            if "<Result>1</Result>" in content:
                logger.info("登录成功")
                self._logged_in = True
                return True
            else:
                logger.error(f"登录失败: {content}")
                self._logged_in = False
                return False

        except httpx.RequestError as e:
            logger.error(f"登录连接错误: {str(e)}")
            self._logged_in = False
            self._health.mark_error(e)
            raise AUFEConnectionError(f"登录连接失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"登录错误: {str(e)}")
            self._logged_in = False
            self._health.mark_error(e)
            raise AUFELoginError(f"登录失败: {str(e)}") from e

    @activity_tracker
    def login_status(self) -> bool:
        """
        检查用户当前是否已登录

        Returns:
            bool: 已登录返回True，否则返回False
        """
        return self._logged_in and self._health.is_healthy

    @activity_tracker
    def get_twfid(self) -> Optional[str]:
        """
        从当前会话获取TWFID令牌

        Returns:
            str: TWFID令牌，如果未登录则返回None
        """
        return self.twf_id

    @activity_tracker
    def requester(self) -> httpx.AsyncClient:
        """
        获取httpx会话客户端

        Returns:
            httpx.AsyncClient: 当前会话客户端
        """
        if self.twf_id:
            self.session.cookies.set("TWFID", self.twf_id)
        return self.session

    def _encrypt_password(self, password: str, key: str) -> str:
        """
        使用DES ECB模式和PKCS7填充加密密码
        复制JavaScript中CryptoJS.DES.encrypt的功能

        Args:
            password: 要加密的密码
            key: 加密密钥

        Returns:
            str: Base64编码的加密字符串
        """
        # 处理密钥 - CryptoJS使用的是8字节密钥
        key_bytes = key.encode("utf-8")[:8]
        # 如果密钥不足8字节，则用0填充
        if len(key_bytes) < 8:
            key_bytes = key_bytes + b"\0" * (8 - len(key_bytes))

        # 处理明文数据 - 确保是字节类型
        password_bytes = password.encode("utf-8")

        # 使用PKCS7填充
        padder = symmetric_padding.PKCS7(64).padder()
        padded_data = padder.update(password_bytes) + padder.finalize()

        # 创建DES加密器 - ECB模式
        cipher = Cipher(
            algorithms.TripleDES(key_bytes), modes.ECB(), backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # 加密数据
        encrypted = encryptor.update(padded_data) + encryptor.finalize()

        # 返回Base64编码的字符串
        return b64encode(encrypted).decode("utf-8")

    @activity_tracker
    @retry_async()
    async def uaap_login(self, username: str, password: str) -> bool:
        """
        执行大学UAAP系统登录过程

        Args:
            username: 用户名
            password: 密码

        Returns:
            bool: 登录成功返回True，否则返回False
            
        Raises:
            AUFELoginError: UAAP登录失败
            AUFEConnectionError: 连接失败
        """

        headers = AUFEConfig.DEFAULT_HEADERS.copy()

        try:
            # 步骤1: 获取登录页面以检索必要的令牌
            logger.info("访问UAAP登录页面...")
            response = await self.session.get(self.uaap_login_url, headers=headers)

            if response.status_code != 200:
                logger.error(f"访问UAAP登录页面失败。状态码: {response.status_code}")
                return False

            # 解析HTML响应
            soup = BeautifulSoup(response.text, "html.parser")

            # 提取LT令牌
            lt_input = soup.find("input", {"name": "lt"})
            if not lt_input:
                logger.error("在页面上找不到LT令牌")
                return False

            lt_value = lt_input.get("value")  # type: ignore
            logger.info(f"找到LT令牌: {lt_value}")

            # 提取execution令牌
            execution_input = soup.find("input", {"name": "execution"})
            if not execution_input:
                logger.error("在页面上找不到execution令牌")
                return False

            execution_value = execution_input.get("value")  # type: ignore
            logger.info(f"找到execution令牌: {execution_value}")

            # 步骤2: 加密密码
            encrypted_password = self._encrypt_password(password, lt_value)  # type: ignore
            logger.info("密码加密成功")

            # 步骤3: 准备登录数据
            login_data = {
                "username": username,
                "password": encrypted_password,
                "lt": lt_value,
                "execution": execution_value,
                "_eventId": "submit",
                "isQrSubmit": "false",
                "qrValue": "",
                "isMobileLogin": "false",
            }

            # 步骤4: 提交登录表单
            logger.info("提交UAAP登录数据...")
            login_headers = headers.copy()
            login_headers.update(
                {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "http://uaap.aufe.edu.cn",
                    "Referer": self.uaap_login_url,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Encoding": "gzip, deflate",
                    "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en-US;q=0.7,en;q=0.6",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Upgrade-Insecure-Requests": "1",
                }
            )

            login_response = await self.session.post(
                self.uaap_login_url, data=login_data, headers=login_headers
            )

            logger.info(f"UAAP响应状态: {login_response.status_code}")

            # 步骤5: 检查登录是否成功
            if login_response.status_code == 302:
                redirect_location = login_response.headers.get("Location", "")
                if redirect_location:
                    logger.info(f"UAAP重定向到: {redirect_location}")
                    self.uaap_cookies = dict(login_response.cookies)
                    self._uaap_logged_in = True
                    logger.info("UAAP登录成功!")
                    return True
                else:
                    logger.error("UAAP登录失败: 未找到重定向位置")
                    return False
            else:
                error_soup = BeautifulSoup(login_response.text, "html.parser")
                error_msg = error_soup.find("div", {"id": "tipMsg"})
                if error_msg and error_msg.text.strip():
                    logger.error(f"UAAP登录失败: {error_msg.text.strip()}")
                else:
                    logger.error("UAAP登录失败: 未知错误")
                return False

        except httpx.RequestError as e:
            logger.error(f"UAAP连接错误: {str(e)}")
            self._health.mark_error(e)
            raise AUFEConnectionError(f"UAAP连接失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"UAAP登录错误: {str(e)}")
            self._health.mark_error(e)
            raise AUFELoginError(f"UAAP登录失败: {str(e)}") from e

    @activity_tracker
    def uaap_login_status(self) -> bool:
        """
        检查UAAP系统登录状态

        Returns:
            bool: 已登录返回True，否则返回False
        """
        return self._uaap_logged_in and self._health.is_healthy

    @activity_tracker
    def get_uaap_cookies(self) -> Optional[Dict[str, str]]:
        """
        获取UAAP登录后的cookies

        Returns:
            Dict[str, str]: UAAP cookies，如果未登录则返回None
        """
        return self.uaap_cookies

    async def get_protected_page(
        self, url: str, use_uaap_cookies: bool = True
    ) -> Optional[str]:
        """
        访问受保护的页面

        Args:
            url: 要访问的URL
            use_uaap_cookies: 是否使用UAAP cookies

        Returns:
            str: 页面内容，失败返回None
        """
        self._update_activity()

        headers = AUFEConfig.DEFAULT_HEADERS.copy()

        cookies = self.uaap_cookies if use_uaap_cookies else None

        logger.info(f"访问受保护的页面: {url}")
        response = await self.session.get(url, headers=headers, cookies=cookies)

        if response.status_code == 200:
            logger.info("成功访问受保护的页面")
            return response.text
        else:
            logger.error(f"访问页面失败。状态码: {response.status_code}")
            return None

    @activity_tracker
    @retry_async()
    async def redirect_to(
        self, redirect_url: str, cookies: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        手动处理重定向并返回结果

        Args:
            redirect_url: 重定向URL
            cookies: 要使用的cookies

        Returns:
            Dict包含response和cookies，失败返回None
            
        Raises:
            AUFEConnectionError: 连接失败
        """
        logger.info(f"跟踪重定向到: {redirect_url}")

        headers = AUFEConfig.DEFAULT_HEADERS.copy()

        try:
            response = await self.session.get(
                redirect_url,
                headers=headers,
                cookies=cookies,
                follow_redirects=False,
            )

            logger.info(f"重定向响应状态: {response.status_code}")

            # 如果是重定向，继续跟踪
            if response.status_code in (301, 302, 303, 307, 308):
                next_location = response.headers.get("Location")
                if next_location:
                    # 合并新cookie并递归跟踪下一个重定向
                    all_cookies = dict(cookies or {})
                    all_cookies.update(dict(response.cookies))
                    return await self.redirect_to(next_location, all_cookies)

            # 返回最终响应及其cookie
            return {
                "response": response,
                "cookies": (
                    response.cookies
                    if cookies is None
                    else {**cookies, **dict(response.cookies)}
                ),
            }

        except Exception as e:
            logger.error(f"跟踪重定向时出错: {str(e)}")
            return None

    async def close(self) -> None:
        """关闭httpx会话并清理资源"""
        if self._is_closed:
            return

        self._is_closed = True

        # 取消自动关闭任务
        if self._auto_close_task and not self._auto_close_task.done():
            self._auto_close_task.cancel()
            try:
                await self._auto_close_task
            except asyncio.CancelledError:
                pass

        # 从连接池中移除
        if self.student_id and self.student_id in _aufe_connections:
            del _aufe_connections[self.student_id]

        # 关闭会话
        await self.session.aclose()
        logger.info(f"学生 {self.student_id} 的AUFE连接已关闭")

    @activity_tracker
    async def model_request(
        self, 
        model: T_BaseModel, 
        url: str, 
        method: str = "GET", 
        use_cache: bool = True,
        force_reconnect: bool = False,
        **kwargs
    ) -> Optional[T_BaseModel]:
        """
        使用指定的模型发送请求并返回解析后的模型实例，包含重试机制

        Args:
            model: 要使用的Pydantic模型类
            url: 请求的URL
            method: HTTP方法（默认为GET）
            use_cache: 是否使用缓存
            force_reconnect: 是否强制重连
            **kwargs: 其他请求参数

        Returns:
            T_BaseModel: 解析后的模型实例，如果请求失败则返回None
            
        Raises:
            AUFEConnectionError: 连接失败
            AUFEParseError: 数据解析失败
        """
        # 检查缓存
        cache_key = f"{method}:{url}:{hash(str(kwargs))}"
        if use_cache:
            cached_result = self._get_cached_response(cache_key)
            if cached_result is not None:
                logger.debug(f"使用缓存的模型响应: {url}")
                return cached_result
        
        # 如果需要或者连接不健康，先重连
        if force_reconnect or self._health.should_reconnect():
            await self._reconnect()
        
        # 使用重试机制发送请求
        try:
            result = await self._send_model_request_with_retry(model, url, method, **kwargs)
            # 缓存成功的结果
            if result is not None and use_cache:
                self._cache_response(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"模型请求失败: {url}, 错误: {str(e)}")
            return None
            
    async def _send_model_request_with_retry(
        self, model: T_BaseModel, url: str, method: str, **kwargs
    ) -> Optional[T_BaseModel]:
        """带重试的模型请求发送"""
        config = self.retry_config
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                logger.debug(f"发送模型请求，第 {attempt + 1} 次尝试: {url}")
                
                # 发送HTTP请求
                response = await self._send_http_request(method, url, **kwargs)
                
                if response.status_code == 200:
                    try:
                        # 解析JSON数据
                        json_data = response.json()
                        # 解析为Pydantic模型
                        parsed_model = model.parse_obj(json_data)
                        logger.info(f"模型请求成功: {url}")
                        self._health.mark_healthy()
                        return parsed_model
                    except Exception as parse_error:
                        error = AUFEParseError(f"数据解析失败: {str(parse_error)}")
                        self._health.mark_error(error)
                        last_exception = error
                        
                        if attempt == config.max_attempts - 1:
                            break
                        logger.warning(f"第 {attempt + 1} 次请求数据解析失败: {str(parse_error)}")
                        await asyncio.sleep(_calculate_delay(attempt, config))
                        continue
                else:
                    error = AUFEConnectionError(f"HTTP错误: {response.status_code}")
                    self._health.mark_error(error)
                    last_exception = error
                    
                    if attempt == config.max_attempts - 1:
                        break
                    logger.warning(f"第 {attempt + 1} 次请求HTTP失败: {response.status_code}")
                    await asyncio.sleep(_calculate_delay(attempt, config))
                    continue
                    
            except httpx.RequestError as e:
                error = AUFEConnectionError(f"请求失败: {str(e)}")
                self._health.mark_error(error)
                last_exception = error
                
                if attempt == config.max_attempts - 1:
                    break
                logger.warning(f"第 {attempt + 1} 次请求异常: {str(e)}")
                await asyncio.sleep(_calculate_delay(attempt, config))
                continue
            except Exception as e:
                # 非可重试异常
                logger.error(f"不可重试的异常: {str(e)}")
                raise e
                
        # 所有重试都失败，尝试重连后再试
        if self._health.should_reconnect():
            logger.info("重连后再次尝试")
            await self._reconnect()
            return await self._send_model_request_final_attempt(model, url, method, **kwargs)
            
        if last_exception:
            raise last_exception
        return None
        
    async def _send_model_request_final_attempt(
        self, model: T_BaseModel, url: str, method: str, **kwargs
    ) -> Optional[T_BaseModel]:
        """重连后的最后尝试"""
        try:
            logger.info(f"重连后最后尝试: {url}")
            response = await self._send_http_request(method, url, **kwargs)
            
            if response.status_code == 200:
                json_data = response.json()
                parsed_model = model.parse_obj(json_data)
                logger.info(f"重连后模型请求成功: {url}")
                self._health.mark_healthy()
                return parsed_model
            else:
                error = AUFEConnectionError(f"重连后HTTP错误: {response.status_code}")
                self._health.mark_error(error)
                raise error
                
        except Exception as e:
            error = AUFEConnectionError(f"重连后请求失败: {str(e)}")
            self._health.mark_error(error)
            raise error from e
            
    async def _send_http_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """发送HTTP请求"""
        requester = self.requester()
        
        if method.upper() == "GET":
            return await requester.get(url, **kwargs)
        elif method.upper() == "POST":
            return await requester.post(url, **kwargs)
        elif method.upper() == "PUT":
            return await requester.put(url, **kwargs)
        elif method.upper() == "DELETE":
            return await requester.delete(url, **kwargs)
        else:
            return await requester.request(method, url, **kwargs)
            
    async def _reconnect(self) -> None:
        """重新连接"""
        logger.info("开始重建连接")
        try:
            # 关闭当前会话
            await self.session.aclose()
            
            # 创建新的会话
            self.session = self._create_session()
            
            # 重置状态
            self._logged_in = False
            self._uaap_logged_in = False
            self.twf_id = None
            self.uaap_cookies = None
            
            # 重置健康状态
            self._health.mark_healthy()
            
            logger.info("连接重建完成")
            
        except Exception as e:
            logger.error(f"重建连接失败: {str(e)}")
            raise AUFEConnectionError(f"重建连接失败: {str(e)}") from e

    @activity_tracker
    def store_context(self, key: str, value: Any) -> None:
        """
        在当前上下文中存储数据

        Args:
            key: 上下文键
            value: 要存储的值
        """
        context = vpn_context_var.get({})
        context[key] = value
        vpn_context_var.set(context)

    @activity_tracker
    def get_context(self, key: str, default: Any = None) -> Any:
        """
        从当前上下文获取数据

        Args:
            key: 上下文键
            default: 如果键不存在时的默认值

        Returns:
            从上下文获取的值或默认值
        """
        context = vpn_context_var.get({})
        return context.get(key, default)

    def clear_context(self) -> None:
        """清除所有上下文数据"""
        vpn_context_var.set({})

    @property
    def context_student_id(self) -> Optional[str]:
        """
        从上下文获取学生ID

        Returns:
            从上下文获取的学生ID或None
        """
        return student_id_var.get()

    async def __aenter__(self) -> "AUFEConnection":
        """异步上下文管理器入口"""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[object],
    ) -> None:
        """异步上下文管理器出口"""
        await self.close()

    def is_active(self) -> bool:
        """
        检查连接是否仍然活跃（未关闭且最近使用过）

        Returns:
            bool: 连接活跃返回True，否则返回False
        """
        return (
            not self._is_closed 
            and (time.time() - self.last_activity < AUFEConfig.ACTIVITY_TIMEOUT)
            and self._health.is_healthy
        )

    @classmethod
    def get_connection_by_student_id(
        cls, student_id: str
    ) -> Optional["AUFEConnection"]:
        """
        通过学生ID获取AUFE连接

        Args:
            student_id: 学生ID

        Returns:
            AUFEConnection实例，如果未找到则返回None
        """
        return _aufe_connections.get(student_id)

    @classmethod
    def create_or_get_connection(
        cls, 
        server: str, 
        student_id: str,
        timeout: float = AUFEConfig.DEFAULT_TIMEOUT,
        retry_config: Optional[RetryConfig] = None
    ) -> "AUFEConnection":
        """
        为学生ID创建新的AUFE连接或获取现有连接

        Args:
            server: 服务器主机名
            student_id: 学生ID
            timeout: 请求超时时间
            retry_config: 重试配置

        Returns:
            AUFEConnection实例
        """
        existing_conn = cls.get_connection_by_student_id(student_id)
        if existing_conn and existing_conn.is_active():
            existing_conn._update_activity()
            logger.debug(f"重用现有连接: {student_id}")
            return existing_conn

        # 关闭现有的非活跃连接
        if existing_conn:
            logger.info(f"关闭非活跃连接: {student_id}")
            asyncio.create_task(existing_conn.close())

        # 创建新连接
        logger.info(f"创建新连接: {student_id}")
        return cls(server, student_id, timeout, retry_config)

    @classmethod
    def get_all_active_connections(cls) -> Dict[str, "AUFEConnection"]:
        """
        获取所有活跃的AUFE连接

        Returns:
            活跃连接的学生ID -> AUFEConnection字典
        """
        active_connections = {}
        for student_id, conn in _aufe_connections.items():
            if conn.is_active():
                active_connections[student_id] = conn
        return active_connections

    @classmethod
    async def cleanup_inactive_connections(cls) -> int:
        """
        清理所有非活跃连接
        
        Returns:
            int: 已清理的连接数量
        """
        inactive_connections = []
        for student_id, conn in list(_aufe_connections.items()):
            if not conn.is_active():
                inactive_connections.append((student_id, conn))

        cleaned_count = 0
        for student_id, conn in inactive_connections:
            try:
                await conn.close()
                cleaned_count += 1
                logger.debug(f"清理非活跃连接: {student_id}")
            except Exception as e:
                logger.error(f"清理连接时出错 {student_id}: {str(e)}")
        
        if cleaned_count > 0:
            logger.info(f"已清理 {cleaned_count} 个非活跃连接")
        
        return cleaned_count
        
    @classmethod
    def get_connection_stats(cls) -> Dict[str, Any]:
        """
        获取连接池统计信息
        
        Returns:
            Dict: 连接统计信息
        """
        total_connections = len(_aufe_connections)
        active_connections = len(cls.get_all_active_connections())
        inactive_connections = total_connections - active_connections
        
        # 计算健康连接数
        healthy_connections = sum(
            1 for conn in _aufe_connections.values() 
            if conn._health.is_healthy
        )
        
        return {
            "total_connections": total_connections,
            "active_connections": active_connections,
            "inactive_connections": inactive_connections,
            "healthy_connections": healthy_connections,
            "unhealthy_connections": total_connections - healthy_connections
        }
