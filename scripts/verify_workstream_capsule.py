#!/usr/bin/env python3
"""Validate a non-sensitive static workstream capsule without persisting or executing it."""
import argparse,json,re
from pathlib import Path
F={"schema_version","capsule_id","workflow_pack_sha256","spec_sha256","phase","evidence_refs","blockers","next_safe_action","persistence_requested","client_authority_owner","human_disposition","next_stage_authorized"};P={"planned","blocked","evidence_collected","requires_human_decision"};A={"collect_evidence","request_client_decision","stop"};B={"MISSING_EVIDENCE","TARGET_IDENTITY_UNVERIFIED","CLIENT_DECISION_REQUIRED","BUDGET_EXHAUSTED"}
def ss(x,nonempty=False):return isinstance(x,list) and (bool(x) if nonempty else True) and all(isinstance(i,str) and i for i in x) and len(x)==len(set(x))
def validate(x):
 if not isinstance(x,dict) or set(x)!=F:return ["CAPSULE_FIELD_SET_INVALID"]
 if x.get("schema_version")!="1.0.0" or not isinstance(x.get("capsule_id"),str) or not re.fullmatch(r"WSC-[A-Z0-9-]+",x["capsule_id"]):return ["CAPSULE_IDENTITY_INVALID"]
 for n in ("workflow_pack_sha256","spec_sha256"):
  if not isinstance(x.get(n),str) or not re.fullmatch(r"[0-9a-f]{64}",x[n]):return ["CAPSULE_IDENTITY_INVALID"]
 if not isinstance(x.get("phase"),str) or x["phase"] not in P or not ss(x.get("evidence_refs"),True) or any(not re.fullmatch(r"EVID-[A-Z0-9-]+",item) for item in x["evidence_refs"]) or not ss(x.get("blockers")) or any(item not in B for item in x["blockers"]) or not isinstance(x.get("next_safe_action"),str) or x["next_safe_action"] not in A:return ["CAPSULE_CONTENT_INVALID"]
 if x.get("persistence_requested") is not False:return ["CAPSULE_PERSISTENCE_FORBIDDEN"]
 if x.get("client_authority_owner")!="client" or x.get("human_disposition")!="pending" or x.get("next_stage_authorized") is not False:return ["CAPSULE_AUTHORITY_ESCALATION"]
 return []
def main():
 p=argparse.ArgumentParser();p.add_argument("--capsule",type=Path,required=True);a=p.parse_args()
 try:x=json.loads(a.capsule.read_text(encoding="utf-8"))
 except (OSError,UnicodeDecodeError,json.JSONDecodeError):print(json.dumps({"status":"FAIL","reasons":["INPUT_DOCUMENT_INVALID"]}));return 1
 r=validate(x);print(json.dumps({"status":"PASS" if not r else "FAIL","reasons":r},sort_keys=True));return 0 if not r else 1
if __name__=="__main__":raise SystemExit(main())
