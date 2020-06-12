import asyncio
import threading
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Mapping, Union

import pytest
from hypercorn.typing import ASGIFramework
from nebula_sdk.util import SoftTerminationPolicy
from nebula_sdk.webhook import WebhookServer
from quart import Quart
from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

if TYPE_CHECKING:
    from wsgiref.types import StartResponse, WSGIApplication


retry_strategy = Retry(
    total=4,
    backoff_factor=1,
)

session = Session()
session.mount('http://', HTTPAdapter(max_retries=retry_strategy))


class TestWebhookServer:

    async def _test_app(self, event_loop: asyncio.AbstractEventLoop,
                        app: Union[ASGIFramework, 'WSGIApplication']) -> None:
        # Create the server.
        term = SoftTerminationPolicy()

        srv = WebhookServer(app, termination_policy=term, port=0)
        srv_task = event_loop.create_task(srv.serve())

        # Issue request to server and check response.
        resp = await event_loop.run_in_executor(
            None, session.get,
            f'http://localhost:{srv.port}',
        )
        resp.raise_for_status()

        assert resp.json() == {'success': True}

        # Stop the server.
        await term.terminate_task(srv_task)

        # Wait for everything to clean up and exit.
        await asyncio.wait_for(asyncio.gather(*filter(
            lambda t: t != asyncio.current_task(),
            asyncio.all_tasks(),
        ), return_exceptions=True), 30)

    @pytest.mark.asyncio
    async def test_asgi_2(self, event_loop: asyncio.AbstractEventLoop) -> None:
        class Application:

            def __init__(self, scope: Dict[Any, Any]) -> None:
                if scope['type'] != 'http':
                    raise NotImplementedError()

            async def __call__(self, receive: Callable[..., Any],
                               send: Callable[..., Any]) -> None:
                await send({
                    'type': 'http.response.start',
                    'status': 200,
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'{"success": true}'
                })

        await self._test_app(event_loop, Application)

    @pytest.mark.asyncio
    async def test_asgi_3(self, event_loop: asyncio.AbstractEventLoop) -> None:
        async def application(scope: Dict[Any, Any],
                              receive: Callable[..., Any],
                              send: Callable[..., Any]) -> None:
            if scope['type'] != 'http':
                raise NotImplementedError()

            await send({
                'type': 'http.response.start',
                'status': 200,
            })
            await send({
                'type': 'http.response.body',
                'body': b'{"success": true}'
            })

        await self._test_app(event_loop, application)

    @pytest.mark.asyncio
    async def test_wsgi(self, event_loop: asyncio.AbstractEventLoop) -> None:
        def application(environ: Mapping[str, Any],
                        start_response: 'StartResponse') -> Iterable[bytes]:
            start_response('200 OK', [])
            yield b'{"success": true}'

        await self._test_app(event_loop, application)

    @pytest.mark.asyncio
    async def test_quart(self, event_loop: asyncio.AbstractEventLoop) -> None:
        application = Quart(__name__)

        @application.route('/')
        async def hello() -> str:
            return '{"success": true}'

        await self._test_app(event_loop, application)

    def test_serve_forever(self) -> None:
        def application(environ: Mapping[str, Any],
                        start_response: 'StartResponse') -> Iterable[bytes]:
            raise NotImplementedError()

        term = SoftTerminationPolicy()

        srv = WebhookServer(application, termination_policy=term, port=0)
        t = threading.Thread(target=srv.serve_forever)
        t.daemon = True
        t.start()

        # Issue a request to the server; discard response.
        session.get(f'http://localhost:{srv.port}')

        # Request termination of server.
        term.terminate_all()

        t.join(timeout=30)
        assert not t.is_alive()
