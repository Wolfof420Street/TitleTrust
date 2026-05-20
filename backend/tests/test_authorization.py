from backend.core.authorization import _expand_roles, _permissions_for_roles
from backend.domain.authz import Permission, Role


def test_role_hierarchy_expansion():
    expanded = _expand_roles([Role.AUDITOR.value])
    assert Role.AUDITOR in expanded
    assert Role.ANALYST in expanded
    assert Role.REVIEWER in expanded


def test_permission_mapping():
    perms = _permissions_for_roles({Role.REVIEWER})
    assert Permission.AUDIT_READ in perms
    assert Permission.FORENSIC_RUN not in perms
