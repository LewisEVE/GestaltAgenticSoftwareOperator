"""FastAPI entrypoint and runtime bootstrap for Gestalt Core."""

from __future__ import annotations

from contextlib import asynccontextmanager, suppress

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from prometheus_fastapi_instrumentator import Instrumentator

from gestalt.blackboard import GestaltBlackboard
from gestalt.config import GestaltSettings, get_settings
from gestalt.events import MemoryEventBus, build_event_bus
from gestalt.graph import build_graph, run_cycle, scheduler_request
from gestalt.protocol import (
    BlackboardQuery,
    CycleRequest,
    CycleResponse,
    HealthResponse,
    TriggerAuditRequest,
)
from gestalt.tools import ToolRegistry
from gestalt.tools.implementations import (
    BlackboardQueryTool,
    BlackboardWriteTool,
    HttpRequestTool,
    KubernetesPatchTool,
    KubernetesReadTool,
    PrometheusQueryTool,
    RedisStreamInspectTool,
    SandboxCommandTool,
)
from gestalt.utils import GestaltRuntime, ModelGateway, configure_logging, get_logger
from gestalt.utils.telemetry import configure_tracing, shutdown_tracing

logger = get_logger(__name__)


def _register_tools(runtime: GestaltRuntime) -> None:
    runtime.tool_registry.bulk_register(
        [
            BlackboardQueryTool(runtime.blackboard),
            BlackboardWriteTool(runtime.blackboard),
            PrometheusQueryTool(),
            HttpRequestTool(runtime.settings.security),
            SandboxCommandTool(),
            RedisStreamInspectTool(),
            KubernetesReadTool(),
            KubernetesPatchTool(),
        ],
    )


async def build_runtime(settings: GestaltSettings) -> GestaltRuntime:
    """Initialize the shared runtime dependencies."""

    configure_logging(settings.telemetry.log_level)
    configure_tracing(settings.telemetry)
    blackboard = GestaltBlackboard(settings.blackboard)
    await blackboard.initialize()
    event_bus = build_event_bus(settings.events)
    try:
        await event_bus.initialize()
    except Exception as exc:
        if settings.blackboard.is_sqlite:
            logger.warning(
                "event bus initialization failed; falling back to in-memory bus",
                extra={"error": str(exc), "backend": settings.events.backend},
            )
            with suppress(Exception):
                await event_bus.close()
            event_bus = MemoryEventBus(settings.events)
            await event_bus.initialize()
        else:
            raise
    runtime = GestaltRuntime(
        settings=settings,
        blackboard=blackboard,
        event_bus=event_bus,
        tool_registry=ToolRegistry(),
        model_gateway=ModelGateway(settings.models),
    )
    _register_tools(runtime)
    build_graph(runtime)
    scheduler = build_scheduler(runtime)
    scheduler.start()
    runtime.scheduler = scheduler
    return runtime


async def shutdown_runtime(runtime: GestaltRuntime) -> None:
    """Gracefully shut down shared runtime dependencies."""

    if runtime.scheduler is not None:
        runtime.scheduler.shutdown(wait=False)
    await runtime.event_bus.close()
    await runtime.blackboard.close()
    shutdown_tracing()


def build_scheduler(runtime: GestaltRuntime) -> AsyncIOScheduler:
    """Configure periodic jobs that feed the super-graph."""

    scheduler = AsyncIOScheduler(timezone=runtime.settings.scheduler.timezone)
    scheduler.add_job(
        run_cycle,
        "interval",
        minutes=runtime.settings.scheduler.monitor_interval_minutes,
        id="monitor",
        replace_existing=True,
        args=[runtime, scheduler_request("Scheduled monitoring cycle", scheduled_agent="monitor")],
        max_instances=1,
    )
    scheduler.add_job(
        run_cycle,
        "interval",
        hours=runtime.settings.scheduler.security_audit_interval_hours,
        id="security_audit",
        replace_existing=True,
        args=[
            runtime,
            scheduler_request("Scheduled security audit cycle", scheduled_agent="security_audit"),
        ],
        max_instances=1,
    )
    scheduler.add_job(
        run_cycle,
        "interval",
        minutes=runtime.settings.scheduler.knowledge_maintenance_minutes,
        id="knowledge_maintenance",
        replace_existing=True,
        args=[runtime, scheduler_request("Scheduled knowledge curation", scheduled_agent="knowledge")],
        max_instances=1,
    )
    scheduler.add_job(
        run_cycle,
        "interval",
        minutes=runtime.settings.scheduler.optimizer_interval_minutes,
        id="optimizer_maintenance",
        replace_existing=True,
        args=[runtime, scheduler_request("Scheduled optimization maintenance", scheduled_agent="optimizer")],
        max_instances=1,
    )
    return scheduler


