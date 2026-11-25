"""Serve the installed shacl-py viewer for one native window selection."""

import asyncio
import json
import os
import secrets
import socket
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path


async def serve_project(root, protocol):
    import streamlit as st
    import uvicorn
    from shacl_py.branding import branding
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware

    theme = branding(root)
    token = secrets.token_hex(24)
    with socket.create_server(("127.0.0.1", 0)) as listener:
        host, port = listener.getsockname()
        for key, value in {
            # A frozen installation has no site-packages directory. Force bundled assets.
            "global.developmentMode": False,
            "server.address": host,
            "server.port": port,
            "server.baseUrlPath": token,
            "server.headless": True,
            "server.fileWatcherType": "none",
            "server.enableStaticServing": False,
            "server.enableAgentApi": False,
            "browser.gatherUsageStats": False,
            "client.toolbarMode": "minimal",
            "theme.base": "light",
            "theme.primaryColor": "#000000",
        }.items():
            st.config.set_option(key, value)

        @asynccontextmanager
        async def lifespan(app):
            print(
                json.dumps(
                    {
                        "url": f"http://{host}:{port}/{token}/",
                        "name": root.name,
                        "title": theme["page_title"],
                    }
                ),
                file=protocol,
                flush=True,
            )
            yield

        async def local_styles(request, call_next):
            response = await call_next(request)
            if response.headers.get("content-type", "").startswith("text/html"):
                # The desktop distribution supplies the catalogue's fonts offline.
                response.headers["Content-Security-Policy"] = (
                    "style-src 'self' 'unsafe-inline'; font-src 'self' data:"
                )
            return response

        app = st.App(
            Path(__file__).with_name("desktop_app.py"),
            lifespan=lifespan,
            middleware=[Middleware(BaseHTTPMiddleware, dispatch=local_styles)],
        )
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=host,
                port=port,
                access_log=False,
                log_level="warning",
                timeout_graceful_shutdown=2,
            )
        )
        loop = asyncio.get_running_loop()

        def watch_parent():
            # EOF also closes the viewer after a desktop crash.
            sys.stdin.buffer.read(1)
            loop.call_soon_threadsafe(setattr, server, "should_exit", True)

        threading.Thread(target=watch_parent, daemon=True).start()
        await server.serve(sockets=[listener])


def run(path):
    protocol, sys.stdout = sys.stdout, sys.stderr
    try:
        root = Path(path).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Choose a project folder.")
        os.environ["SHACL_PY_ROOT"] = str(root)
        os.environ["SHACL_PY_METALAD"] = "0"
        os.chdir(Path(__file__).resolve().parent)
        asyncio.run(serve_project(root, protocol))
    except Exception as error:
        print(json.dumps({"error": str(error)}), file=protocol, flush=True)
        raise
