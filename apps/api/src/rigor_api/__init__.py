"""Rigor API package composition.

Extension routers are attached to the final FastAPI application after the core
app is created. The execution and solution modules own independent routers, so
route registration no longer depends on mutating a router that FastAPI already
copied.
"""

from . import execution_patches as execution_patches
from . import attachment_progress_patch as attachment_progress_patch
from . import execution_routes as execution_routes
from . import knowledge_catalog_routes as knowledge_catalog_routes
from . import knowledge_progress_routes as knowledge_progress_routes
from . import knowledge_routes as knowledge_routes
from . import attachment_solution_routes as attachment_solution_routes
from . import main as main

main.app.include_router(execution_routes.router)
main.app.include_router(attachment_solution_routes.router)
