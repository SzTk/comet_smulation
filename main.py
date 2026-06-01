from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.core.middleware import EmailAllowlistMiddleware
from api.routes import router

app = FastAPI(title="Comet Simulation")
app.add_middleware(EmailAllowlistMiddleware)
app.include_router(router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
