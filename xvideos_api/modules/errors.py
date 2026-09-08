from base_api.modules.errors import (
    ScraperException,
    NotFound,
    NetworkError,
    BotDetection,
    ProxyError,
    UnknownNetworkError,
    DownloadFailed,
)


class NoLoginCookies(ScraperException):
    def __init__(self, msg):
        super().__init__(msg)
        self.msg = msg


__all__ = [
    "NoLoginCookies",
    "NotFound",
    "NetworkError",
    "BotDetection",
    "ProxyError",
    "UnknownNetworkError",
    "DownloadFailed",
]
