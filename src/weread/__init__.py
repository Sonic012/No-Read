"""
微信读书模块

数据源统一走官方 Agent API Gateway，见 ``gateway.py`` 与 ``provider.py``。
"""

from .gateway import WeReadAuthError, WeReadError, WeReadGateway, WeReadUpgradeRequired
from .provider import BookBundle, OfficialWeReadProvider, WeReadProvider

__all__ = [
    "WeReadGateway",
    "WeReadError",
    "WeReadAuthError",
    "WeReadUpgradeRequired",
    "WeReadProvider",
    "OfficialWeReadProvider",
    "BookBundle",
]
