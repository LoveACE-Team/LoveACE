from fastapi import Depends
from fastapi.routing import APIRouter
from provider.aufe.aac import AACClient
from provider.aufe.aac.depends import get_aac_client
from provider.loveac.authme import AuthmeResponse
from router.aac.model import ScoreInfoResponse, ScoreListResponse
from router.common_model import ErrorResponse


aac_router = APIRouter(prefix="/api/v1/aac")


@aac_router.post(
    "/fetch_score_info",
    summary="获取爱安财总分信息",
    response_model=ScoreInfoResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_score_info(client: AACClient = Depends(get_aac_client)):
    """获取爱安财系统的总分信息"""
    try:
        result = await client.fetch_score_info()

        # 检查是否是AuthmeResponse（认证错误）
        if isinstance(result, AuthmeResponse):
            return result

        # 使用新的错误检测机制
        response = ScoreInfoResponse.from_data(
            data=result,
            success_message="爱安财总分信息获取成功",
            error_message="获取爱安财总分信息失败，网络请求多次重试后仍无法连接服务器，请稍后重试或联系管理员",
        )
        return response

    except Exception as e:
        return ErrorResponse(
            message=f"获取爱安财总分信息时发生系统错误：{str(e)}", code=500
        )


@aac_router.post(
    "/fetch_score_list",
    summary="获取爱安财分数明细列表",
    response_model=ScoreListResponse | AuthmeResponse | ErrorResponse,
)
async def fetch_score_list(
    client: AACClient = Depends(get_aac_client),
):
    """获取爱安财系统的分数明细列表"""
    try:
        result = await client.fetch_score_list()

        # 检查是否是AuthmeResponse（认证错误）
        if isinstance(result, AuthmeResponse):
            return result

        # 检查分数列表数据
        if result and hasattr(result, "data") and result.data:
            # 使用新的错误检测机制检查列表数据
            response = ScoreListResponse.from_data(
                data=result.data,
                success_message="爱安财分数明细获取成功",
                error_message="获取爱安财分数明细失败，网络请求多次重试后仍无法连接服务器，请稍后重试或联系管理员",
            )
            return response
        else:
            # 没有数据的情况
            return ScoreListResponse.error(
                message="暂无爱安财分数数据，请确认您的账户状态或稍后再试",
                code=404,
                data=[],
            )

    except Exception as e:
        return ErrorResponse(
            message=f"获取爱安财分数明细时发生系统错误：{str(e)}", code=500
        )
