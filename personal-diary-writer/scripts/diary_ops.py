#!/usr/bin/env python3
"""Create bounded diary scopes and atomically apply one approved mutation."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DATE_HEADING = re.compile(r"(?m)^# (\d{4}-\d{2}-\d{2})(?:[^\r\n]*)\r?$")
WEEKLY_HEADING = re.compile(
    r"(?m)^## \[(\d{4}-W\d{2})\] Weekly Cognitive Audit(?:[^\r\n]*)\r?$"
)
MONTHLY_HEADING = re.compile(
    r"(?m)^## \[(\d{4}-\d{2})\] Monthly Cognitive Audit(?:[^\r\n]*)\r?$"
)
QUARTERLY_HEADING = re.compile(
    r"(?m)^## \[(\d{4}-Q[1-4])\] Quarterly Cognitive Audit(?:[^\r\n]*)\r?$"
)
H2_HEADING = re.compile(r"(?m)^## (?!#)(?:[^\r\n]*)\r?$")
MARKDOWN_ATX_H1 = re.compile(r"(?m)^ {0,3}#(?!#)(?:[ \t]+|$)[^\r\n]*\r?$")
MARKDOWN_ATX_H2 = re.compile(r"(?m)^ {0,3}##(?!#)(?:[ \t]+|$)[^\r\n]*\r?$")
MARKDOWN_SETEXT = re.compile(r"(?m)^ {0,3}(?:=+|-+)[ \t]*\r?$")
PERSONAL_DIARY_H2 = (
    "## 今日事项",
    "## 今日进展与证据",
    "## 判断与反思",
    "## 时间背景",
    "## 能量管理（描述性生理背景）",
    "## 明日事项",
    "## 风险与未知",
    "## 行动闭环",
)
DEFAULT_ROOT = Path("C:/Users/shich/MEMORY/raw/privacy/Diary")
SESSION_ROOT = Path("C:/Users/shich/.pi/agent/sessions")
WEEKLY_GATE = Path(
    "C:/Users/shich/.pi/agent/skills/personal-cognitive-auditor/scripts/audit_gate.py"
)
PERIODIC_TOPOLOGY = WEEKLY_GATE.with_name("periodic_topology.py")
CONFIRMATION_PREFIXES = ("确认写入", "确认保存")
PERSONAL_DIARY_AUTOSAVE_DENY_KEYWORDS = (
    "不写",
    "不要写",
    "禁止写",
    "无需写",
    "暂不写",
    "别写",
    "草稿",
    "预览",
    "只读",
    "不保存",
    "不要保存",
    "暂不保存",
    "无需保存",
    "仅供查看",
    "修改技能",
    "更新技能",
    "修复技能",
    "审计技能",
    "检查技能",
    "查看技能",
    "创建技能",
)
PERSONAL_DIARY_VALID_PREFIXES = (
    "更新个人日志",
    "更新个人日记",
    "更新今日日志",
    "生成个人日志",
    "生成个人日记",
    "记录个人日志",
    "记录今日日志",
    "写个人日志",
    "写个人日记",
    "写今日日志",
    "记个人日志",
    "记日记",
    "保存个人日志",
    "保存个人日记",
)


class DiaryError(ValueError):
    """A fail-closed diary contract violation."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _normalized_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve())).replace("\\", "/")


