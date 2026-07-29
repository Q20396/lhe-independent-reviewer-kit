#!/usr/bin/env python3
"""Validate a static blocked handoff receipt without performing a handoff."""
import argparse,json,re
from pathlib import Path
F={"schema_version","receipt_id","workstream_envelope_sha256","from_agent","to_agent","context_sha256","evidence_refs","unresolved_risks","next_safe_action","client_authority_owner","execution_authorized","effect_summary"};A={"request_client_authorization","collect_evidence","stop"}
def ss(x):return isinstance(x,list) and bool(x) and all(isinstance(i,str) and i for i in x) and len(x)==len(set(x))
def validate(x):
 if not isinstance(x,dict) or set(x)!=F:return ["HANDOFF_FIELD_SET_INVALID"]
 if x.get("schema_version")!="1.0.0" or not isinstance(x.get("receipt_id"),str) or not re.fullmatch(r"SHR-[A-Z0-9-]+",x["receipt_id"]):return ["HANDOFF_IDENTITY_INVALID"]
 for name in ("workstream_envelope_sha256","context_sha256"):
  if not isinstance(x.get(name),str) or not re.fullmatch(r"[0-9a-f]{64}",x[name]):return ["HANDOFF_IDENTITY_INVALID"]
 if not all(isinstance(x.get(name),str) and x[name] for name in ("from_agent","to_agent")) or not ss(x.get("evidence_refs")) or not ss(x.get("unresolved_risks")) or not isinstance(x.get("next_safe_action"),str) or x["next_safe_action"] not in A:return ["HANDOFF_EVIDENCE_INVALID"]
 if x.get("client_authority_owner")!="client" or x.get("execution_authorized") is not False:return ["HANDOFF_AUTHORITY_ESCALATION"]
 return [] if x.get("effect_summary")==[] else ["HANDOFF_EFFECT_FORBIDDEN"]
def main():
 p=argparse.ArgumentParser();p.add_argument("--receipt",type=Path,required=True);a=p.parse_args()
 try:x=json.loads(a.receipt.read_text(encoding="utf-8"))
 except (OSError,UnicodeDecodeError,json.JSONDecodeError):print(json.dumps({"status":"FAIL","reasons":["INPUT_DOCUMENT_INVALID"]}));return 1
 r=validate(x);print(json.dumps({"status":"PASS" if not r else "FAIL","reasons":r},sort_keys=True));return 0 if not r else 1
if __name__=="__main__":raise SystemExit(main())
