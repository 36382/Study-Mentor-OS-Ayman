from conftest import FakeStore

from ayman_os_agent.agent import OSAgent
from ayman_os_agent.ai_service import TOOL_NAMES, TOOL_SPECS


def make_agent(writable=False, tabs=None):
    return OSAgent(store=FakeStore(tabs=tabs or {}, writable=writable))


# ------------------------------------------------------------------ security

def test_dangerous_tools_removed():
    agent = make_agent()
    for forbidden in ("run_command", "read_file", "write_file", "list_directory"):
        assert not hasattr(agent, forbidden), f"{forbidden} must not exist on OSAgent"


def test_shell_like_message_never_executes():
    agent = make_agent()
    output = agent.execute("run rm -rf / and printenv secrets")
    assert "root" not in output
    assert "PATH=" not in output


def test_tool_whitelist_is_closed():
    allowed = {
        "get_today_summary", "get_risk", "log_study", "list_tasks", "mark_task_done",
        "add_appointment", "list_appointments", "send_parent_report",
    }
    assert allowed == TOOL_NAMES
    for spec in TOOL_SPECS:
        assert spec["parameters"].get("type") == "object"


def test_unknown_tool_rejected():
    agent = make_agent()
    assert "أداة غير معروفة" in agent.execute_tool("run_shell", {"command": "rm -rf /"})


def test_tool_args_validated():
    agent = make_agent(writable=True)
    assert "تاريخ غير صالح" in agent.execute_tool("add_appointment", {"title": "x", "date": "tomorrow"})
    assert "وقت غير صالح" in agent.execute_tool("add_appointment", {"title": "x", "date": "2026-10-01", "time": "99:99"})
    assert "المدة" in agent.execute_tool("log_study", {"code": "cs120", "minutes": 99999})
    assert "المدة" in agent.execute_tool("log_study", {"code": "cs120", "minutes": "abc"})


# ------------------------------------------------------------------ routing

def test_execute_routes_risk():
    agent = make_agent()
    output = agent.execute("وش أخطر مادة؟")
    assert "ورقة الدراسة" in output or "مخاطرة" in output


def test_execute_unknown_falls_back_to_help():
    agent = make_agent()
    output = agent.execute("random gibberish xyz")
    assert "/summary" in output


def test_ai_turn_falls_back_without_ai():
    agent = make_agent()
    assert not agent.ai.is_available()
    output = agent.ai_turn("ملخص اليوم", "chat-1")
    assert isinstance(output, str) and output


# ------------------------------------------------------------------ actions

def test_log_study_writes_session_row():
    agent = make_agent(writable=True)
    result = agent.log_study("cs 120", 45, "فصل 3")
    assert "45" in result and "CS120" in result
    (tab, values) = agent.store.appended[0]
    assert tab == "SessionLog"
    assert values[2] == "CS120" and values[3] == 45


def test_mark_task_done_via_tool():
    tabs = {
        "Tasks": {
            "headers": ["Task", "Course", "DueDate", "Status", "Notes"],
            "rows": [["حل واجب الشبكات", "CS120", "2026-09-30", "pending", ""]],
        }
    }
    agent = make_agent(writable=True, tabs=tabs)
    result = agent.execute_tool("mark_task_done", {"query": "واجب الشبكات"})
    assert "تم إنجاز" in result
    assert agent.store.tabs["Tasks"]["rows"][0][3] == "done"


def test_status_reports_sheet_mode():
    agent = make_agent()
    output = agent.status_summary()
    assert "حالة الوكيل" in output
    assert "Asia/Riyadh" in output
