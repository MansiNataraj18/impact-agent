import re
from dataclasses import dataclass

from impact_agent.models.common import UnresolvedItem
from impact_agent.models.parsed_tdd import ChangeAction, CodeCheck, ParsedChange
from impact_agent.parser.normalize import collapse
from impact_agent.parser.sections import SECTION_CHANGES, Section

# Changed-service heading, on one line or split as "name", blank line(s), "(complexity: x)".
SERVICE_RE = re.compile(r"^([a-z][a-z0-9-]*) \(complexity: (?:low|medium|high)\)$")
SERVICE_NAME_RE = re.compile(r"^([a-z][a-z0-9-]*)$")
COMPLEXITY_RE = re.compile(r"^\(complexity: (?:low|medium|high)\)$")
NO_CHANGE_RE = re.compile(r"^([a-z][a-z0-9-]*) [—–-] no change$")
CHANGE_HEADER_RE = re.compile(r"^Change (\d+): (\S+) \((modify|create|reference)\b.*\)$")
CHANGE_LIKE_RE = re.compile(r"^Change (\d+)")

LABEL_FILE = "File:"
LABEL_CODE_CHECK = "Code check:"
LABEL_CHANGE = "Change:"
LABEL_DONE_WHEN = "Done when:"
# Lines starting with one of these end the free text of the "Change:" field.
FIELD_LABELS = (
    LABEL_FILE,
    LABEL_CODE_CHECK,
    "Today:",
    LABEL_CHANGE,
    "How:",
    "Why:",
    "Sketch:",
    LABEL_DONE_WHEN,
    "Data model:",
)

REASON_SECTION_MISSING = f"Section '{SECTION_CHANGES}' not found"
REASON_HEADER = "Change header could not be parsed"
REASON_DUPLICATE = "Duplicate change number {n}"
REASON_NO_FILE = "No 'File:' value found"
REASON_NO_CODE_CHECK = "No valid 'Code check:' (VERIFIED or NEW) found"
REASON_NO_SUMMARY = "No 'Change:' text found"
REASON_NO_SERVICE = "No service heading precedes this change"
REASON_AFTER_NO_CHANGE = "This change follows a 'no change' service heading, not a changed service"
REASON_NO_DONE_WHEN = "No 'Done when:' list found"
REASON_NO_BOUNDARY = "No boundary found after the change block"


@dataclass(frozen=True)
class _Marker:
    kind: str  # "service", "no_change", "change", "bad_change"
    line: int
    name: str | None = None


def missing_section_item() -> UnresolvedItem:
    return UnresolvedItem(scope="section", field="changes", reason=REASON_SECTION_MISSING)


def _next_non_empty(norm: list[str], start: int, end: int) -> str | None:
    return next((norm[i] for i in range(start, end) if norm[i]), None)


def _find_markers(norm: list[str], section: Section) -> list[_Marker]:
    markers = []
    for index in range(section.body_start, section.end):
        line = norm[index]
        if match := SERVICE_RE.match(line):
            markers.append(_Marker("service", index, match.group(1)))
        elif SERVICE_NAME_RE.match(line) and COMPLEXITY_RE.match(
            _next_non_empty(norm, index + 1, section.end) or ""
        ):
            markers.append(_Marker("service", index, line))
        elif match := NO_CHANGE_RE.match(line):
            markers.append(_Marker("no_change", index, match.group(1)))
        elif CHANGE_HEADER_RE.match(line):
            markers.append(_Marker("change", index))
        elif CHANGE_LIKE_RE.match(line):
            markers.append(_Marker("bad_change", index))
    return markers


def _read_file(norm: list[str], start: int, end: int) -> str | None:
    for index in range(start, end):
        if norm[index].startswith(LABEL_FILE):
            value = norm[index][len(LABEL_FILE) :].strip()
            follow = index + 1
            while (
                value.endswith("/")
                and follow < end
                and norm[follow]
                and not any(ch.isspace() for ch in norm[follow])
            ):
                value += norm[follow]
                follow += 1
            return value or None
    return None


