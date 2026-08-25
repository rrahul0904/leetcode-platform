"""Rigor API package.

Register extension routes before the FastAPI application is composed. FastAPI
copies APIRouter routes when ``include_router`` is called, so importing the app
before these modules finish would silently omit durable execution and governed
solution endpoints from the application route table.
"""

# Apply execution compatibility/progress patches before the API or execution
# controller imports their module-level runner/finalizer references.
from . import execution_patches as execution_patches
from . import attachment_progress_patch as attachment_progress_patch
# Register the durable execution routes on the practice router before main.py
# includes that router in the FastAPI application.
from . import execution_routes as execution_routes
from . import knowledge_catalog_routes as knowledge_catalog_routes
from . import knowledge_progress_routes as knowledge_progress_routes
from . import knowledge_routes as knowledge_routes
from . import attachment_solution_routes as attachment_solution_routes

# ``main`` is intentionally imported last. APIRouter.include_router copies the
# current route set, so this ordering is part of the API composition contract.
from . import main as main
