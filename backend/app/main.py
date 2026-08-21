from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import analytics, chat, embedding_model, embeddings, health, models, settings as settings_router
from app.routers import metrics as metrics_router
from app.services.embedding_service import embedding_engine_manager
from app.services.inference_service import inference_engine_manager
from app.services.metrics import metrics_writer
from app.services.model_download_service import model_download_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_download_manager.scan_on_startup()
    inference_engine_manager.warm_up()
    embedding_engine_manager.warm_up()
    await metrics_writer.start()
    yield
    await metrics_writer.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analytics.router)
app.include_router(models.router)
app.include_router(settings_router.router)
app.include_router(chat.router)
app.include_router(embeddings.router)
app.include_router(embedding_model.router)
if settings.enable_prometheus_metrics:
    app.include_router(metrics_router.router)


@app.exception_handler(HTTPException)
async def openai_compatible_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if request.url.path.startswith("/v1/") and isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    if request.url.path.startswith("/v1/"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": str(exc.detail), "type": "invalid_request_error", "param": None, "code": None}},
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def openai_compatible_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if not request.url.path.startswith("/v1/"):
        return JSONResponse(
            status_code=422, content={"detail": jsonable_encoder(exc.errors())}
        )
    first_error = exc.errors()[0] if exc.errors() else {}
    param = ".".join(str(p) for p in first_error.get("loc", []) if p != "body")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": first_error.get("msg", "Invalid request."),
                "type": "invalid_request_error",
                "param": param or None,
                "code": None,
            }
        },
    )
