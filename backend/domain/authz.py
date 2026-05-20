from enum import Enum
from typing import Dict, Set


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    AUDITOR = "auditor"
    ANALYST = "analyst"
    REVIEWER = "reviewer"


class Permission(str, Enum):
    AUDIT_START = "audit:start"
    AUDIT_READ = "audit:read"
    AUDIT_RETRY = "audit:retry"
    FORENSIC_RUN = "forensic:run"
    GEOSPATIAL_RUN = "geospatial:run"
    TITBITS_READ = "titbits:read"
    DEVICE_SESSION_MANAGE = "device-session:manage"


ROLE_HIERARCHY: Dict[Role, Set[Role]] = {
    Role.SUPER_ADMIN: {Role.SUPER_ADMIN, Role.AUDITOR, Role.ANALYST, Role.REVIEWER},
    Role.AUDITOR: {Role.AUDITOR, Role.ANALYST, Role.REVIEWER},
    Role.ANALYST: {Role.ANALYST, Role.REVIEWER},
    Role.REVIEWER: {Role.REVIEWER},
}

ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.SUPER_ADMIN: set(Permission),
    Role.AUDITOR: {
        Permission.AUDIT_READ,
        Permission.AUDIT_RETRY,
        Permission.FORENSIC_RUN,
        Permission.GEOSPATIAL_RUN,
        Permission.TITBITS_READ,
        Permission.DEVICE_SESSION_MANAGE,
    },
    Role.ANALYST: {
        Permission.AUDIT_START,
        Permission.AUDIT_READ,
        Permission.FORENSIC_RUN,
        Permission.GEOSPATIAL_RUN,
        Permission.TITBITS_READ,
        Permission.DEVICE_SESSION_MANAGE,
    },
    Role.REVIEWER: {Permission.AUDIT_READ, Permission.TITBITS_READ, Permission.DEVICE_SESSION_MANAGE},
}
