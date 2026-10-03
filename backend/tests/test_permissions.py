from types import SimpleNamespace

from backend.app.security.permissions import PermissionLevel, PermissionManager


def test_safe_tools_can_execute_without_confirmation():
    manager = PermissionManager()

    assert manager.can_execute(SimpleNamespace(permission=PermissionLevel.SAFE))


def test_confirm_tools_require_confirmation():
    manager = PermissionManager()
    tool = SimpleNamespace(permission=PermissionLevel.CONFIRM)

    assert not manager.can_execute(tool)
    assert manager.can_execute(tool, confirmed=True)


def test_blocked_tools_cannot_execute():
    manager = PermissionManager()

    assert not manager.can_execute(SimpleNamespace(permission=PermissionLevel.BLOCKED))


def test_unknown_permission_is_denied():
    manager = PermissionManager()

    assert not manager.can_execute(SimpleNamespace(permission="UNKNOWN"))
