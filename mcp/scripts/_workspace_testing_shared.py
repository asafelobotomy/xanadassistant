from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_test_summary(text: str) -> dict:
    summary = {"format": "unknown", "passed": 0, "failed": 0, "errors": 0, "total": 0, "firstFailure": None}
    if not text:
        return summary
    pytest_counts = re.findall(r"(\d+)\s+(passed|failed|errors?|skipped)", text, re.IGNORECASE)
    if pytest_counts:
        summary["format"] = "pytest"
        skipped = 0
        for raw_count, label in pytest_counts:
            count = int(raw_count)
            label_lower = label.lower()
            if label_lower == "passed":
                summary["passed"] += count
            elif label_lower == "failed":
                summary["failed"] += count
            elif label_lower in {"error", "errors"}:
                summary["errors"] += count
            elif label_lower == "skipped":
                skipped += count
        summary["total"] = summary["passed"] + summary["failed"] + summary["errors"] + skipped
        if failed_match := re.search(r"^FAILED\s+(.+?)\s+-\s+(.+)$", text, re.MULTILINE):
            summary["firstFailure"] = f"{failed_match.group(1)}: {failed_match.group(2)}"
        return summary
    if ran_match := re.search(r"Ran\s+(\d+)\s+tests", text, re.IGNORECASE):
        summary["format"] = "unittest"
        summary["total"] = int(ran_match.group(1))
        result_match = re.search(r"^(OK|FAILED)\s*(?:\((.+)\))?$", text, re.MULTILINE)
        if result_match and result_match.group(1) == "OK":
            summary["passed"] = summary["total"]
        elif result_match:
            for part in (result_match.group(2) or "").split(","):
                key, _, value = part.strip().partition("=")
                if key == "failures" and value.isdigit():
                    summary["failed"] = int(value)
                elif key == "errors" and value.isdigit():
                    summary["errors"] = int(value)
            summary["passed"] = max(0, summary["total"] - summary["failed"] - summary["errors"])
        if failed_match := re.search(r"^(?:FAIL|ERROR):\s+(\S+)", text, re.MULTILINE):
            summary["firstFailure"] = failed_match.group(1)
    return summary


def parse_coverage_xml_file(path: Path) -> dict:
    root = ET.parse(str(path)).getroot()
    line_rate = float(root.get("line-rate", 0.0))
    lines_valid = int(root.get("lines-valid", 0))
    lines_covered = int(root.get("lines-covered", 0))
    zero_coverage_files = [
        item.get("filename", "unknown")
        for item in root.iter("class")
        if float(item.get("line-rate", 1.0)) == 0.0
    ][:20]
    return {
        "lineRate": round(line_rate, 4),
        "percentCovered": round(line_rate * 100, 1),
        "linesValid": lines_valid,
        "linesCovered": lines_covered,
        "zeroCoverageFiles": zero_coverage_files,
    }