def create_app(settings: GestaltSettings | None = None) -> FastAPI:
    """Create the FastAPI application instance."""

    resolved_settings = settings or get_settings()
    app = FastAPI(title=resolved_settings.app.name, version=resolved_settings.version)

    @asynccontextmanager
    async def lifespan(current_app: FastAPI):
        runtime = await build_runtime(resolved_settings)
        current_app.state.runtime = runtime
        yield
        await shutdown_runtime(runtime)

    app.router.lifespan_context = lifespan
    Instrumentator().instrument(app).expose(app)

    async def get_runtime(request: Request) -> GestaltRuntime:
        runtime = getattr(request.app.state, "runtime", None)
        if runtime is None:
            runtime = await build_runtime(resolved_settings)
            request.app.state.runtime = runtime
            request.app.state.runtime_initialized_outside_lifespan = True
        return runtime

    async def require_admin_token(
        authorization: str | None = Header(default=None),
    ) -> None:
        expected = resolved_settings.app.admin_token.get_secret_value()
        if not authorization or authorization.removeprefix("Bearer ").strip() != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token.")

    @app.get("/health/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        return HealthResponse(status="live", version=resolved_settings.version)

    @app.get("/health/ready", response_model=HealthResponse)
    async def ready(runtime: GestaltRuntime = Depends(get_runtime)) -> HealthResponse:
        latest_stats = await runtime.blackboard.get_latest_stats()
        return HealthResponse(
            status="ready",
            version=resolved_settings.version,
            dependencies={
                "blackboard": "ready",
                "event_bus": "ready",
                "graph": "ready" if runtime.graph is not None else "initializing",
                "stats": "present" if latest_stats is not None else "absent",
            },
        )

    @app.post("/api/v1/cycles/run", response_model=CycleResponse, dependencies=[Depends(require_admin_token)])
    async def trigger_cycle(
        payload: CycleRequest,
        runtime: GestaltRuntime = Depends(get_runtime),
    ) -> CycleResponse:
        state = await run_cycle(runtime, payload)
        return CycleResponse(
            trace_id=state.trace_id,
            cycle_id=state.cycle_id,
            accepted=True,
            summary=state.latest_summary,
            commands=state.commands,
        )

    @app.post("/api/v1/audit/trigger", response_model=CycleResponse, dependencies=[Depends(require_admin_token)])
    async def trigger_audit(
        payload: TriggerAuditRequest,
        runtime: GestaltRuntime = Depends(get_runtime),
    ) -> CycleResponse:
        state = await run_cycle(
            runtime,
            CycleRequest(
                objective="Manual security audit trigger",
                metadata={**payload.metadata, "force_audit": True, "audit_scope": payload.scope},
            ),
        )
        return CycleResponse(
            trace_id=state.trace_id,
            cycle_id=state.cycle_id,
            accepted=True,
            summary=state.latest_summary,
            commands=state.commands,
        )

    @app.get("/api/v1/stats/latest")
    async def latest_stats(runtime: GestaltRuntime = Depends(get_runtime)):
        report = await runtime.blackboard.get_latest_stats()
        return report.model_dump(mode="json") if report is not None else {}

    @app.post("/api/v1/blackboard/query", dependencies=[Depends(require_admin_token)])
    async def query_blackboard(
        payload: BlackboardQuery,
        runtime: GestaltRuntime = Depends(get_runtime),
    ):
        result = await runtime.blackboard.query_memory(payload)
        return result.model_dump(mode="json")

    return app


app = create_app()
