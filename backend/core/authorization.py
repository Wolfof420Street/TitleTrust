import logging
from typing import Any, Callable, Dict, Iterable, Optional, Set

from fastapi import Depends, HTTPException, status

try:
    from backend.domain.authz import Permission, ROLE_HIERARCHY, ROLE_PERMISSIONS, Role
except ModuleNotFoundError:
    from domain.authz import Permission, ROLE_HIERARCHY, ROLE_PERMISSIONS, Role

logger = logging.getLogger("TitleTrust-Authorization")


def _expand_roles(raw_roles: Iterable[str]) -> Set[Role]:
    resolved: Set[Role] = set()
    for raw in raw_roles:
        try:
            role = Role(raw)
        except ValueError:
            continue
        resolved.update(ROLE_HIERARCHY[role])
    return resolved


def _permissions_for_roles(roles: Set[Role]) -> Set[Permission]:
    perms: Set[Permission] = set()
    for role in roles:
        perms.update(ROLE_PERMISSIONS.get(role, set()))
    return perms


def require_permission(permission: Permission):
    try:
        from backend.auth import get_current_user
        from backend.repositories.policy_repository import PolicyRepository
        from backend.services.firebase import db
    except ModuleNotFoundError:
        from auth import get_current_user
        from repositories.policy_repository import PolicyRepository
        from services.firebase import db

    def dependency(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        claims = user.get("claims", {}) if isinstance(user, dict) else {}
        roles_claim = claims.get("roles") or user.get("roles") or [Role.REVIEWER.value]
        if isinstance(roles_claim, str):
            roles_claim = [roles_claim]

        org_id = claims.get("org_id") or user.get("org_id") or "personal"
        PolicyRepository(db).upsert_membership(
            org_id,
            user.get("uid", "unknown"),
            {
                "roles": list(roles_claim),
                "attributes": claims.get("attributes", {}),
            },
        )

        roles = _expand_roles(roles_claim)
        permissions = _permissions_for_roles(roles)

        if permission not in permissions:
            logger.warning(
                "Authorization denied",
                extra={"uid": user.get("uid"), "permission": permission.value, "roles": list(roles_claim)},
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        return user

    return dependency


def require_resource_permission(
    permission: Permission,
    resource_resolver: Callable[..., Optional[Dict[str, Any]]],
):
    try:
        from backend.auth import get_current_user
    except ModuleNotFoundError:
        from auth import get_current_user

    def dependency(*args, user: Dict[str, Any] = Depends(get_current_user), **kwargs) -> Dict[str, Any]:
        try:
            from backend.repositories.policy_repository import PolicyRepository
            from backend.services.firebase import db
            from backend.services.policy_service import PolicyService
        except ModuleNotFoundError:
            from repositories.policy_repository import PolicyRepository
            from services.firebase import db
            from services.policy_service import PolicyService

        policy_service = PolicyService(PolicyRepository(db))
        claims = user.get("claims", {}) if isinstance(user, dict) else {}
        roles_claim = claims.get("roles") or user.get("roles") or [Role.REVIEWER.value]
        if isinstance(roles_claim, str):
            roles_claim = [roles_claim]

        org_id = claims.get("org_id") or user.get("org_id") or "personal"
        PolicyRepository(db).upsert_membership(
            org_id,
            user.get("uid", "unknown"),
            {
                "roles": list(roles_claim),
                "attributes": claims.get("attributes", {}),
            },
        )
        resource = resource_resolver(*args, **kwargs)
        allowed, reason = policy_service.evaluate(
            action=permission.value,
            organization_id=org_id,
            user_id=user.get("uid", "unknown"),
            resource=resource,
            claims=claims,
        )
        if not allowed:
            logger.warning(
                "Authorization denied",
                extra={
                    "uid": user.get("uid"),
                    "permission": permission.value,
                    "roles": list(roles_claim),
                    "organization_id": org_id,
                    "reason": reason,
                },
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency
