from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from api.routes import router

app = FastAPI(title="Comet Simulation")
app.include_router(router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
