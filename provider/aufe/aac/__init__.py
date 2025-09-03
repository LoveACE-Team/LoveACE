from typing import Optional
from urllib.parse import unquote
from loguru import logger
from provider.aufe.aac.model import (
    LoveACScoreInfo,
    LoveACScoreInfoResponse,
    LoveACScoreListResponse,
    ErrorLoveACScoreInfo,
    ErrorLoveACScoreListResponse,
    ErrorLoveACScoreCategory,
)
from provider.aufe.client import (
    AUFEConnection, 
    aufe_config_global, 
    activity_tracker, 
    retry_async,
    AUFEConnectionError,
    AUFEParseError,
    RetryConfig
)


class AACConfig:
    """AAC 模块配置常量"""
    BASE_URL = "http://api-dekt-ac-acxk-net.vpn2.aufe.edu.cn:8118"
    WEB_URL = "http://dekt-ac-acxk-net.vpn2.aufe.edu.cn:8118"
    LOGIN_SERVICE_URL = "http://uaap-aufe-edu-cn.vpn2.aufe.edu.cn:8118/cas/login?service=http%3a%2f%2fapi.dekt.ac.acxk.net%2fUser%2fIndex%2fCoreLoginCallback%3fisCASGateway%3dtrue"


@retry_async()
async def get_system_token(vpn_connection: AUFEConnection) -> Optional[str]:
    """
    获取系统令牌 (sys_token)

    Args:
        vpn_connection: VPN连接实例

    Returns:
        Optional[str]: 系统令牌，失败时返回None
        
    Raises:
        AUFEConnectionError: 连接失败
        AUFEParseError: 令牌解析失败
    """
    try:
        next_location = AACConfig.LOGIN_SERVICE_URL
        max_redirects = 10  # 防止无限重定向
        redirect_count = 0

        while redirect_count < max_redirects:
            response = await vpn_connection.requester().get(
                next_location, follow_redirects=False
            )

            # 如果是重定向，继续跟踪
            if response.status_code in (301, 302, 303, 307, 308):
                next_location = response.headers.get("Location")
                if not next_location:
                    raise AUFEParseError("重定向响应中缺少Location头")
                    
                logger.debug(f"重定向到: {next_location}")
                redirect_count += 1

                if "register?ticket=" in next_location:
                    logger.info(f"重定向到爱安财注册页面: {next_location}")
                    try:
                        sys_token = next_location.split("ticket=")[-1]
                        # URL编码转为正常字符串
                        sys_token = unquote(sys_token)
                        if sys_token:
                            logger.info(f"获取到系统令牌: {sys_token[:10]}...")
                            return sys_token
                        else:
                            raise AUFEParseError("提取的系统令牌为空")
                    except Exception as e:
                        raise AUFEParseError(f"解析系统令牌失败: {str(e)}") from e
            else:
                break

        if redirect_count >= max_redirects:
            raise AUFEConnectionError(f"重定向次数过多 ({max_redirects})")
            
        raise AUFEParseError("未能从重定向中获取到系统令牌")

    except (AUFEConnectionError, AUFEParseError):
        raise
    except Exception as e:
        logger.error(f"获取系统令牌异常: {str(e)}")
        raise AUFEConnectionError(f"获取系统令牌失败: {str(e)}") from e


