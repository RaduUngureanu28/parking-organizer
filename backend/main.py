from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import optimizer

app = FastAPI() 

app.add_middleware(CORSMiddleware, 
                   allow_origins = ["http://localhost:5173"],
                   allow_credentials = True,
                   allow_methods = ["*"],
                   allow_headers = ["*"])

class Point(BaseModel):
    x: float
    y: float

class OptimizeRequest(BaseModel):
    outline: List[Point]
    blocked_zones: List[List[Point]]
    entrance: Point

@app.post("/optimize")
def optimize(request: OptimizeRequest):
    try:
        # Temporarily call optimize_layout2 to test margins
        result = optimizer.optimize_layout2(
            outline=[(p.x, p.y) for p in request.outline],
            blocked_zones=[[(p.x, p.y) for p in zone] for zone in request.blocked_zones],
            entrance=(request.entrance.x, request.entrance.y)
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))