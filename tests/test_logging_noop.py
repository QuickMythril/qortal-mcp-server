from qortal_mcp.server import _log_tool_result


def test_log_tool_result_handles_non_dict():
    # Should not raise even if result is not a dict.
    _log_tool_result("dummy", {"ok": True})
    _log_tool_result("dummy", {"error": "fail"})
    _log_tool_result("dummy", None)  # type: ignore[arg-type]