def _read_code_check(norm: list[str], start: int, end: int) -> CodeCheck | None:
    for index in range(start, end):
        if norm[index].startswith(LABEL_CODE_CHECK):
            tokens = norm[index][len(LABEL_CODE_CHECK) :].split()
            if tokens and tokens[0] in {check.value for check in CodeCheck}:
                return CodeCheck(tokens[0])
            return None
    return None


def _read_summary(norm: list[str], start: int, end: int) -> str | None:
    for index in range(start, end):
        if norm[index].startswith(LABEL_CHANGE):
            parts = [norm[index][len(LABEL_CHANGE) :]]
            for follow in range(index + 1, end):
                if norm[follow].startswith(FIELD_LABELS):
                    break
                parts.append(norm[follow])
            return collapse(" ".join(parts)) or None
    return None


def _has_done_when(norm: list[str], start: int, end: int) -> bool:
    return any(norm[index].startswith(LABEL_DONE_WHEN) for index in range(start, end))


def parse_changes(
    norm: list[str], section: Section, has_following_heading: bool
) -> tuple[list[ParsedChange], list[str], list[UnresolvedItem]]:
    markers = _find_markers(norm, section)
    changes: list[ParsedChange] = []
    no_change: list[str] = []
    unresolved: list[UnresolvedItem] = []
    seen_numbers: set[int] = set()
    service: str | None = None
    after_no_change = False

    for position, marker in enumerate(markers):
        if marker.kind == "service":
            service = marker.name
            after_no_change = False
            continue
        if marker.kind == "no_change":
            if marker.name not in no_change:
                no_change.append(marker.name)
            # Never guess: a change after a no-change heading must not inherit the earlier service.
            service = None
            after_no_change = True
            continue
        if marker.kind == "bad_change":
            number = int(CHANGE_LIKE_RE.match(norm[marker.line]).group(1))
            unresolved.append(
                UnresolvedItem(
                    scope="change", change_number=number, reason=REASON_HEADER, line=marker.line
                )
            )
            continue

        header = CHANGE_HEADER_RE.match(norm[marker.line])
        number = int(header.group(1))
        if number in seen_numbers:
            unresolved.append(
                UnresolvedItem(
                    scope="section",
                    reason=REASON_DUPLICATE.format(n=number),
                    line=marker.line,
                )
            )
            continue
        seen_numbers.add(number)

        if position + 1 < len(markers):
            boundary: int | None = markers[position + 1].line
        else:
            boundary = section.end if has_following_heading else None
        block_start = marker.line + 1
        block_end = boundary if boundary is not None else section.end

        file = _read_file(norm, block_start, block_end)
        code_check = _read_code_check(norm, block_start, block_end)
        summary = _read_summary(norm, block_start, block_end)
        insert_before = boundary if _has_done_when(norm, block_start, block_end) else None

        def missing(field: str, reason: str, number: int = number, line: int = marker.line):
            unresolved.append(
                UnresolvedItem(
                    scope="change", change_number=number, field=field, reason=reason, line=line
                )
            )

        if service is None:
            missing("service", REASON_AFTER_NO_CHANGE if after_no_change else REASON_NO_SERVICE)
        if file is None:
            missing("file", REASON_NO_FILE)
        if code_check is None:
            missing("code_check", REASON_NO_CODE_CHECK)
        if summary is None:
            missing("summary", REASON_NO_SUMMARY)
        if not _has_done_when(norm, block_start, block_end):
            missing("insert_before_line", REASON_NO_DONE_WHEN)
        elif boundary is None:
            missing("insert_before_line", REASON_NO_BOUNDARY)

        changes.append(
            ParsedChange(
                number=number,
                service=service,
                file=file,
                symbol=header.group(2),
                action=ChangeAction(header.group(3)),
                code_check=code_check,
                summary=summary,
                insert_before_line=insert_before,
            )
        )
    return changes, no_change, unresolved
