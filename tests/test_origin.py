import unittest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from fixtures.comfy_origin import create_origin_only_middleware


class OriginTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_pinned_middleware(self):
        app = web.Application(middlewares=[create_origin_only_middleware()])

        async def handler(request):
            return web.Response(text="ok")

        app.router.add_route("*", "/{tail:.*}", handler)
        async with TestClient(TestServer(app)) as client:
            for method, path, headers, status in [
                ("GET", "/", {}, 200),
                ("GET", "/", {"Sec-Fetch-Site": "none"}, 200),
                (
                    "GET",
                    "/",
                    {
                        "Sec-Fetch-Site": "cross-site",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Dest": "document",
                    },
                    403,
                ),
                ("POST", "/prompt", {"Sec-Fetch-Site": "cross-site"}, 403),
                ("GET", "/system_stats", {"Sec-Fetch-Site": "cross-site"}, 403),
                ("POST", "/prompt", {"Origin": "https://evil.example"}, 403),
            ]:
                r = await client.request(method, path, headers=headers)
                self.assertEqual(r.status, status)
