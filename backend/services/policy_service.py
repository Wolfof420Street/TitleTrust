from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

try:
    from backend.repositories.policy_repository import PolicyRepository
except ModuleNotFoundError:
    from repositories.policy_repository import PolicyRepository


class PolicyService:
    def __init__(self, repository: PolicyRepository, ttl_seconds: int = 30) -> None:
        self._repository = repository
        self._ttl_seconds = ttl_seconds
        self._policy_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._membership_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def _cached_policy(self, organization_id: str) -> Dict[str, Any]:
        cached = self._policy_cache.get(organization_id)
        now = time.time()
        if cached and now - cached[0] < self._ttl_seconds:
            return cached[1]
        policy = self._repository.get_policy(organization_id)
        self._policy_cache[organization_id] = (now, policy)
        return policy

    def _cached_membership(self, organization_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        key = f"{organization_id}:{user_id}"
        cached = self._membership_cache.get(key)
        now = time.time()
        if cached and now - cached[0] < self._ttl_seconds:
            return cached[1]
        membership = self._repository.get_membership(organization_id, user_id)
        if membership:
            self._membership_cache[key] = (now, membership)
        return membership

    def evaluate(
        self,
        *,
        action: str,
        organization_id: str,
        user_id: str,
        resource: Optional[Dict[str, Any]] = None,
        claims: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        membership = self._cached_membership(organization_id, user_id)
        if not membership:
            return False, "No organization membership"

        if resource and resource.get("organization_id") not in {None, organization_id}:
            return False, "Tenant boundary violation"

        roles = set(membership.get("roles", []))
        attributes = membership.get("attributes", {})
        effective_policy = self._cached_policy(organization_id)
        statements = effective_policy.get("statements", [])

        explicit_deny = False
        allow = False
        for statement in statements:
            if action not in statement.get("actions", []):
                continue
            if roles.isdisjoint(set(statement.get("roles", []))):
                continue

            conditions = statement.get("conditions", {})
            if conditions.get("owner_only") and resource and resource.get("user_id") != user_id:
                continue
            if "required_attributes" in conditions:
                required = conditions["required_attributes"]
                if any(attributes.get(key) != value for key, value in required.items()):
                    continue

            if statement.get("effect") == "deny":
                explicit_deny = True
            elif statement.get("effect") == "allow":
                allow = True

        if explicit_deny:
            return False, "Explicit policy deny"
        if allow:
            return True, "Policy allow"
        return False, "No matching allow policy"
