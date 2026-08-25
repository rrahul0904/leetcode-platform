"""Rigor API package.

Import route-registration modules before ``rigor_api.main`` builds the FastAPI
application. Each module attaches its versioned routes to the existing practice
router, preserving one API surface without introducing a second application.
"""

# Apply execution compatibility/progress patches before the API or execution
# controller imports their module-level runner/finalizer references.
from . import execution_patches as execution_patches
from . import attachment_progress_patch as attachment_progress_patch
# Register the durable execution routes on the practice router. They support
# both Python and PostgreSQL and are included before the legacy synchronous
# submissions router in main.py.
from . import execution_routes as execution_routes
from . import knowledge_catalog_routes as knowledge_catalog_routes
from . import knowledge_progress_routes as knowledge_progress_routes
from . import knowledge_routes as knowledge_routes
from . import attachment_solution_routes as attachment_solution_routes
