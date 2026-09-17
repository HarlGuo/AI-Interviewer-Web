from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from httpx import HTTPError

from .ai_resume_reviewer import review_resume
from .auth import CurrentUser, get_current_user
from .access_control import commit_daily_interview, release_daily_interview, require_approved, reserve_daily_interview
from .config import settings
from .agents.interviewer import interviewer_agent
from .deepseek import DeepSeekNotConfiguredError
from .llm.deepseek import LLMNotConfiguredError
from .resume_parser import parse_pdf
from .schemas import AnalyticsEventRequest, FeedbackRequest, InterviewAgentStartRequest, InterviewReport, InterviewStartResponse, InterviewStatusRequest, InterviewTurnRequest, InterviewTurnResponse, ReportRequest, ResumeParseResponse
from .supabase_store import (
    record_feedback,
    record_interview_draft,
    record_interview_start,
    record_interview_turn,
    record_product_event,
    record_report,
    update_interview_status,
    upsert_attribution,
)
from .telemetry_context import reset_telemetry_context, set_telemetry_context

app = FastAPI(title="AI Interviewer API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["*"])


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {"status": "ok", "deepseek_configured": bool(settings.deepseek_api_key), "model": settings.deepseek_model, "auth_mode": settings.auth_mode, "supabase_configured": settings.supabase_auth_enabled, "analytics_configured": settings.analytics_enabled, "app_version": settings.app_version, "agent_version": settings.agent_version}


@app.post("/v1/resumes/parse", response_model=ResumeParseResponse)
async def parse_resume(file: UploadFile = File(...), _user: CurrentUser = Depends(get_current_user)) -> ResumeParseResponse:
    await require_approved(_user)
    if file.content_type not in {"application/pdf", "application/octet-stream"} and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="只支持 PDF 简历")
    data = await file.read(10 * 1024 * 1024 + 1)
    context_token = set_telemetry_context(user_id=_user.id)
    try:
        parsed = parse_pdf(file.filename or "resume.pdf", data)
        return await review_resume(parsed)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="AI 简历复核服务尚未配置") from error
    except HTTPError as error:
        raise HTTPException(status_code=502, detail="AI 简历复核失败，请稍后重试") from error
    finally:
        reset_telemetry_context(context_token)


@app.post("/v1/interviews", response_model=InterviewStartResponse)
async def create_interview(config: InterviewAgentStartRequest, _user: CurrentUser = Depends(get_current_user)) -> InterviewStartResponse:
    reservation_id = await reserve_daily_interview(_user)
    interview_id = str(uuid4())
    draft_stored = await record_interview_draft(_user.id, interview_id, config)
    if settings.analytics_enabled and not draft_stored:
        await release_daily_interview(_user, reservation_id)
        raise HTTPException(status_code=503, detail="面试记录暂时无法创建，请稍后重试")
    context_token = set_telemetry_context(user_id=_user.id, interview_id=interview_id)
    try:
        result = await interviewer_agent.start(config, interview_id=interview_id)
        saved = await record_interview_start(_user.id, config, result)
        if settings.analytics_enabled and not saved:
            await release_daily_interview(_user, reservation_id)
            await update_interview_status(_user.id, interview_id, "failed")
            raise HTTPException(status_code=503, detail="第一题已生成，但面试记录保存失败；本次不计入每日限额，请重试")
        await commit_daily_interview(_user, reservation_id)
        return result
    except (DeepSeekNotConfiguredError, LLMNotConfiguredError) as error:
        await release_daily_interview(_user, reservation_id)
        await update_interview_status(_user.id, interview_id, "failed")
        raise HTTPException(status_code=503, detail="面试服务暂不可用，请稍后重试") from error
    except HTTPError as error:
        await release_daily_interview(_user, reservation_id)
        await update_interview_status(_user.id, interview_id, "failed")
        raise HTTPException(status_code=502, detail="面试问题生成失败，请稍后重试") from error
    except (KeyError, ValueError, RuntimeError) as error:
        await release_daily_interview(_user, reservation_id)
        await update_interview_status(_user.id, interview_id, "failed")
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        reset_telemetry_context(context_token)


@app.post("/v1/interviews/turn", response_model=InterviewTurnResponse)
async def interview_turn(request: InterviewTurnRequest, _user: CurrentUser = Depends(get_current_user)) -> InterviewTurnResponse:
    await require_approved(_user)
    context_token = set_telemetry_context(user_id=_user.id, interview_id=request.interview_id)
    try:
        result = await interviewer_agent.advance(request)
        await record_interview_turn(_user.id, request, result)
        return result
    except (DeepSeekNotConfiguredError, LLMNotConfiguredError) as error:
        raise HTTPException(status_code=503, detail="面试服务暂不可用，请稍后重试") from error
    except HTTPError as error:
        raise HTTPException(status_code=502, detail="动态追问生成失败，请稍后重试") from error
    except (KeyError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        reset_telemetry_context(context_token)


@app.post("/v1/reports", response_model=InterviewReport)
async def create_report(request: ReportRequest, _user: CurrentUser = Depends(get_current_user)) -> InterviewReport:
    await require_approved(_user)
    interview_id = str(request.interview_id)
    context_token = set_telemetry_context(user_id=_user.id, interview_id=interview_id)
    try:
        report = await interviewer_agent.report(request)
        await record_report(_user.id, interview_id, report)
        return report
    except (DeepSeekNotConfiguredError, LLMNotConfiguredError) as error:
        raise HTTPException(status_code=503, detail="报告服务尚未配置") from error
    except (HTTPError, KeyError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=502, detail="报告生成失败，请稍后重试") from error
    finally:
        reset_telemetry_context(context_token)


@app.patch("/v1/interviews/{interview_id}/status")
async def change_interview_status(interview_id: str, request: InterviewStatusRequest, _user: CurrentUser = Depends(get_current_user)) -> dict[str, bool]:
    await require_approved(_user)
    stored = await update_interview_status(_user.id, interview_id, request.status)
    if not stored and settings.analytics_enabled:
        raise HTTPException(status_code=503, detail="面试状态暂时无法保存")
    return {"saved": stored}


@app.post("/v1/interviews/{interview_id}/feedback")
async def submit_interview_feedback(interview_id: str, request: FeedbackRequest, _user: CurrentUser = Depends(get_current_user)) -> dict[str, bool]:
    await require_approved(_user)
    stored = await record_feedback(_user.id, interview_id, request)
    if not stored:
        raise HTTPException(status_code=503, detail="反馈暂时无法保存")
    return {"saved": True}


@app.post("/v1/analytics/events", status_code=202)
async def ingest_analytics_event(request: AnalyticsEventRequest, _user: CurrentUser = Depends(get_current_user)) -> dict[str, bool]:
    stored = await record_product_event(_user.id, request)
    if request.event_name in {"landing_viewed", "registration_created"}:
        await upsert_attribution(_user.id, request)
    if not stored:
        raise HTTPException(status_code=503, detail="埋点服务尚未配置")
    return {"accepted": True}


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
