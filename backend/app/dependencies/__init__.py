"""
Authentication and Authorization (RBAC) dependencies.
"""

from app.dependencies.auth import (
    get_current_user,
    get_optional_user,
    require_admin,
    require_staff_or_admin,
    require_catalog_access,
    require_roles,
)

__all__ = [
    "get_current_user",
    "get_optional_user",
    "require_admin",
    "require_staff_or_admin",
    "require_catalog_access",
    "require_roles",
]