class AACClient:
    """爱安财系统客户端"""

    def __init__(
        self,
        vpn_connection: AUFEConnection,
        ticket: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None
    ):
        """
        初始化爱安财系统客户端

        Args:
            vpn_connection: VPN连接实例
            ticket: 系统令牌
            retry_config: 重试配置
        """
        self.vpn_connection = vpn_connection
        self.base_url = AACConfig.BASE_URL.rstrip("/")
        self.web_url = AACConfig.WEB_URL.rstrip("/")
        self.twfid = vpn_connection.get_twfid()
        self.system_token: Optional[str] = ticket
        self.retry_config = retry_config or RetryConfig()
        
        logger.info(
            f"爱安财系统客户端初始化: base_url={self.base_url}, web_url={self.web_url}"
        )
        
    def _get_default_headers(self) -> dict:
        """获取默认请求头"""
        return {
            **aufe_config_global.DEFAULT_HEADERS,
            "ticket": self.system_token or "",
            "sdp-app-session": self.twfid or "",
        }

    @activity_tracker
    @retry_async()
    async def validate_connection(self) -> bool:
        """
        验证爱安财系统连接

        Returns:
            bool: 连接是否有效
            
        Raises:
            AUFEConnectionError: 连接失败
        """
        try:
            headers = aufe_config_global.DEFAULT_HEADERS.copy()
            
            response = await self.vpn_connection.requester().get(
                f"{self.web_url}/", headers=headers
            )
            is_valid = response.status_code == 200

            logger.info(
                f"爱安财系统连接验证结果: {'有效' if is_valid else '无效'} (HTTP状态码: {response.status_code})"
            )

            if not is_valid:
                raise AUFEConnectionError(f"爱安财系统连接验证失败，状态码: {response.status_code}")
                
            return is_valid
            
        except AUFEConnectionError:
            raise
        except Exception as e:
            logger.error(f"验证爱安财系统连接异常: {str(e)}")
            raise AUFEConnectionError(f"验证连接失败: {str(e)}") from e

    @activity_tracker
    async def fetch_score_info(self) -> LoveACScoreInfo:
        """
        获取爱安财总分信息，使用重试机制

        Returns:
            LoveACScoreInfo: 总分信息，失败时返回错误模型
        """
        try:
            logger.info("开始获取爱安财总分信息")

            headers = self._get_default_headers()

            # 使用新的重试机制
            score_response = await self.vpn_connection.model_request(
                model=LoveACScoreInfoResponse,
                url=f"{self.base_url}/User/Center/DoGetScoreInfo?sf_request_type=ajax",
                method="POST",
                headers=headers,
                data={},  # 空的POST请求体
                follow_redirects=True,
            )

            if score_response and score_response.code == 0 and score_response.data:
                logger.info(
                    f"爱安财总分信息获取成功: {score_response.data.total_score}分"
                )
                return score_response.data
            else:
                error_msg = score_response.msg if score_response else '未知错误'
                logger.error(f"获取爱安财总分信息失败: {error_msg}")
                # 返回错误模型
                return ErrorLoveACScoreInfo(
                    TotalScore=-1.0,
                    IsTypeAdopt=False,
                    TypeAdoptResult=f"请求失败: {error_msg}",
                )
        except (AUFEConnectionError, AUFEParseError) as e:
            logger.error(f"获取爱安财总分信息失败: {str(e)}")
            return ErrorLoveACScoreInfo(
                TotalScore=-1.0,
                IsTypeAdopt=False,
                TypeAdoptResult=f"请求失败: {str(e)}",
            )
        except Exception as e:
            logger.error(f"获取爱安财总分信息异常: {str(e)}")
            # 返回错误模型
            return ErrorLoveACScoreInfo(
                TotalScore=-1.0,
                IsTypeAdopt=False,
                TypeAdoptResult="系统错误，请稍后重试",
            )

    @activity_tracker
    async def fetch_score_list(
        self, page_index: int = 1, page_size: int = 10
    ) -> LoveACScoreListResponse:
        """
        获取爱安财分数列表，使用重试机制

        Args:
            page_index: 页码，默认为1
            page_size: 每页大小，默认为10

        Returns:
            LoveACScoreListResponse: 分数列表响应，失败时返回错误模型
        """
        def _create_error_response(error_msg: str) -> ErrorLoveACScoreListResponse:
            """创建错误响应模型"""
            return ErrorLoveACScoreListResponse(
                code=-1,
                msg=error_msg,
                data=[
                    ErrorLoveACScoreCategory(
                        ID="error",
                        ShowNum=-1,
                        TypeName="请求失败",
                        TotalScore=-1.0,
                        children=[],
                    )
                ],
            )
            
        try:
            logger.info(
                f"开始获取爱安财分数列表，页码: {page_index}, 每页大小: {page_size}"
            )

            headers = self._get_default_headers()
            data = {"pageIndex": str(page_index), "pageSize": str(page_size)}

            # 使用新的重试机制
            score_list_response = await self.vpn_connection.model_request(
                model=LoveACScoreListResponse,
                url=f"{self.base_url}/User/Center/DoGetScoreList?sf_request_type=ajax",
                method="POST",
                headers=headers,
                data=data,
                follow_redirects=True,
            )

            if (
                score_list_response
                and score_list_response.code == 0
                and score_list_response.data
            ):
                logger.info(
                    f"爱安财分数列表获取成功，分类数量: {len(score_list_response.data)}"
                )
                return score_list_response
            else:
                error_msg = score_list_response.msg if score_list_response else '未知错误'
                logger.error(f"获取爱安财分数列表失败: {error_msg}")
                return _create_error_response(f"请求失败: {error_msg}")
                
        except (AUFEConnectionError, AUFEParseError) as e:
            logger.error(f"获取爱安财分数列表失败: {str(e)}")
            return _create_error_response(f"请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"获取爱安财分数列表异常: {str(e)}")
            return _create_error_response("系统错误，已进行多次重试")

