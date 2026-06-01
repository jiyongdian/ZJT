"""
封装的 httpx 异步 API 客户端，用于 E2E 测试中的 API 调用。
遵守非阻塞原则，使用 httpx.AsyncClient 而非 requests。
"""
import httpx


class APIClient:
    """异步 API 客户端封装"""

    def __init__(self, base_url: str, headers: dict = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self._client = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=httpx.Timeout(self.timeout),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def get(self, path: str, **kwargs) -> httpx.Response:
        return await self._client.get(path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        return await self._client.post(path, **kwargs)

    async def put(self, path: str, **kwargs) -> httpx.Response:
        return await self._client.put(path, **kwargs)

    async def delete(self, path: str, **kwargs) -> httpx.Response:
        return await self._client.delete(path, **kwargs)

    async def patch(self, path: str, **kwargs) -> httpx.Response:
        return await self._client.patch(path, **kwargs)