def _quarter(day: date) -> int:
    return ((day.month - 1) // 3) + 1


def canonical_target(day: date, kind: str) -> Path:
    if kind == "personal":
        return DEFAULT_ROOT / f"{day.year}-Q{_quarter(day)}.md"
    raise DiaryError(f"unsupported diary kind: {kind}")


def _validate_target(target: Path, day: date, kind: str) -> None:
    expected = canonical_target(day, kind)
    if _normalized_path(target) != _normalized_path(expected):
        raise DiaryError(
            f"target is not canonical for {day.isoformat()} and kind={kind}: "
            f"expected {expected}"
        )


def _audit_spec(
    day: date,
    action: str,
    week: str | None,
    month: str | None,
    quarter: str | None,
) -> tuple[str, str, re.Pattern[str], str]:
    values = {"week": week, "month": month, "quarter": quarter}
    supplied = [name for name, value in values.items() if value is not None]
    if action == "replace-weekly-audit" and supplied == ["week"]:
        match = re.fullmatch(r"(\d{4})-W(\d{2})", week or "")
        if not match:
            raise DiaryError("weekly audit requires an ISO week in YYYY-Www form")
        try:
            period_end = date.fromisocalendar(
                int(match.group(1)), int(match.group(2)), 7
            )
        except ValueError as exc:
            raise DiaryError(f"invalid ISO week: {week}") from exc
        label, period_id, heading = "weekly", week or "", WEEKLY_HEADING
    elif action == "replace-monthly-audit" and supplied == ["month"]:
        match = re.fullmatch(r"(\d{4})-(\d{2})", month or "")
        if not match:
            raise DiaryError("monthly audit requires a month in YYYY-MM form")
        year, month_number = int(match.group(1)), int(match.group(2))
        if not 1 <= month_number <= 12:
            raise DiaryError("monthly audit requires a month in YYYY-MM form")
        period_end = date(
            year, month_number, calendar.monthrange(year, month_number)[1]
        )
        label, period_id, heading = "monthly", month or "", MONTHLY_HEADING
    elif action == "replace-quarterly-audit" and supplied == ["quarter"]:
        match = re.fullmatch(r"(\d{4})-Q([1-4])", quarter or "")
        if not match:
            raise DiaryError("quarterly audit requires a quarter in YYYY-QN form")
        year, quarter_number = int(match.group(1)), int(match.group(2))
        end_month = quarter_number * 3
        period_end = date(year, end_month, calendar.monthrange(year, end_month)[1])
        label, period_id, heading = "quarterly", quarter or "", QUARTERLY_HEADING
    else:
        raise DiaryError(
            f"audit action and period identifier do not match: action={action}, "
            f"week={week}, month={month}, quarter={quarter}"
        )
    if day != period_end:
        raise DiaryError(
            f"{label} audit date must equal period end: {period_end.isoformat()}"
        )
    return label, period_id, heading, f"{label}_audit_gate"


def _validate_matrix(
    day: date,
    kind: str,
    action: str,
    week: str | None,
    month: str | None,
    quarter: str | None,
) -> str:
    if action in {"replace-date", "replace-personal-diary"} and any(
        (week, month, quarter)
    ):
        raise DiaryError(f"{action} does not accept an audit period identifier")
    if kind == "personal" and action == "replace-date":
        return "user_confirmation"
    if kind == "personal" and action == "replace-personal-diary":
        return "personal_diary_request_gate"
    if kind == "personal" and action in {
        "replace-weekly-audit",
        "replace-monthly-audit",
        "replace-quarterly-audit",
    }:
        return _audit_spec(day, action, week, month, quarter)[3]
    raise DiaryError(
        f"unauthorized diary operation matrix: kind={kind}, action={action}, "
        f"week={week}, month={month}, quarter={quarter}"
    )


def _read_target(path: Path) -> tuple[bytes, str, str, bool]:
    if not path.exists():
        return b"", "", "\n", False
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    body = raw[3:] if bom else raw
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DiaryError(f"target is not valid UTF-8: {exc}") from exc
    if text.strip() and not DATE_HEADING.search(text):
        raise DiaryError("non-empty canonical target has no recognizable date heading")
    newline = "\r\n" if b"\r\n" in body else "\n"
    return raw, text, newline, bom


def _read_payload_source(path: Path) -> tuple[bytes, str]:
    source = path.read_bytes()
    try:
        text = source.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DiaryError(f"payload is not valid UTF-8: {exc}") from exc
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not normalized:
        raise DiaryError("payload is empty")
    return source, normalized


def _validate_personal_diary_payload(text: str, day: date) -> None:
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    h1 = MARKDOWN_ATX_H1.findall(text)
    h2_matches = list(MARKDOWN_ATX_H2.finditer(text))
    h2 = [match.group(0).strip() for match in h2_matches]
    if (
        not first_line.startswith(f"# {day.isoformat()}")
        or len(h1) != 1
        or MARKDOWN_SETEXT.search(text)
        or h2 != list(PERSONAL_DIARY_H2)
    ):
        raise DiaryError(
            "canonical personal diary payload must contain its date H1 and the "
            "eight required H2 sections in order, with no other H1/H2 or Setext headings"
        )
    for index, match in enumerate(h2_matches):
        end = (
            h2_matches[index + 1].start() if index + 1 < len(h2_matches) else len(text)
        )
        if not text[match.end() : end].strip():
            raise DiaryError("canonical personal diary sections must not be empty")


def _read_payload(
    path: Path,
    day: date,
    newline: str,
    action: str,
    week: str | None,
    month: str | None,
    quarter: str | None,
) -> tuple[bytes, bytes, str]:
    source, text = _read_payload_source(path)
    if action in {"replace-date", "replace-personal-diary"}:
        headings = DATE_HEADING.findall(text)
        if headings != [day.isoformat()]:
            raise DiaryError(
                "date payload must contain exactly one top-level heading for the requested date"
            )
        if action == "replace-personal-diary":
            _validate_personal_diary_payload(text, day)
    elif action in {
        "replace-weekly-audit",
        "replace-monthly-audit",
        "replace-quarterly-audit",
    }:
        label, period_id, _, _ = _audit_spec(day, action, week, month, quarter)
        with _immutable_gate_snapshot(source, ".md") as snapshot:
            _run_gate(
                [
                    sys.executable,
                    str(PERIODIC_TOPOLOGY),
                    str(snapshot),
                    "--period-type",
                    label,
                    "--period-id",
                    period_id,
                ],
                f"{label} audit topology gate",
            )
    else:
        raise DiaryError(f"unsupported action: {action}")
    rendered = text.replace("\n", newline)
    return source, rendered.encode("utf-8"), rendered


def _date_span(text: str, day: date) -> tuple[int, int] | None:
    matches = list(DATE_HEADING.finditer(text))
    requested = [item for item in matches if item.group(1) == day.isoformat()]
    if len(requested) > 1:
        raise DiaryError("target contains duplicate headings for the requested date")
    if not requested:
        return None
    current = requested[0]
    following = [item for item in matches if item.start() > current.start()]
    return current.start(), following[0].start() if following else len(text)


def _audit_span(
    block: str,
    heading: re.Pattern[str],
    period_id: str,
    label: str,
) -> tuple[int, int] | None:
    matches = [item for item in heading.finditer(block) if item.group(1) == period_id]
    if len(matches) > 1:
        raise DiaryError(f"target date block contains duplicate {label} audit headings")
    if not matches:
        return None
    current = matches[0]
    following = [
        item for item in H2_HEADING.finditer(block) if item.start() > current.start()
    ]
    return current.start(), following[0].start() if following else len(block)


def _protected_audit_content(
    block: str,
    heading: re.Pattern[str],
    period_id: str,
    label: str,
) -> str:
    span = _audit_span(block, heading, period_id, label)
    if span is None:
        return block.rstrip("\r\n")
    start, end = span
    return (block[:start] + block[end:].lstrip("\r\n")).rstrip("\r\n")


def _render_date(text: str, payload: str, day: date, newline: str) -> str:
    block = payload.rstrip("\r\n")
    span = _date_span(text, day)
    if span is not None:
        start, end = span
        suffix = text[end:]
        separator = newline * 2 if suffix else newline
        return text[:start] + block + separator + suffix.lstrip("\r\n")
    first = DATE_HEADING.search(text)
    if first:
        return text[: first.start()] + block + newline * 2 + text[first.start() :]
    if text.strip():
        raise DiaryError("cannot insert into a non-empty target without date headings")
    return block + newline


def _render_audit(
    text: str,
    payload: str,
    day: date,
    action: str,
    week: str | None,
    month: str | None,
    quarter: str | None,
    newline: str,
) -> tuple[str, str]:
    label, period_id, heading, _ = _audit_spec(day, action, week, month, quarter)
    span = _date_span(text, day)
    payload_block = payload.rstrip("\r\n")
    if span is None:
        date_block = f"# {day.isoformat()}" + newline * 2 + payload_block + newline
        first = DATE_HEADING.search(text)
        if first:
            rendered = (
                text[: first.start()] + date_block + newline + text[first.start() :]
            )
        elif text.strip():
            raise DiaryError(
                "cannot insert into a non-empty target without date headings"
            )
        else:
            rendered = date_block
        return rendered, _sha256(b"")
    start, end = span
    date_block = text[start:end]
    protected_before = _protected_audit_content(date_block, heading, period_id, label)
    audit = _audit_span(date_block, heading, period_id, label)
    if audit is None:
        updated_block = (
            date_block.rstrip("\r\n") + newline * 2 + payload_block + newline
        )
    else:
        audit_start, audit_end = audit
        suffix = date_block[audit_end:]
        separator = newline * 2 if suffix else newline
        updated_block = (
            date_block[:audit_start] + payload_block + separator + suffix.lstrip("\r\n")
        )
    if (
        _protected_audit_content(updated_block, heading, period_id, label)
        != protected_before
    ):
        raise DiaryError(f"{label} audit mutation would alter protected diary content")
    return text[:start] + updated_block + text[end:], _sha256(
        protected_before.encode("utf-8")
    )


def _personal_diary_parts(block: str, day: date) -> tuple[str, list[str]]:
    """Separate diary-owned text from validated, opaque periodic H2 blocks."""
    headings = list(MARKDOWN_ATX_H2.finditer(block))
    diary = block[: headings[0].start()] if headings else block
    audits: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(block)
        section = block[heading.start() : end]
        title = heading.group(0).rstrip("\r\n")
        if title in PERSONAL_DIARY_H2:
            diary += section
            continue
        for label, pattern in (
            ("weekly", WEEKLY_HEADING),
            ("monthly", MONTHLY_HEADING),
            ("quarterly", QUARTERLY_HEADING),
        ):
            match = pattern.fullmatch(title)
            if match:
                period = match.group(1)
                key = (label, period)
                if key in seen:
                    raise DiaryError("duplicate periodic audit block")
                seen.add(key)
                _audit_spec(
                    day,
                    f"replace-{label}-audit",
                    period if label == "weekly" else None,
                    period if label == "monthly" else None,
                    period if label == "quarterly" else None,
                )
                if MARKDOWN_ATX_H1.search(section) or MARKDOWN_SETEXT.search(section):
                    raise DiaryError("illegal periodic audit topology")
                audits.append(section)
                break
        else:
            raise DiaryError("unrecognized or illegal periodic H2 block")
    return diary.rstrip("\r\n"), audits


def _render_personal_diary(
    text: str, payload: str, day: date, newline: str
) -> tuple[str, str]:
    _validate_personal_diary_payload(payload, day)
    span = _date_span(text, day)
    audits = _personal_diary_parts(text[span[0] : span[1]], day)[1] if span else []
    protected = "".join(audits)
    if span and audits:
        start, end = span
        updated = payload.rstrip("\r\n") + newline * 2 + protected
        rendered = text[:start] + updated + text[end:]
    else:
        rendered = _render_date(text, payload, day, newline)
    result_span = _date_span(rendered, day)
    assert result_span is not None
    diary, after = _personal_diary_parts(rendered[result_span[0] : result_span[1]], day)
    if diary != payload.rstrip("\r\n") or after != audits:
        raise DiaryError("personal diary render changed payload or protected audits")
    return rendered, _sha256(protected.encode("utf-8"))


def _render_operation(
    text: str,
    payload: str,
    day: date,
    action: str,
    week: str | None,
    month: str | None,
    quarter: str | None,
    newline: str,
) -> tuple[str, str | None]:
    if action == "replace-date":
        return _render_date(text, payload, day, newline), None
    if action == "replace-personal-diary":
        return _render_personal_diary(text, payload, day, newline)
    if action in {
        "replace-weekly-audit",
        "replace-monthly-audit",
        "replace-quarterly-audit",
    }:
        return _render_audit(text, payload, day, action, week, month, quarter, newline)
    raise DiaryError(f"unsupported action: {action}")


def _scope_fields(
    target: Path,
    day: date,
    kind: str,
    action: str,
    week: str | None,
    month: str | None,
    quarter: str | None,
    authorization_id: str,
    scope_nonce: str,
    target_sha256: str,
    source_sha256: str,
    payload_sha256: str,
    protected_sha256: str | None,
) -> dict[str, Any]:
    return {
        "action": action,
        "authorization_id": authorization_id,
        "scope_nonce": scope_nonce,
        "date": day.isoformat(),
        "kind": kind,
        "week": week,
        "month": month,
        "quarter": quarter,
        "payload_sha256": payload_sha256,
        "source_sha256": source_sha256,
        "target": _normalized_path(target),
        "target_sha256_before": target_sha256,
        "protected_content_sha256_before": protected_sha256,
    }


def build_scope(args: argparse.Namespace) -> dict[str, Any]:
    day = date.fromisoformat(args.date)
    target = Path(args.file)
    _validate_matrix(day, args.kind, args.action, args.week, args.month, args.quarter)
    _validate_target(target, day, args.kind)
    target_raw, target_text, newline, _ = _read_target(target)
    source_raw, payload_raw, payload_text = _read_payload(
        Path(args.content_file),
        day,
        newline,
        args.action,
        args.week,
        args.month,
        args.quarter,
    )
    _, protected_sha = _render_operation(
        target_text,
        payload_text,
        day,
        args.action,
        args.week,
        args.month,
        args.quarter,
        newline,
    )
    scope_nonce = getattr(args, "scope_nonce", None) or secrets.token_hex(16)
    if not isinstance(scope_nonce, str) or not re.fullmatch(
        r"[0-9a-f]{32}", scope_nonce
    ):
        raise DiaryError("scope nonce must be 128-bit lowercase hex")
    fields = _scope_fields(
        target,
        day,
        args.kind,
        args.action,
        args.week,
        args.month,
        args.quarter,
        args.authorization_id,
        scope_nonce,
        _sha256(target_raw),
        _sha256(source_raw),
        _sha256(payload_raw),
        protected_sha,
    )
    scope_sha = _sha256(_canonical_json(fields))
    return {
        "schema": "diary-write-scope-v1",
        "event_type": "approval_request",
        "status": "awaiting_confirmation",
        **fields,
        "authorization_scope_sha256": scope_sha,
        "write_scope_sha256": scope_sha,
    }


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiaryError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise DiaryError(f"{label} must be a JSON object")
    return value


def _load_scope(path: Path) -> dict[str, Any]:
    value = _load_json(path, "scope receipt")
    if value.get("schema") != "diary-write-scope-v1":
        raise DiaryError("scope receipt schema mismatch")
    if value.get("status") != "awaiting_confirmation":
        raise DiaryError("scope receipt is not awaiting confirmation")
    return value


def _message_text(message: dict[str, Any], *, preserve_whitespace: bool = False) -> str:
    content = message.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    else:
        return ""
    return text if preserve_whitespace else text.strip()


def _protected_user_event(
    event_id: Any, *, preserve_whitespace: bool = False
) -> tuple[dict[str, Any], str]:
    if not isinstance(event_id, str) or not event_id.strip():
        raise DiaryError("protected user event id is required")
    session_value = os.environ.get("PI_SESSION_FILE")
    if not session_value:
        raise DiaryError("PI_SESSION_FILE is required for protected request evidence")
    session = Path(session_value).resolve()
    try:
        session.relative_to(SESSION_ROOT.resolve())
    except ValueError as exc:
        raise DiaryError(
            "session evidence is outside the protected Pi session root"
        ) from exc
    try:
        lines = session.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise DiaryError(f"unable to read protected session evidence: {exc}") from exc
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("id") != event_id or event.get("type") != "message":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "user":
            break
        text = _message_text(message, preserve_whitespace=preserve_whitespace)
        if not text:
            break
        return event, text
    raise DiaryError("protected user request event was not found")


def _verify_user_confirmation(value: dict[str, Any], receipt: dict[str, Any]) -> None:
    _, text = _protected_user_event(value.get("approval_evidence_id"))
    scope_hash = receipt.get("authorization_scope_sha256")
    expected_texts = {f"{prefix} {scope_hash}" for prefix in CONFIRMATION_PREFIXES}
    if text not in expected_texts:
        raise DiaryError("session confirmation is not bound to this write scope")


def _local_day_at_event(event: dict[str, Any], label: str) -> date:
    timestamp = event.get("timestamp")
    if not isinstance(timestamp, str):
        raise DiaryError(f"{label} request event timestamp is required")
    try:
        instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DiaryError(f"{label} request event timestamp is invalid") from exc
    if instant.tzinfo is None:
        raise DiaryError(f"{label} request event timestamp must include a timezone")
    return instant.astimezone(ZoneInfo("Asia/Shanghai")).date()


def _period_id_at_event(event: dict[str, Any], label: str) -> str:
    local_day = _local_day_at_event(event, "periodic")
    if label == "weekly":
        iso_year, iso_week, _ = local_day.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if label == "monthly":
        return f"{local_day.year}-{local_day.month:02d}"
    if label == "quarterly":
        return f"{local_day.year}-Q{_quarter(local_day)}"
    raise DiaryError(f"unsupported periodic request type: {label}")


def _explicit_date_in_text(text: str, default_year: int) -> date | None:
    match = re.search(r'(?:(\d{4})[年\.\-/])?(\d{1,2})[月\.\-/](\d{1,2})日?', text)
    if match:
        year = int(match.group(1)) if match.group(1) else default_year
        month = int(match.group(2))
        day = int(match.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None
    iso_match = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', text)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            return None
    return None


def _is_personal_diary_autosave_authorized(text: str) -> bool:
    normalized = text.strip()
    for prefix in ("[OVERRIDE]", "[WARROOM]"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break
    if normalized.startswith(("[OVERRIDE]", "[WARROOM]")):
        return False
    if any(kw in normalized for kw in PERSONAL_DIARY_AUTOSAVE_DENY_KEYWORDS):
        return False
    # A read/explanation request can mention saving without authorizing it.
    if re.match(
        r"^(?:(?:请你|请|帮我|麻烦你|麻烦)\s*)*(?:查看|分析|解释|阅读|查询|审阅|总结|检查)",
        normalized,
    ):
        return False
    if any(normalized.startswith(p) for p in PERSONAL_DIARY_VALID_PREFIXES):
        return True
    if ("个人日志" in normalized or "个人日记" in normalized) and any(
        act in normalized
        for act in ("更新", "生成", "记录", "写", "保存", "修改", "补写", "录入")
    ):
        return True
    return False


def _verify_personal_diary_request(
    value: dict[str, Any], receipt: dict[str, Any], args: argparse.Namespace
) -> None:
    expected = {
        "request_artifact_schema": "personal-diary-request-v1",
        "request_diary_date": args.date,
        "request_kind": "personal",
        "request_action": "replace-personal-diary",
        "request_target": receipt.get("target"),
        "request_scope_sha256": receipt.get("authorization_scope_sha256"),
        "request_save_policy": "canonical_autosave",
        "diary_payload_sha256": receipt.get("source_sha256"),
        "approval_evidence_id": receipt.get("source_sha256"),
    }
    if any(value.get(key) != item for key, item in expected.items()):
        raise DiaryError(
            "personal diary request artifact is not bound to the write scope"
        )
    event, text = _protected_user_event(
        value.get("request_event_id"), preserve_whitespace=True
    )
    if value.get("request_event_sha256") != _sha256(text.encode("utf-8")):
        raise DiaryError(
            "personal diary request artifact is not bound to the user event"
        )
    if not _is_personal_diary_autosave_authorized(text):
        raise DiaryError(
            "personal diary autosave requires an authorized personal diary request; "
            "draft, preview, read-only, or meta/management requests are not writable"
        )
    event_day = _local_day_at_event(event, "personal diary")
    explicit_day = _explicit_date_in_text(text, event_day.year)
    effective_day = explicit_day if explicit_day is not None else event_day
    if effective_day != date.fromisoformat(args.date):
        raise DiaryError("personal diary request date does not match the write date")
    try:
        source = Path(args.content_file).read_bytes()
    except OSError as exc:
        raise DiaryError(f"unable to read personal diary payload: {exc}") from exc
    if _sha256(source) != receipt.get("source_sha256"):
        raise DiaryError("personal diary payload changed after scope")
    with _immutable_gate_snapshot(source, ".md") as snapshot:
        _run_gate(
            [
                sys.executable,
                str(WEEKLY_GATE),
                str(snapshot),
                "--enforce-template-fields",
            ],
            "personal diary content gate",
        )


def _verify_periodic_request(
    value: dict[str, Any], receipt: dict[str, Any], args: argparse.Namespace
) -> None:
    day = date.fromisoformat(args.date)
    label, period_id, _, _ = _audit_spec(
        day, args.action, args.week, args.month, args.quarter
    )
    expected = {
        "request_artifact_schema": "periodic-audit-request-v1",
        "request_period_type": label,
        "request_period_id": period_id,
        "request_action": args.action,
        "request_target": receipt.get("target"),
        "request_scope_sha256": receipt.get("authorization_scope_sha256"),
        "request_save_policy": "canonical_autosave",
    }
    if any(value.get(key) != item for key, item in expected.items()):
        raise DiaryError("periodic request artifact is not bound to the write scope")
    event, text = _protected_user_event(value.get("request_event_id"))
    if value.get("request_event_sha256") != _sha256(text.encode("utf-8")):
        raise DiaryError("periodic request artifact is not bound to the user event")
    # Match one transport marker without changing the protected event/hash.
    # No recursive stripping, prose extraction, or substring authorization.
    normalized = text
    for marker in ("【微信消息】\r\n", "【微信消息】\n"):
        if normalized.startswith(marker):
            normalized = normalized[len(marker):]
            break
    for prefix in ("[OVERRIDE]", "[WARROOM]"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break
    structured = "AUDIT_AUTOSAVE " + json.dumps(
        {
            "period_id": period_id,
            "period_type": label,
            "save_policy": "canonical_autosave",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    aliases = {
        "weekly": {
            "本周个人日志审计",
            "个人日志周审计",
            "本周日志审计",
            "周度日志审计",
            "日志周审计",
        },
        "monthly": {
            "本月个人日志审计",
            "个人日志月度审计",
            "本月日志审计",
            "月度日志审计",
            "日志月度审计",
        },
        "quarterly": {
            "本季度个人日志审计",
            "个人日志季度审计",
            "本季度日志审计",
            "本季日志审计",
            "季度日志审计",
            "日志季度审计",
        },
    }
    if normalized == structured:
        return
    if normalized in aliases[label] and _period_id_at_event(event, label) == period_id:
        return
    raise DiaryError(
        "periodic autosave requires an exact canonical audit request; "
        "draft, preview, read-only, or modified requests are not writable"
    )


def _run_gate(command: list[str], label: str) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise DiaryError(f"{label} could not run: {exc}") from exc
    if completed.returncode != 0:
        raise DiaryError(f"{label} did not pass")
    return completed.stdout.strip()


@contextmanager
def _immutable_gate_snapshot(data: bytes, suffix: str) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="diary-gate-") as directory:
        snapshot = Path(directory) / f"input{suffix}"
        with open(snapshot, "xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            snapshot.chmod(0o400)
        except OSError:
            pass
        yield snapshot




def _verify_audit_gate(value: dict[str, Any], args: argparse.Namespace) -> None:
    label, period_id, _, _ = _audit_spec(
        date.fromisoformat(args.date),
        args.action,
        args.week,
        args.month,
        args.quarter,
    )
    if value.get("approval_evidence_id") != value.get("audit_payload_sha256"):
        raise DiaryError(f"{label} audit approval evidence is not bound")
    try:
        payload_bytes = Path(args.content_file).read_bytes()
    except OSError as exc:
        raise DiaryError(f"unable to read {label} audit payload: {exc}") from exc
    if value.get("audit_payload_sha256") != _sha256(payload_bytes):
        raise DiaryError(f"{label} audit approval is not bound to the payload")
    with _immutable_gate_snapshot(payload_bytes, ".md") as snapshot:
        _run_gate(
            [
                sys.executable,
                str(WEEKLY_GATE),
                str(snapshot),
                "--enforce-template-fields",
                "--period-type",
                label,
                "--period-id",
                period_id,
            ],
            f"{label} audit gate",
        )


def _load_approval(
    path: Path, receipt: dict[str, Any], args: argparse.Namespace
) -> dict[str, Any]:
    value = _load_json(path, "approval artifact")
    if value.get("schema") != "diary-write-approval-v1":
        raise DiaryError("approval artifact schema mismatch")
    if value.get("status") != "confirmed":
        raise DiaryError("approval artifact is not confirmed")
    expected_source = _validate_matrix(
        date.fromisoformat(args.date),
        args.kind,
        args.action,
        args.week,
        args.month,
        args.quarter,
    )
    if value.get("approval_source") != expected_source:
        raise DiaryError("approval source does not match the diary operation matrix")
    if (
        not isinstance(value.get("approval_evidence_id"), str)
        or not value["approval_evidence_id"].strip()
    ):
        raise DiaryError("approval evidence id is required")
    for key in ("authorization_id", "authorization_scope_sha256"):
        if value.get(key) != receipt.get(key):
            raise DiaryError("approval artifact is not bound to the scope receipt")
    if expected_source == "user_confirmation":
        _verify_user_confirmation(value, receipt)
    elif expected_source == "personal_diary_request_gate":
        _verify_personal_diary_request(value, receipt, args)
    else:
        _verify_periodic_request(value, receipt, args)
        _verify_audit_gate(value, args)
    return value


@contextmanager
def _exclusive_lock(target: Path) -> Iterator[None]:
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.with_name(target.name + ".lock")
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise DiaryError(f"diary target is locked: {lock}") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as handle:
            handle.write(str(os.getpid()) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _scope_args_from_replace(
    args: argparse.Namespace, receipt: dict[str, Any]
) -> argparse.Namespace:
    return argparse.Namespace(
        file=args.file,
        date=args.date,
        kind=args.kind,
        content_file=args.content_file,
        authorization_id=args.authorization_id,
        action=args.action,
        week=args.week,
        month=args.month,
        quarter=args.quarter,
        scope_nonce=receipt.get("scope_nonce"),
    )


def replace_operation(args: argparse.Namespace) -> dict[str, Any]:
    day = date.fromisoformat(args.date)
    target = Path(args.file)
    _validate_matrix(day, args.kind, args.action, args.week, args.month, args.quarter)
    _validate_target(target, day, args.kind)
    receipt = _load_scope(Path(args.scope_file))
    approval = _load_approval(Path(args.approval_file), receipt, args)
    with _exclusive_lock(target):
        current = build_scope(_scope_args_from_replace(args, receipt))
        bound = (
            "action",
            "authorization_id",
            "scope_nonce",
            "date",
            "kind",
            "week",
            "month",
            "quarter",
            "payload_sha256",
            "source_sha256",
            "target",
            "target_sha256_before",
            "protected_content_sha256_before",
            "authorization_scope_sha256",
        )
        if any(receipt.get(key) != current.get(key) for key in bound):
            raise DiaryError(
                "scope receipt does not match the current write payload or target"
            )

        target_raw, target_text, newline, bom = _read_target(target)
        _, payload_raw, payload_text = _read_payload(
            Path(args.content_file),
            day,
            newline,
            args.action,
            args.week,
            args.month,
            args.quarter,
        )
        if _sha256(target_raw) != receipt["target_sha256_before"]:
            raise DiaryError("target changed after scope creation")
        if _sha256(payload_raw) != receipt["payload_sha256"]:
            raise DiaryError("payload changed after scope creation")
        rendered, protected_sha = _render_operation(
            target_text,
            payload_text,
            day,
            args.action,
            args.week,
            args.month,
            args.quarter,
            newline,
        )
        if protected_sha != receipt.get("protected_content_sha256_before"):
            raise DiaryError("protected diary content changed after scope creation")

        day_count = sum(
            1 for item in DATE_HEADING.findall(rendered) if item == day.isoformat()
        )
        if day_count != 1:
            raise DiaryError(
                "render verification failed: date heading count is not one"
            )
        period_heading_count = None
        if args.action in {
            "replace-weekly-audit",
            "replace-monthly-audit",
            "replace-quarterly-audit",
        }:
            label, period_id, heading, _ = _audit_spec(
                day, args.action, args.week, args.month, args.quarter
            )
            period_heading_count = sum(
                1 for item in heading.findall(rendered) if item == period_id
            )
            if period_heading_count != 1:
                raise DiaryError(
                    f"render verification failed: {label} heading count is not one"
                )

        encoded = (b"\xef\xbb\xbf" if bom else b"") + rendered.encode("utf-8")
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb",
                dir=target.parent,
                prefix=target.name + ".",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, target)
            temporary = None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
        written = target.read_bytes()
        if written != encoded:
            raise DiaryError(
                "write verification failed: target bytes differ from render"
            )

    return {
        "schema_version": 2,
        "component": "diary_ops",
        "event_type": "write_commit",
        "status": "success",
        "action": receipt["action"],
        "approval_source": approval["approval_source"],
        "authorization_id": receipt["authorization_id"],
        "authorization_scope_sha256": receipt["authorization_scope_sha256"],
        "write_scope_sha256": receipt["authorization_scope_sha256"],
        "payload_sha256": receipt["payload_sha256"],
        "target_sha256_after": _sha256(written),
        "date_heading_count": day_count,
        "period_heading_count": period_heading_count,
        "target": receipt["target"],
    }


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--file", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--kind", choices=("personal",), required=True)
    parser.add_argument(
        "--action",
        choices=(
            "replace-date",
            "replace-personal-diary",
            "replace-weekly-audit",
            "replace-monthly-audit",
            "replace-quarterly-audit",
        ),
        required=True,
    )
    parser.add_argument("--week")
    parser.add_argument("--month")
    parser.add_argument("--quarter")
    parser.add_argument("--content-file", required=True)
    parser.add_argument("--authorization-id", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    scope = subparsers.add_parser("scope")
    _common_arguments(scope)
    scope.add_argument("--receipt-file")
    replace = subparsers.add_parser("replace")
    _common_arguments(replace)
    replace.add_argument("--scope-file", required=True)
    replace.add_argument("--approval-file", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "scope":
            result = build_scope(args)
            if args.receipt_file:
                _write_json_atomic(Path(args.receipt_file), result)
        else:
            result = replace_operation(args)
    except (DiaryError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": 2,
                    "component": "diary_ops",
                    "status": "failed",
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
