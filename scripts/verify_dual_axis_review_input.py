#!/usr/bin/env python3
"""Validate static, non-authorizing input for independent dual-axis review."""
import argparse
import json
import re
from pathlib import Path

FIELDS = {"schema_version", "input_id", "review_request_id", "target_candidate_commit", "axes", "requested_checks", "allowed_effects", "human_disposition", "promotion_state", "next_stage_authorized"}
AXIS_FIELDS = {"availability", "source"}
PROVIDED_SOURCE_FIELDS = {"kind", "locator", "bytes_sha256"}
UNAVAILABLE_SOURCE_FIELDS = {"kind", "locator"}
SOURCE_KINDS = {"issue", "pull-request", "repository-file", "external-document"}


def valid_sha256(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)


def valid_axis(value):
    if not isinstance(value, dict) or set(value) != AXIS_FIELDS:
        return False
    source = value.get("source")
    if not isinstance(availability := value.get("availability"), str) or availability not in {"provided", "not-available"} or not isinstance(source, dict):
        return False
    if availability == "not-available":
        return set(source) == UNAVAILABLE_SOURCE_FIELDS and source.get("kind") == "none" and isinstance(source.get("locator"), str) and bool(source["locator"])
    if set(source) != PROVIDED_SOURCE_FIELDS or not isinstance(source.get("kind"), str):
        return False
    if source["kind"] not in SOURCE_KINDS or not isinstance(source.get("locator"), str) or not source["locator"] or not valid_sha256(source.get("bytes_sha256")):
        return False
    return True


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        return ["DUAL_AXIS_FIELD_SET_INVALID"]
    if value.get("schema_version") != "1.0.0" or not isinstance(value.get("input_id"), str) or not re.fullmatch(r"DAI-[A-Z0-9-]+", value["input_id"]):
        return ["DUAL_AXIS_IDENTITY_INVALID"]
    if not isinstance(value.get("review_request_id"), str) or not re.fullmatch(r"IRR-[A-Z0-9-]+", value["review_request_id"]) or not isinstance(value.get("target_candidate_commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", value["target_candidate_commit"]):
        return ["DUAL_AXIS_REQUEST_BINDING_INVALID"]
    axes = value.get("axes")
    if not isinstance(axes, dict) or set(axes) != {"spec", "standards"}:
        return ["DUAL_AXIS_AXIS_SET_INVALID"]
    if not all(valid_axis(axes[name]) for name in ("spec", "standards")):
        return ["DUAL_AXIS_SOURCE_INVALID"]
    if value.get("requested_checks") != ["spec", "standards"]:
        return ["DUAL_AXIS_CHECK_SET_INVALID"]
    if value.get("allowed_effects") != []:
        return ["DUAL_AXIS_EFFECT_FORBIDDEN"]
    if value.get("human_disposition") != "pending" or value.get("promotion_state") != "not-promoted" or value.get("next_stage_authorized") is not False:
        return ["DUAL_AXIS_AUTHORITY_ESCALATION"]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print(json.dumps({"status": "FAIL", "reasons": ["INPUT_DOCUMENT_INVALID"]}))
        return 1
    reasons = validate(value)
    print(json.dumps({"status": "PASS" if not reasons else "FAIL", "reasons": reasons}, sort_keys=True))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
