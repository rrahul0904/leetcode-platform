"""Rigor API package.

Register extension modules before composing the FastAPI application, then make
execution-route ownership explicit on the final app. This avoids relying on
APIRouter side effects and guarantees that legacy synchronous Run/Submit paths
cannot shadow the durable execution plane.
"""

from fastapi.routing import APIRoute

# Apply execution compatibility/progress patches before the API or execution
# controller imports their module-level runner/finalizer references.
from . import execution_patches as execution_patches
from . import attachment_progress_patch as attachment_progress_patch
from . import execution_routes as execution_routes
from . import knowledge_catalog_routes as knowledge_catalog_routes
from . import knowledge_progress_routes as knowledge_progress_routes
from . import knowledge_routes as knowledge_routes
from . import attachment_solution_routes as attachment_solution_routes

# ``main`` is intentionally imported after extension modules. The final route
# table is normalized below so durable handlers are the only owners of the
# Run/Submit execution paths.
from . import main as main

_EXECUTION_ROUTES: dict[tuple[str, str], object] = {
    ("/api/v1/questions/{slug}/run", "POST"): execution_routes.queue_run_for_question,
    (
        "/api/v1/questions/{slug}/submissions",
        "POST",
    ): execution_routes.queue_submit_for_question,
    (
        "/api/v1/executions/{execution_id}",
        "GET",
    ): execution_routes.get_candidate_execution,
    (
        "/api/v1/executions/{execution_id}/cancel",
        "POST",
    ): execution_routes.cancel_candidate_execution,
}
_SOLUTION_ROUTE = "/api/v1/questions/{slug}/solution"


def _is_owned_route(route: object) -> bool:
    if not isinstance(route, APIRoute):
        return False
    return any(
        route.path == path and method in route.methods
        for path, method in _EXECUTION_ROUTES
    ) or (route.path == _SOLUTION_ROUTE and "GET" in route.methods)


# FastAPI copies router contents when routers are included. Remove any copied
# legacy/dynamically registered variants and attach the authoritative durable
# routes directly to the application in a deterministic order.
main.app.router.routes[:] = [
    route for route in main.app.router.routes if not _is_owned_route(route)
]
main.app.include_router(execution_routes.router, prefix="/api/v1")
main.app.add_api_route(
    _SOLUTION_ROUTE,
    attachment_solution_routes.reveal_question_solution,
    methods=["GET"],
    tags=["practice"],
)
