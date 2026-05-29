import asyncio
import json
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from physics.simulation import SimulationParams, run_simulation

router = APIRouter()

# In-memory job store: job_id -> asyncio.Queue of SSE messages
_jobs: dict[str, asyncio.Queue] = {}

PRESETS = [
    {"name": "ダークマターなし",   "rho0": 0.0,  "rs": 20.0,
     "description": "純粋なニュートン重力のみ"},
    {"name": "標準銀河系ハロー",   "rho0": 0.3,  "rs": 20.0,
     "description": "観測値ベースの天の川銀河NFWハロー"},
    {"name": "高密度ハロー",        "rho0": 3.0,  "rs": 10.0,
     "description": "高密度・小スケール半径の極端なケース"},
]


class DarkMatterParams(BaseModel):
    rho0: float
    rs: float


class CometParams(BaseModel):
    semi_major_axis_au: float
    eccentricity: float
    inclination_deg: float


class SimulateRequest(BaseModel):
    dark_matter: DarkMatterParams
    comet: CometParams
    duration_years: float | None = None
    timestep_years: float = 100.0
    n_output_points: int = 5000


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/presets")
def get_presets():
    return PRESETS


@router.post("/simulate")
async def start_simulation(req: SimulateRequest):
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _jobs[job_id] = queue

    params = SimulationParams(
        rho0_gev_cm3=req.dark_matter.rho0,
        rs_kpc=req.dark_matter.rs,
        semi_major_axis_au=req.comet.semi_major_axis_au,
        eccentricity=req.comet.eccentricity,
        inclination_deg=req.comet.inclination_deg,
        duration_years=req.duration_years,
        timestep_years=req.timestep_years,
        n_output_points=req.n_output_points,
    )

    loop = asyncio.get_running_loop()

    def run_and_enqueue():
        def progress_cb(pct: int):
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "progress", "percent": pct}), loop
            )

        result = run_simulation(params, progress_cb=progress_cb)
        result["type"] = "result"
        asyncio.run_coroutine_threadsafe(queue.put(result), loop)
        asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel

    loop.run_in_executor(None, run_and_enqueue)
    return {"job_id": job_id}


@router.get("/simulate/{job_id}/stream")
async def stream_simulation(job_id: str):
    queue = _jobs.get(job_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            msg = await queue.get()
            if msg is None:
                _jobs.pop(job_id, None)
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
