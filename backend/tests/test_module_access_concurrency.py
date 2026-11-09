import asyncio
import threading
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.middleware.business_os import BusinessOSModuleAccessMiddleware


def test_module_pool_wait_does_not_block_event_loop():
    async def scenario():
        entered = threading.Event()
        release = threading.Event()
        middleware = BusinessOSModuleAccessMiddleware(lambda scope, receive, send: None)
        def blocked_check(request, module):
            entered.set()
            assert release.wait(3), 'The event loop did not release the simulated pool wait'
            return JSONResponse({'detail': 'disabled'}, status_code=403)
        middleware._check_access = blocked_check
        request = Request({'type': 'http', 'method': 'GET', 'path': '/api/v1/project-management/notes', 'headers': []})
        async def next_handler(request):
            raise AssertionError('A denied module must not reach its handler')
        async def release_from_event_loop():
            while not entered.is_set():
                await asyncio.sleep(0.01)
            release.set()
        task = asyncio.create_task(release_from_event_loop())
        try:
            response = await middleware.dispatch(request, next_handler)
            assert response.status_code == 403
            await task
        finally:
            release.set()
            task.cancel()
    asyncio.run(scenario())
