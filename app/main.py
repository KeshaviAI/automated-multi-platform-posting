import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import PostRequest, PostResponse
from app.services import posting_service

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Automated Multi-Platform Posting", version="1.0.0")


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(p) for p in e["loc"][1:]) or "body",
         "message": e["msg"][13:] if e["msg"].startswith("Value error, ") else e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"success": False, "errors": errors})


@app.post("/posting", response_model=PostResponse)
async def posting(req: PostRequest) -> PostResponse:
    results = await posting_service.publish_all(req.message, req.link)
    return PostResponse(success=any(r.status == "success" for r in results), results=results)
