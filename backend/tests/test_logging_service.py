from app.services.logging_service import logging_service


def test_log_action_writes_and_reads_back(log_file):
    logging_service.log_action(
        user="admin", action="block_group", target="media", success=True, details="test"
    )
    logs = logging_service.get_recent_logs(limit=10)
    assert len(logs) == 1
    assert logs[0].action == "block_group"
    assert logs[0].success is True


def test_get_recent_logs_missing_file_returns_empty(tmp_path):
    logging_service.log_file = str(tmp_path / "does_not_exist.log")
    assert logging_service.get_recent_logs() == []


def test_get_recent_logs_respects_limit_and_order(log_file):
    for i in range(5):
        logging_service.log_action(
            user="admin", action="toggle_group", target=f"group{i}", success=True
        )
    logs = logging_service.get_recent_logs(limit=2)
    assert len(logs) == 2
    assert logs[0].target == "group4"  # más reciente primero
