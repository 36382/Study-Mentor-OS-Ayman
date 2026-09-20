"""OSAgent: the study-mentor brain.

Security model:
- NO shell execution, NO arbitrary file read/write, NO OS tooling.
- The only writable destinations are the study Google Sheet (via SheetStore)
  and the agent's own data dir (legacy appointments fallback).
- Free-form messages go through the AI tool-use loop; every tool call is
  validated against a strict whitelist in :meth:`execute_tool`.
"""

from __future__ import annotations

import re
from collections import deque

from .ai_service import TOOL_NAMES, AIService
from .config import get_parent_email, get_telegram_chat_ids, get_telegram_token, get_timezone_name
from .notifications import AlertManager
from .reporting import ParentReportBuilder
from .scheduler import AppointmentManager
from .sheet_store import SheetStore
from .study_sheet import StudySheetManager, field
from .tasks import TaskManager
from .timeutils import now, parse_date, parse_time, today_iso

SYSTEM_PROMPT = (
    "أنت «المرشد الدراسي» في نظام Study Mentor OS. دورك: متابعة مذاكرة الطالب، تسجيل جلساته، "
    "تنظيم مهامه ومواعيده، وتحفيزه باختصار.\n"
    "قواعد:\n"
    "- أجب بالعربية، بحد أقصى 6 أسطر، وبلا حشو أو تكرار للسؤال.\n"
    "- استخدم الأدوات لجلب الحقائق أو تسجيل الأفعال؛ لا تخترع أرقاماً.\n"
    "- عند ذكر الطالب أن ذاكر جلسة، سجّلها بأداة log_study مباشرة.\n"
    "- التاريخ والوقت الحاليان سيُزوَّدان لك في هذه الرسالة؛ استخدمهما لحسم «اليوم/غداً».\n"
    "- المواعيد والمهام تُحفظ في شيت الدراسة تلقائياً عند استخدام الأدوات."
)


def _clean_minutes(value: object) -> int | None:
    try:
        minutes = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if minutes < 1 or minutes > 600:
        return None
    return minutes


