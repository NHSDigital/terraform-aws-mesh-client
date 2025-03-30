from unittest.mock import patch

from mesh_lock_manager_application import MeshLockManagerApplication

from mocked.mesh_testing_common import was_value_logged

app = MeshLockManagerApplication()


@patch("shared.application.release_lock")
def test_happy_path(rel_lock, capsys):
    mock_event = {
        "EventDetail": {
            "body": {"lock_name": "test_lock", "execution_id": "test_execution"}
        },
        "Operation": "release",
    }

    app.main(mock_event, {})
    logs = capsys.readouterr()
    assert was_value_logged(logs.out, "MESHLOCK0002", "Log_Level", "INFO")


def test_operation_not_remove(capsys):
    mock_event = {
        "EventDetail": {
            "body": {"lock_name": "test_lock", "execution_id": "test_execution"}
        },
        "Operation": {"not release"},
    }

    app.main(mock_event, {})
    logs = capsys.readouterr()
    assert not was_value_logged(logs.out, "MESHLOCK0002", "Log_Level", "INFO")
