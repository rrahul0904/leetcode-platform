"""Rigor API package.

Import route-registration modules before ``rigor_api.main`` builds the FastAPI
application. Each module attaches its versioned routes to the existing practice
router, preserving one API surface without introducing a second application.
"""

from . import knowledge_catalog_routes as knowledge_catalog_routes
from . import knowledge_progress_routes as knowledge_progress_routes
from . import knowledge_candidate_context_routes as knowledge_candidate_context_routes
from . import knowledge_routes as knowledge_routes
