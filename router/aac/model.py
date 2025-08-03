from router.common_model import BaseResponse
from provider.aufe.aac.model import LoveACScoreInfo, LoveACScoreCategory
from typing import List


# 统一响应模型
class ScoreInfoResponse(BaseResponse[LoveACScoreInfo]):
    """爱安财总分信息响应"""

    pass


class ScoreListResponse(BaseResponse[List[LoveACScoreCategory]]):
    """爱安财分数明细列表响应"""

    pass
