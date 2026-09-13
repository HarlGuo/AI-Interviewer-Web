from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from httpx import HTTPError

from .ai_resume_reviewer import review_resume
from .auth import CurrentUser, get_current_user
from .access_control import commit_daily_interview, release_daily_interview, require_approved, reserve_daily_interview
from .config import settings
from .agents.interview_graph import advance_interview, start_interview
from .deepseek import DeepSeekNotConfiguredError, generate_report
from .llm.deepseek import LLMNotConfiguredError
from .resume_parser import parse_pdf
from .schemas import InterviewAgentStartRequest, InterviewReport, InterviewStartResponse, InterviewTurnRequest, InterviewTurnResponse, ReportRequest, ResumeParseResponse

app = FastAPI(title="AI Interviewer API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {"status": "ok", "deepseek_configured": bool(settings.deepseek_api_key), "model": settings.deepseek_model, "auth_mode": settings.auth_mode, "supabase_configured": settings.supabase_auth_enabled}


@app.post("/v1/resumes/parse", response_model=ResumeParseResponse)
async def parse_resume(file: UploadFile = File(...), _user: CurrentUser = Depends(get_current_user)) -> ResumeParseResponse:
    await require_approved(_user)
    if file.content_type not in {"application/pdf", "application/octet-stream"} and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="只支持 PDF 简历")
    data = await file.read(10 * 1024 * 1024 + 1)
    try:
        parsed = parse_pdf(file.filename or "resume.pdf", data)
        return await review_resume(parsed)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="AI 简历复核服务尚未配置") from error
    except HTTPError as error:
        raise HTTPException(status_code=502, detail="AI 简历复核失败，请稍后重试") from error


@app.post("/v1/interviews", response_model=InterviewStartResponse)
async def create_interview(config: InterviewAgentStartRequest, _user: CurrentUser = Depends(get_current_user)) -> InterviewStartResponse:
    reservation_id = await reserve_daily_interview(_user)
    try:
        result = await start_interview(config)
        await commit_daily_interview(_user, reservation_id)
        return result
    except (DeepSeekNotConfiguredError, LLMNotConfiguredError) as error:
        await release_daily_interview(_user, reservation_id)
        raise HTTPException(status_code=503, detail="面试 Agent 尚未配置") from error
    except HTTPError as error:
        await release_daily_interview(_user, reservation_id)
        raise HTTPException(status_code=502, detail="面试问题生成失败，请稍后重试") from error
    except (KeyError, ValueError, RuntimeError) as error:
        await release_daily_interview(_user, reservation_id)
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/v1/interviews/turn", response_model=InterviewTurnResponse)
async def interview_turn(request: InterviewTurnRequest, _user: CurrentUser = Depends(get_current_user)) -> InterviewTurnResponse:
    await require_approved(_user)
    try:
        return await advance_interview(request)
    except (DeepSeekNotConfiguredError, LLMNotConfiguredError) as error:
        raise HTTPException(status_code=503, detail="面试 Agent 尚未配置") from error
    except HTTPError as error:
        raise HTTPException(status_code=502, detail="动态追问生成失败，请稍后重试") from error
    except (KeyError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/v1/reports", response_model=InterviewReport)
async def create_report(request: ReportRequest, _user: CurrentUser = Depends(get_current_user)) -> InterviewReport:
    await require_approved(_user)
    try:
        return await generate_report(request)
    except (DeepSeekNotConfiguredError, LLMNotConfiguredError) as error:
        raise HTTPException(status_code=503, detail="报告服务尚未配置") from error
    except (HTTPError, KeyError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=502, detail="报告生成失败，请稍后重试") from error


# FunctionGraph can serve the exported Expo Web client and API from one HTTP
# function. Local development keeps using the separate Expo dev server because
# this directory only exists in production packages.
frontend_dist = Path(__file__).resolve().parents[2] / "dist"
if frontend_dist.is_dir():
    expo_assets = frontend_dist / "_expo"
    if expo_assets.is_dir():
        app.mount("/_expo", StaticFiles(directory=expo_assets), name="expo-assets")

    @app.get("/runtime-config.js", include_in_schema=False)
    async def runtime_config() -> Response:
        config = {
            "supabaseUrl": settings.supabase_url or "",
            "supabasePublishableKey": settings.supabase_publishable_key or "",
        }
        script = f"globalThis.__AI_INTERVIEWER_CONFIG__={json.dumps(config, ensure_ascii=False)};"
        return Response(
            content=script,
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/{web_path:path}", include_in_schema=False)
    async def serve_web(web_path: str) -> FileResponse:
        relative = web_path.strip("/")
        candidates = []
        if relative:
            candidates.extend((frontend_dist / relative, frontend_dist / f"{relative}.html"))
        else:
            candidates.append(frontend_dist / "index.html")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_file() and frontend_dist.resolve() in resolved.parents:
                return FileResponse(resolved)
        return FileResponse(frontend_dist / "index.html")
