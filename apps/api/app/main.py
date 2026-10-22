from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import core

app = FastAPI(title="Scholarly Pattern Explorer API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(core.router, prefix="/api/v1")


@app.middleware("http")
async def _timings(request, call_next):
    """Per-stage search timings (ml.timing) as a Server-Timing header, plus a log line."""
    import logging
    import time
    from ml.timing import collect, server_timing
    t0 = time.perf_counter()
    with collect() as t:
        response = await call_next(request)
    t["total"] = (time.perf_counter() - t0) * 1000
    response.headers["Server-Timing"] = server_timing(t)
    if request.url.path.endswith("/search"):
        logging.getLogger("spe.timing").info("search %s", server_timing(t))
    return response