def _clean_code(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()[:20]


class OSAgent:
    """Safe, sheet-backed study mentor agent."""

    def __init__(self, store: SheetStore | None = None, data_dir=None) -> None:
        self.store = store or SheetStore.from_env()
        self.study_sheet = StudySheetManager(self.store)
        self.scheduler = AppointmentManager(self.store)
        self.tasks = TaskManager(self.store)
        self.report_builder = ParentReportBuilder(self.scheduler, self.study_sheet, self.tasks)
        self.alert_manager = AlertManager()
        self.ai = AIService()
        self._sessions: dict[str, deque] = {}

    # ================================================================ facts

    def sheet_mode(self) -> str:
        return self.study_sheet.mode()

    def today_summary(self) -> str:
        if not self.study_sheet.is_available():
            return self.study_sheet.summary()
        minutes = self.study_sheet.minutes_logged_today()
        latest = self.study_sheet.latest_daily()
        lines = [
            "## ملخص اليوم",
            f"التاريخ: {today_iso()} ({get_timezone_name()})",
            f"دقائق مسجلة اليوم (جلسات البوت): {minutes:g}" if minutes else "لا توجد جلسات مسجلة اليوم بعد.",
        ]
        if latest:
            lines.append(
                f"آخر سجل يومي: TotalMin={field(latest, 'totalmin', 'total_min', default='-')}, "
                f"Confidence={field(latest, 'confidence', default='-')}"
            )
        open_tasks = self.tasks.open_items()
        if open_tasks:
            lines.append(f"مهام مفتوحة: {len(open_tasks)} — استخدم /tasks لعرضها.")
        lines.extend(
            [
                "",
                "### توصية سريعة",
                "- ابدأ بالمادة الأعلى مخاطرة (أمر /risk).",
                "- سجّل كل جلسة فور انتهائها: /log CS120 45",
            ]
        )
        return "\n".join(lines)

    def risk_summary(self) -> str:
        top = self.study_sheet.top_risk_course()
        if top is None:
            return self.study_sheet.summary()
        ranked = self.study_sheet.high_risk_courses()
        lines = [
            "## تقييم المخاطرة",
            f"أعلى مخاطرة الآن: {field(top, 'code', 'key', default='-')} - {field(top, 'name', default='-')}",
            f"Risk={field(top, 'risk', default='-')} | Priority={field(top, 'priority', default='-')} "
            f"| Target={field(top, 'weeklytargetmin', 'target', default='-')} min",
        ]
        if len(ranked) > 1:
            others = "، ".join(str(field(item, "code", "key", default="?")) for item in ranked[1:4])
            lines.append(f"مواد عالية الخطورة التالية: {others}")
        lines.append("التوصية: خصص فترة ثابتة يومية لهذه المادة قبل أي مراجعة أقل أهمية.")
        return "\n".join(lines)

    def study_sheet_summary(self) -> str:
        return self.study_sheet.summary()

    def parent_report(self) -> str:
        return self.report_builder.build("تقرير الوالد")

    def status_summary(self) -> str:
        writable = self.store.is_writable()
        mode = "قراءة + كتابة (Google Sheets)" if writable else ("قراءة فقط (XLSX)" if self.study_sheet.is_available() else "غير متصل")
        lines = [
            "## حالة الوكيل",
            f"التوقيت: {get_timezone_name()} — الآن {now().strftime('%Y-%m-%d %H:%M')}",
            f"مصدر البيانات: {mode}",
        ]
        if writable:
            sync = self.store.last_sync_at.strftime("%H:%M:%S") if self.store.last_sync_at else "-"
            lines.append(f"آخر مزامنة شيت: {sync}")
        if self.store.last_error:
            lines.append(f"⚠️ آخر خطأ شيت: {self.store.last_error[:160]}")
        lines.append(f"مزود الذكاء: {self.ai.backend_name()}")
        lines.append(f"تيليجرام: {len(get_telegram_chat_ids())} مستخدم مصرح")
        return "\n".join(lines)

    # ================================================================ actions

    def log_study(self, code: str, minutes: int, note: str = "") -> str:
        code = _clean_code(code)
        minutes = _clean_minutes(minutes)
        if not code:
            return "حدد رمز المادة. مثال: /log CS120 45"
        if minutes is None:
            return "المدة يجب أن تكون بين 1 و600 دقيقة."
        if not self.store.is_writable():
            return "وضع القراءة فقط: تسجيل الجلسات يتطلب اتصال الكتابة بالشيت (GOOGLE_SERVICE_ACCOUNT_JSON)."
        timestamp = now().strftime("%H:%M")
        ok = self.store.append_row(
            "SessionLog",
            [today_iso(), timestamp, code, minutes, note.strip()[:120]],
            ["Date", "Time", "CourseCode", "Minutes", "Note"],
        )
        if not ok:
            return f"تعذر الحفظ في الشيت: {self.store.last_error}"
        return f"✅ سجلت {minutes} دقيقة على {code} اليوم ({timestamp}). استمر!"

    def add_appointment(self, title: str, date: str, time: str = "09:00", note: str = "") -> str:
        return self.scheduler.add(title, date, time, note)

    def list_appointments(self) -> str:
        return self.scheduler.upcoming()

    def tasks_overview(self) -> str:
        return self.tasks.list()

    def complete_task(self, query: str) -> str:
        return self.tasks.mark_done(query)

    def send_parent_report_now(self) -> str:
        report = self.parent_report()
        results = []
        chat_ids = get_telegram_chat_ids()
        token = get_telegram_token()
        if token and chat_ids:
            for chat_id in chat_ids:
                results.append(self.alert_manager.send_telegram_message(report, chat_id))
        else:
            results.append("لم يتم ضبط TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID لإرسال التقرير في تيليجرام.")
        parent_email = get_parent_email()
        if parent_email:
            results.append(self.alert_manager.send_email(parent_email, "تقرير يومي من Study Mentor OS", report))
        return "\n".join(results)

    # ================================================================ AI turn

    def session_history(self, chat_key: str) -> deque:
        return self._sessions.setdefault(chat_key, deque(maxlen=12))

    def ai_turn(self, user_text: str, chat_key: str = "default") -> str:
        """Run one user message through the tool-use loop with short session memory."""
        if not self.ai.is_available():
            return self.execute(user_text)

        current = now()
        system_prompt = (
            f"{SYSTEM_PROMPT}\nالتاريخ والوقت الآن: {current.strftime('%Y-%m-%d %H:%M')} بتوقيت {get_timezone_name()}."
        )

        convo: list[dict] = []
        for message in self.session_history(chat_key):
            convo.append({"role": message["role"], "content": [{"text": message["text"]}]})
        convo.append({"role": "user", "content": [{"text": user_text}]})

        final_text = ""
        for _ in range(5):
            text, calls = self.ai.converse(convo, system_prompt=system_prompt)
            if not calls:
                final_text = text or "لم أستطع توليد رد، أعد المحاولة."
                break
            assistant_blocks: list[dict] = []
            if text:
                assistant_blocks.append({"text": text})
            for call in calls:
                assistant_blocks.append(
                    {"toolUse": {"toolUseId": call["id"], "name": call["name"], "input": call.get("args") or {}}}
                )
            convo.append({"role": "assistant", "content": assistant_blocks})

            result_blocks = []
            for call in calls:
                outcome = self.execute_tool(call["name"], call.get("args") or {})
                result_blocks.append(
                    {
                        "toolResult": {
                            "toolUseId": call["id"],
                            "name": call["name"],
                            "content": [{"text": outcome[:1200]}],
                        }
                    }
                )
            convo.append({"role": "user", "content": result_blocks})
        else:
            final_text = self.ai.converse(convo, system_prompt=system_prompt, tools=None)[0] or "تمت معالجة طلبك."

        history = self.session_history(chat_key)
        history.append({"role": "user", "text": user_text})
        history.append({"role": "assistant", "text": final_text})
        return final_text

    def execute_tool(self, name: str, args: dict) -> str:
        """Strict whitelist dispatch. Anything unknown or malformed is rejected."""
        if name not in TOOL_NAMES:
            return f"أداة غير معروفة: {name}"
        args = args if isinstance(args, dict) else {}

        if name == "get_today_summary":
            return self.today_summary()
        if name == "get_risk":
            return self.risk_summary()
        if name == "list_tasks":
            return self.tasks_overview()
        if name == "list_appointments":
            return self.list_appointments()
        if name == "send_parent_report":
            return self.send_parent_report_now()
        if name == "log_study":
            return self.log_study(args.get("code"), args.get("minutes"), str(args.get("note") or ""))
        if name == "mark_task_done":
            query = str(args.get("query") or args.get("task") or "").strip()
            if not query:
                return "حدد المهمة المطلوب إنجازها."
            return self.complete_task(query)
        if name == "add_appointment":
            title = str(args.get("title") or "").strip()
            date_value = str(args.get("date") or "").strip()
            time_value = str(args.get("time") or "09:00").strip()
            if not title:
                return "عنوان الموعد مطلوب."
            if parse_date(date_value) is None:
                return "تاريخ غير صالح، استخدم YYYY-MM-DD."
            parsed_time = parse_time(time_value)
            if parsed_time is None:
                return "وقت غير صالح، استخدم HH:MM."
            return self.add_appointment(title, date_value, parsed_time.strftime("%H:%M"))
        return f"أداة غير مطبقة: {name}"

    # ================================================================ fast path (no AI)

    def execute(self, prompt: str) -> str:
        """Keyword router used for direct commands and as the no-AI fallback."""
        text = (prompt or "").strip()
        if not text:
            return "اكتب سؤالك أو استخدم /help."

        lowered = text.lower()

        if re.search(r"risk|maturity|مخاطر|مخاطرة|أخطر|اخطر", lowered):
            return self.risk_summary()
        if re.search(r"today|summary|ملخص|اليوم|وضع اليوم", lowered):
            return self.today_summary()
        if re.search(r"sheet|workbook|ورقة|الشيت", lowered):
            return self.study_sheet_summary()
        if re.search(r"appointment|schedule|موعد|مواعيد|تقويم", lowered):
            return self.list_appointments()
        if re.search(r"tasks?|مهام|مهمة|واجب|واجبات", lowered):
            return self.tasks_overview()
        if re.search(r"report|تقرير", lowered):
            return self.parent_report()
        if re.search(r"status|حالة", lowered):
            return self.status_summary()
        return (
            "لم أفهم الطلب بدقة. جرّب:\n"
            "- /summary ملخص اليوم\n"
            "- /risk المواد الأخطر\n"
            "- /log CS120 45 لتسجيل جلسة\n"
            "- /tasks و /done\n"
            "- أو اكتب سؤالك بحرية ليجيب المرشد الذكي."
        )


# ================================================================ CLI

def interactive_loop() -> None:
    agent = OSAgent()
    print("Study Mentor OS — وضع تفاعلي (أوامر آمنة فقط). اكتب «خروج» للخروج.")
    while True:
        try:
            prompt = input("study-mentor> ")
        except EOFError:
            print()
            return
        if prompt.strip().lower() in {"exit", "quit", "bye", "خروج"}:
            print("إلى اللقاء!")
            return
        print(agent.ai_turn(prompt) if agent.ai.is_available() else agent.execute(prompt))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Study Mentor OS agent (safe, sheet-backed)")
    parser.add_argument("prompt", nargs="?", help="سؤال أو أمر بالعربية أو الإنجليزية")
    parser.add_argument("--sheet", action="store_true", help="ملخص ورقة الدراسة")
    parser.add_argument("--risk", action="store_true", help="المادة الأعلى مخاطرة")
    parser.add_argument("--summary", action="store_true", help="ملخص اليوم")
    parser.add_argument("--tasks", action="store_true", help="المهام المفتوحة")
    parser.add_argument("--report", action="store_true", help="تقرير الوالد")
    parser.add_argument("--status", action="store_true", help="حالة النظام")
    parser.add_argument("--interactive", action="store_true", help="وضع تفاعلي")
    args = parser.parse_args(argv)

    agent = OSAgent()

    if args.interactive:
        interactive_loop()
        return 0
    if args.sheet:
        print(agent.study_sheet_summary())
    elif args.risk:
        print(agent.risk_summary())
    elif args.summary:
        print(agent.today_summary())
    elif args.tasks:
        print(agent.tasks_overview())
    elif args.report:
        print(agent.parent_report())
    elif args.status:
        print(agent.status_summary())
    elif args.prompt is not None:
        print(agent.ai_turn(args.prompt) if agent.ai.is_available() else agent.execute(args.prompt))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
