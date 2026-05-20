from backend.services.policy_service import PolicyService


class FakePolicyRepository:
    def __init__(self):
        self.memberships = {
            ("org-1", "user-1"): {"roles": ["analyst"], "attributes": {"region": "nairobi"}},
            ("org-1", "user-2"): {"roles": ["reviewer"], "attributes": {"region": "mombasa"}},
        }

    def get_policy(self, organization_id):
        return {
            "statements": [
                {"effect": "allow", "actions": ["forensic:run"], "roles": ["analyst"]},
                {
                    "effect": "allow",
                    "actions": ["audit:read"],
                    "roles": ["reviewer"],
                    "conditions": {"owner_only": True},
                },
                {"effect": "deny", "actions": ["audit:read"], "roles": ["reviewer"], "conditions": {"required_attributes": {"region": "blocked"}}},
            ]
        }

    def get_membership(self, organization_id, user_id):
        return self.memberships.get((organization_id, user_id))


def test_policy_service_allows_matching_role():
    service = PolicyService(FakePolicyRepository())
    allowed, reason = service.evaluate(action="forensic:run", organization_id="org-1", user_id="user-1")
    assert allowed is True
    assert reason == "Policy allow"


def test_policy_service_enforces_owner_only():
    service = PolicyService(FakePolicyRepository())
    allowed, _ = service.evaluate(
        action="audit:read",
        organization_id="org-1",
        user_id="user-2",
        resource={"user_id": "user-1", "organization_id": "org-1"},
    )
    assert allowed is False
