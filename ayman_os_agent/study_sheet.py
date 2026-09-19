from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import get_data_dir, get_study_sheet_path, get_study_sheet_url

try:
    from openpyxl import load_workbook
except Exception:  # pragma: no cover
    load_workbook = None


class StudySheetManager:
    """Read the study tracking workbook used by the agent."""

    def __init__(self, workbook_path: str | None = None) -> None:
        self.remote_error: str | None = None
        self.workbook_path = self._resolve_path(workbook_path)

    def _resolve_path(self, workbook_path: str | None) -> Path | None:
        if workbook_path:
            path = Path(workbook_path).expanduser()
            return path if path.exists() else path

        explicit = get_study_sheet_path()
        if explicit:
            return Path(explicit).expanduser()

        remote_url = get_study_sheet_url()
        if remote_url:
            remote_path = get_data_dir() / "study-sheet.xlsx"
            try:
                self._download_remote_workbook(remote_url, remote_path)
                return remote_path
            except HTTPError as exc:
                self.remote_error = f"Google Sheet download failed with HTTP {exc.code}."
                if remote_path.exists():
                    return remote_path
                return None
            except URLError as exc:
                self.remote_error = f"Google Sheet download failed: {exc.reason}."
                if remote_path.exists():
                    return remote_path
                return None

        candidates: list[Path] = []
        for base_dir in (
            Path.cwd(),
            Path.cwd().parent,
            Path.home(),
            Path.home() / "OneDrive" / "Desktop",
            Path.home() / "OneDrive" / "Desktop" / "aymn OS",
        ):
            if not base_dir.exists():
                continue
            candidates.extend(
                [
                    base_dir / "Study Mentor OS — Ayman.xlsx",
                    base_dir / "Study Mentor OS - Ayman.xlsx",
                    base_dir / "Study Mentor OS.xlsx",
                ]
            )
            candidates.extend(sorted(base_dir.glob("*.xlsx")))

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _download_remote_workbook(url: str, destination: Path) -> None:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if "spreadsheets" not in parts or "d" not in parts:
            raise ValueError("AYMAN_STUDY_SHEET_URL must be a Google Sheets URL.")
        sheet_id = parts[parts.index("d") + 1]
        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        request = Request(export_url, headers={"User-Agent": "ayman-os-agent/0.2"})
        with urlopen(request, timeout=30) as response:
            content = response.read()
        if not content.startswith(b"PK"):
            raise ValueError("Google Sheet export did not return an XLSX workbook.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def is_available(self) -> bool:
        return bool(self.workbook_path and self.workbook_path.exists() and load_workbook is not None)

    def load_workbook(self):
        if not self.is_available():
            return None
        return load_workbook(self.workbook_path, data_only=True)

    @staticmethod
    def _normalize_value(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "isoformat") and not isinstance(value, str):
            return value.isoformat()
        return str(value).strip()

    @staticmethod
    def _rows_as_dicts(rows: list[tuple[Any, ...]]):
        if not rows:
            return []
        headers = [str(cell).strip() for cell in rows[0]]
        entries = []
        for row in rows[1:]:
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue
            mapping = {}
            for idx, header in enumerate(headers):
                value = row[idx] if idx < len(row) else ""
                mapping[header] = StudySheetManager._normalize_value(value)
            entries.append(mapping)
        return entries

    def summary(self) -> str:
        if not self.is_available():
            if self.remote_error:
                return f"تعذر تحميل ورقة الدراسة من Google Sheets. {self.remote_error}"
            return (
                "ملف ورقة الدراسة غير متوفر. اضبط AYMAN_STUDY_SHEET_URL أو "
                "AYMAN_STUDY_SHEET أو STUDY_SHEET_PATH."
            )

        workbook = self.load_workbook()
        if workbook is None:
            return "تعذر فتح ملف ورقة الدراسة. تأكد من أن الملف Excel صالح." 

        def get_sheet_rows(name: str) -> list[tuple[Any, ...]]:
            sheet = workbook[name]
            rows = list(sheet.iter_rows(values_only=True))
            return [tuple(self._normalize_value(cell) for cell in row) for row in rows if any(cell is not None and str(cell).strip() for cell in row)]

        config_rows = get_sheet_rows("Config")
        config_map = {}
        if config_rows:
            config_map = {row[0]: row[1] if len(row) > 1 else "" for row in config_rows[1:] if row and row[0]}

        schedule_rows = get_sheet_rows("Schedule")
        course_rows = get_sheet_rows("Courses")
        daily_rows = get_sheet_rows("DailyLog")
        alerts_rows = get_sheet_rows("Alerts")

        schedule_preview = []
        if len(schedule_rows) > 1:
            for row in schedule_rows[1:6]:
                if len(row) >= 6:
                    schedule_preview.append(f"- {row[0]}: {row[3]} ({row[1]} - {row[2]})")

        course_entries = self._rows_as_dicts(course_rows)
        high_risk_courses = [
            item for item in course_entries
            if item.get("Risk", "").upper() in {"HIGH", "MEDIUM"}
        ]
        high_risk_courses.sort(key=lambda x: float(x.get("Priority", "999") or 999))

        latest_daily = None
        if daily_rows and len(daily_rows) > 1:
            latest_daily = self._rows_as_dicts(daily_rows)[-1]

        latest_alert = None
        if alerts_rows and len(alerts_rows) > 1:
            latest_alert = self._rows_as_dicts(alerts_rows)[-1]

        lines = [
            "## ملخص ورقة الدراسة",
            f"الملف: {self.workbook_path}",
            f"اسم الطالب: {config_map.get('STUDENT_NAME', '-')}",
            f"بريد الطالب: {config_map.get('STUDENT_EMAIL', '-')}",
            f"بريد الوالد: {config_map.get('PARENT_EMAIL', '-')}",
            "",
            "### جدول اليوم والمواد",
        ]

        if schedule_preview:
            lines.extend(schedule_preview)
        else:
            lines.append("- لا توجد مواعيد مسجلة في الجدول.")

        lines.extend(["", "### المواد ذات الأولوية العالية"])
        if high_risk_courses:
            for item in high_risk_courses[:5]:
                risk = item.get("Risk", "UNKNOWN")
                priority = item.get("Priority", "-")
                target = item.get("WeeklyTargetMin", "-")
                lines.append(f"- {item.get('Code', item.get('Key', '-'))}: {item.get('Name', '-')} | Risk={risk} | Priority={priority} | Target={target} min")
        else:
            lines.append("- لا توجد مواد مطابقة.")

        lines.extend(["", "### آخر سجل يومي"])
        if latest_daily:
            lines.append(
                f"- TotalMin={latest_daily.get('TotalMin', '-')}, Confidence={latest_daily.get('Confidence', '-')}, "
                f"HardestCourse={latest_daily.get('HardestCourse', '-')}, NeedHelp={latest_daily.get('NeedHelp', '-')}"
            )
        else:
            lines.append("- لا يوجد سجل يومي حديث.")

        lines.extend(["", "### آخر تنبيه"])
        if latest_alert:
            lines.append(f"- {latest_alert.get('Severity', '-')} | {latest_alert.get('Type', '-')} | {latest_alert.get('Message', '-')}")
        else:
            lines.append("- لا يوجد تنبيه مسجل.")

        return "\n".join(lines)
