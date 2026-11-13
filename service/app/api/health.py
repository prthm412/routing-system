from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


@router.get("/health")
def health(request: Request) -> JSONResponse:
    city = request.app.state.city
    try:
        with request.app.state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database_ok = True
    except SQLAlchemyError:
        database_ok = False
    body = {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
        "graph": {"nodes": city.node_count, "edges": city.edge_count},
    }
    return JSONResponse(body, status_code=200 if database_ok else 503)