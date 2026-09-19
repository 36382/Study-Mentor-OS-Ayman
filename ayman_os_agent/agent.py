from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from .bedrock_service import BedrockService
from .notifications import AlertManager
from .reporting import ParentReportBuilder
from .scheduler import AppointmentManager
from .study_sheet import StudySheetManager


class OSAgent:
    """A proactive local OS agent with file, shell, AI, scheduling, and reporting tools."""

    def __init__(self, working_dir: Optional[str] = None) -> None:
        self.working_dir = Path(working_dir or os.getcwd()).resolve()
        self.scheduler = AppointmentManager()
        self.study_sheet = StudySheetManager()
        self.report_builder = ParentReportBuilder(self.scheduler, self.study_sheet)
        self.alert_manager = AlertManager()
        self.bedrock = BedrockService()

    def list_directory(self, path: Optional[str] = None) -> str:
        target = self._resolve_path(path)
        if not target.exists():
            return f"Path does not exist: {target}"
        if not target.is_dir():
            return f"Not a directory: {target}"

        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = [f"{p.name}{'/' if p.is_dir() else ''}" for p in entries]
        return "\n".join(lines) if lines else "(empty directory)"

    def read_file(self, path: str) -> str:
        target = self._resolve_path(path)
        if not target.exists():
            return f"File does not exist: {target}"
        if target.is_dir():
            return f"Path is a directory, not a file: {target}"
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return target.read_bytes().decode("utf-8", errors="replace")

    def write_file(self, path: str, content: str) -> str:
        target = self._resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Written {len(content.encode('utf-8'))} bytes to {target}"

    def run_command(self, command: str) -> str:
        if not command.strip():
            return "Empty command"
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = completed.stdout.strip()
            error = completed.stderr.strip()
            combined = "\n".join(part for part in [output, error] if part)
            return combined if combined else f"Command exited with status {completed.returncode}"
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds."

    def status_summary(self) -> str:
        items = self.list_directory(self.working_dir)
        ai_available = self.bedrock.is_available()
        gemini_cfg = self.bedrock.gemini_config
        ai_status = (
            f"✅ متصل ({self.bedrock.backend} - {gemini_cfg.get('model', 'gemini-3.6-flash')})"
            if ai_available
            else "❌ غير مضبوط (أرسل /setkey <المفتاح> أو اضبط GEMINI_API_KEY في لوحة Railway)"
        )
        sheet_status = "✅ متوفرة" if self.study_sheet.is_available() else "⚠️ غير متوفرة"
        return (
            "📊 حالة النظام والوكيل:\n"
            f"• الذكاء الاصطناعي: {ai_status}\n"
            f"• ورقة المتابعة: {sheet_status}\n"
            f"• الدليل الحالي: {self.working_dir}\n\n"
            "📁 المحتويات:\n"
            f"{items[:1000]}"
        )

    def parent_report(self) -> str:
        return self.report_builder.build("تقرير الوالد")

    def study_sheet_summary(self) -> str:
        return self.study_sheet.summary()

    def today_summary(self) -> str:
        summary = self.study_sheet_summary()
        if "ملف ورقة الدراسة غير متوفر" in summary:
            return summary
        return "\n".join([
            "## ملخص اليوم",
            summary,
            "",
            "### توصيّة سريعة",
            "- ركز أولاً على المادة ذات أعلى مخاطرة/أولوية.",
            "- حدّد 30-45 دقيقة يومياً لمراجعة CS120 أو المقرر الأضعف.",
            "- سجل اليوميات قبل نهاية اليوم لتجنب الانقطاع في التقارير.",
        ])

    def risk_summary(self) -> str:
        if not self.study_sheet.is_available():
            return self.study_sheet_summary()

        workbook = self.study_sheet.load_workbook()
        if workbook is None:
            return "تعذر قراءة ورقة الدراسة للـ risk summary."

        if "Courses" not in workbook.sheetnames:
            return "لا توجد ورقة باسم Courses في ملف الدراسة."

        rows = list(workbook["Courses"].iter_rows(values_only=True))
        if not rows:
            return "لا توجد بيانات في Course sheet."

        entries = []
        headers = [str(cell).strip() for cell in rows[0]]
        for row in rows[1:]:
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue
            entry = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            entries.append(entry)

        if not entries:
            return "لا توجد مواد مسجلة."

        ranked = sorted(entries, key=lambda item: (str(item.get("Risk", "")).upper() != "HIGH", float(item.get("Priority", 999) or 999), float(item.get("WeeklyTargetMin", 0) or 0)))
        top = ranked[0]
        return (
            "## تقييم المخاطرة\n"
            f"أعلى مخاطرة الآن: {top.get('Code', '-')} - {top.get('Name', '-')}\n"
            f"Risk={top.get('Risk', '-')} | Priority={top.get('Priority', '-')} | Target={top.get('WeeklyTargetMin', '-')} min\n"
            "التوصية: تخصّص فترة ثابتة يومية لهذه المادة قبل أي مراجعة أقل أهمية."
        )

    def add_appointment(self, title: str, date: str, time: str = "09:00", note: str = "") -> str:
        return self.scheduler.add(title, date, time, note)

    def list_appointments(self) -> str:
        return self.scheduler.list()

    def send_alert(self, to_email: str, subject: str, body: str) -> str:
        return self.alert_manager.send_email(to_email, subject, body)

    def execute(self, prompt: str) -> str:
        text = prompt.strip()
        if not text:
            return "No prompt provided."

        lowered = text.lower()

        if re.search(r"\b(risk|risk summary|check risk|maturity|مخاطرة|تقييم المخاطرة|تحليل المخاطر)\b", lowered):
            return self.risk_summary()

        if re.search(r"\b(today|summary today|daily summary|ملخص اليوم|اليوم)\b", lowered):
            return self.today_summary()

        if re.search(r"\b(sheet|workbook|excel|ورقة|جدول|study sheet|ملف الدراسة)\b", lowered):
            return self.study_sheet_summary()

        if re.search(r"\b(report|تقرير|summary|ملخص|parent)\b", lowered):
            return self.parent_report()

        if re.search(r"\b(appointment|schedule|calendar|event|موعد|تقويم|مواعيد)\b", lowered):
            if re.search(r"\b(list|show|عرض|مواعيد)\b", lowered):
                return self.list_appointments()
            match = re.search(
                r"(?:add|set|schedule|جد|حجز)\s+(?:appointment|event|موعد|جلسة)?\s*(?P<title>[A-Za-z0-9\u0600-\u06FF _-]+?)\s*(?:on|في|date|التاريخ)\s+(?P<date>\d{4}-\d{2}-\d{2})(?:\s*(?:at|في|time|الوقت)\s+(?P<time>\d{1,2}:\d{2}))?(?:\s*(?:note|ملاحظة)\s+(?P<note>.+))?",
                text,
                re.IGNORECASE,
            )
            if match:
                title = match.group("title").strip()
                date = match.group("date").strip()
                time = match.group("time") or "09:00"
                note = (match.group("note") or "").strip()
                return self.add_appointment(title, date, time, note)
            return "نمط غير واضح. مثال: أضف موعد مراجعة على 2026-09-17 في 09:00"

        if re.search(r"\b(send|email|alert|تنبيه|بريد)\b", lowered):
            email_match = re.search(r"(?:to|إلى)\s+([A-Za-z0-9_.%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text, re.IGNORECASE)
            subject_match = re.search(r"(?:subject|موضوع)\s+(.+?)(?:\s+(?:body|message|الرسالة)|$)", text, re.IGNORECASE)
            body_match = re.search(r"(?:body|message|الرسالة)\s+(.+)$", text, re.IGNORECASE)
            if email_match:
                to_email = email_match.group(1)
                subject = subject_match.group(1).strip() if subject_match else "تنبيه من Ayman OS Agent"
                body = body_match.group(1).strip() if body_match else "هذا تنبيه من الوكيل."
                return self.send_alert(to_email, subject, body)

        if re.search(r"\b(ai|ask|bedrock|chatgpt|assistant|ذكاء|ساعدني|شرح)\b", lowered):
            prompt_text = re.sub(r"^(?:ai|ask|bedrock|assistant|ذكاء|ساعدني)\s+", "", text, flags=re.IGNORECASE)
            system_prompt = "أنت مساعد شخصي ذكي. أجب بصياغة عملية وموجزة ومفيدة بالعربية." \
                if "arabic" in lowered or "عربي" in text else "You are a helpful personal assistant."
            return self.bedrock.generate(prompt_text, system_prompt)

        if re.search(r"\b(list|show|ls)\b", lowered):
            path = self._extract_path(text)
            return self.list_directory(path)

        if re.search(r"\b(read|open|cat|اقرأ|فتح)\b", lowered):
            path = self._extract_path(text)
            return self.read_file(path)

        if re.search(r"\b(write|create|save|اكتب|أنشئ|حفظ)\b", lowered):
            target = self._extract_path(text)
            content = self._extract_content(text)
            if not target:
                return "I need a file path to write to. Example: write /tmp/demo.txt with hello world"
            if content is None:
                return "I need content to write. Example: write /tmp/demo.txt with hello world"
            return self.write_file(target, content)

        if (
            re.search(r"^(?:python3?|pytest|bash|sh|pip3?|npm|node|git)\s+", text.strip())
            or re.search(r"\b(run|execute|shell|command|تشغيل|أمر)\b", lowered)
        ):
            command = self._extract_command(text)
            return self.run_command(command)

        if self.bedrock.is_available():
            system_prompt = (
                "أنت Ayman OS Agent، مساعد شخصي ومرشد دراسي ذكي. "
                "أجب بصياغة عملية ومفيدة وموجزة."
            )
            return self.bedrock.generate(text, system_prompt)

        return (
            "أستطيع أن أساعدك في: عرض الملفات، قراءة الملفات، كتابة الملفات، تشغيل الأوامر، "
            "إدارة المواعيد، إعداد التقارير، إرسال التنبيهات، والتفاعل مع AWS Bedrock و Gemini.\n"
            "أمثلة:\n"
            "- list current directory\n"
            "- read README.md\n"
            "- add appointment review on 2026-09-17 at 09:00\n"
            "- report\n"
            "- ask bedrock how to organize my day"
        )

    def _resolve_path(self, path: Optional[str]) -> Path:
        if not path:
            return self.working_dir
        candidate = str(path).strip().strip('"\'')
        resolved = Path(candidate)
        if not resolved.is_absolute():
            resolved = (self.working_dir / resolved).resolve()
        return resolved

    def _extract_path(self, text: str) -> Optional[str]:
        lowered = text.lower()
        if any(keyword in lowered for keyword in ["current directory", "working directory", "this directory", "الدليل الحالي", "الدليل الحالي"]):
            return "."

        patterns = [
            r"(?:read|open|list|show|write|create|save|اقرأ|فتح|اعرض|اكتب|أنشئ|حفظ)\s+(?:the\s+)?(?P<path>\"[^\"]+\"|'[^']+'|[A-Za-z0-9_.:/\\-]+(?:\s+[A-Za-z0-9_.:/\\-]+)*)",
            r"(?:in|at|for|to|في|على|إلى)\s+(?:the\s+)?(?P<path>\"[^\"]+\"|'[^']+'|[A-Za-z0-9_.:/\\-]+(?:\s+[A-Za-z0-9_.:/\\-]+)*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group("path").strip().strip('"\'')
                value = re.split(r"\s+(?:with|and|then|from|to|مع|و|ثم|من|إلى)\b", value, maxsplit=1, flags=re.IGNORECASE)[0].strip()
                if value.lower() in {"with", "and", "then", "from", "to", "مع", "و", "ثم", "من", "إلى"}:
                    continue
                return value
        return None

    def _extract_content(self, text: str) -> Optional[str]:
        match = re.search(r"(?:with|content|مع|محتوى)\s+(.*)$", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_command(self, text: str) -> str:
        match = re.search(r"(?:run|execute|command|تشغيل|أمر)\s+(.*)$", text, re.IGNORECASE)
        return match.group(1).strip() if match else text


def interactive_loop() -> None:
    agent = OSAgent()
    while True:
        try:
            prompt = input("ayman-os-agent> ")
        except EOFError:
            print()
            return
        if prompt.strip().lower() in {"exit", "quit", "bye", "خروج"}:
            print("Goodbye.")
            return
        result = agent.execute(prompt)
        print(result)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Ayman OS Agent")
    parser.add_argument("prompt", nargs="?", help="Natural language task to execute")
    parser.add_argument("--list", dest="list_path", help="List files in a path")
    parser.add_argument("--read", dest="read_path", help="Read a file")
    parser.add_argument("--write", nargs=2, metavar=("PATH", "TEXT"), help="Write text to a file")
    parser.add_argument("--run", dest="run_command", help="Run a shell command")
    parser.add_argument("--sheet", action="store_true", help="Show the study workbook summary")
    parser.add_argument("--risk", action="store_true", help="Show the highest risk academic course")
    parser.add_argument("--summary", action="store_true", help="Show a daily study summary")
    parser.add_argument("--interactive", action="store_true", help="Enter the REPL loop")
    parser.add_argument("--cwd", default=os.getcwd(), help="Working directory for the agent")
    args = parser.parse_args(argv)

    agent = OSAgent(args.cwd)

    if args.interactive:
        interactive_loop()
        return 0

    if args.list_path:
        print(agent.list_directory(args.list_path))
        return 0
    if args.read_path:
        print(agent.read_file(args.read_path))
        return 0
    if args.write:
        path, content = args.write
        print(agent.write_file(path, content))
        return 0
    if args.run_command:
        print(agent.run_command(args.run_command))
        return 0
    if args.sheet:
        print(agent.study_sheet_summary())
        return 0
    if args.risk:
        print(agent.risk_summary())
        return 0
    if args.summary:
        print(agent.today_summary())
        return 0
    if args.prompt is not None:
        print(agent.execute(args.prompt))
        return 0

    print("Ayman OS Agent\nUse --help for commands or run --interactive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
