#!/usr/bin/env python3
"""Validate declared-disabled providers and diagnostic-only doctor responses."""
import argparse,json,re
from pathlib import Path
from typing import Any
PERMS={"git_object_read","artifact_read"}; MF={"schema_version","provider_id","kind","version","status","required_permissions","network_behavior","hook_behavior","persistence_behavior","execution_behavior","evidence_requirements","limitations","human_disposition","next_stage_authorized"}; DF={"schema_version","provider_id","status","reason_codes","observed_evidence","limitations","next_safe_action","human_disposition","next_stage_authorized"}
def strings(x:Any,nonempty=False): return isinstance(x,list) and (bool(x) if nonempty else True) and all(isinstance(i,str) and i for i in x) and len(x)==len(set(x))
def manifest(x:Any):
 if not isinstance(x,dict) or set(x)!=MF:return ["MANIFEST_FIELD_SET_INVALID"]
 if x.get("schema_version")!="1.0.0" or not isinstance(x.get("provider_id"),str) or not re.fullmatch(r"PROVIDER-[A-Z0-9-]+",x["provider_id"]) or not isinstance(x.get("kind"),str) or x["kind"] not in {"graph_provider","planning_provider","catalog_provider"} or not isinstance(x.get("version"),str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+",x["version"]):return ["MANIFEST_IDENTITY_INVALID"]
 if x.get("status")!="declared_disabled" or any(x.get(k)!="forbidden" for k in ("network_behavior","hook_behavior","persistence_behavior","execution_behavior")):return ["MANIFEST_EFFECT_ESCALATION"]
 if not strings(x.get("required_permissions")) or any(p not in PERMS for p in x["required_permissions"]) or not strings(x.get("evidence_requirements"),True) or not strings(x.get("limitations"),True):return ["MANIFEST_EVIDENCE_INVALID"]
 return [] if x.get("human_disposition")=="pending" and x.get("next_stage_authorized") is False else ["MANIFEST_AUTHORITY_ESCALATION"]
def doctor(x:Any,m:Any):
 if manifest(m):return ["MANIFEST_INVALID"]
 if not isinstance(x,dict) or set(x)!=DF:return ["DOCTOR_FIELD_SET_INVALID"]
 if x.get("schema_version")!="1.0.0" or x.get("provider_id")!=m["provider_id"] or not isinstance(x.get("status"),str) or x["status"] not in {"blocked","unverified","requires_human_decision"}:return ["DOCTOR_IDENTITY_INVALID"]
 if not strings(x.get("reason_codes"),True) or not strings(x.get("observed_evidence")) or not strings(x.get("limitations"),True) or not isinstance(x.get("next_safe_action"),str) or x["next_safe_action"] not in {"collect_static_evidence","request_human_decision","request_provider_intake"}:return ["DOCTOR_EVIDENCE_INVALID"]
 return [] if x.get("human_disposition")=="pending" and x.get("next_stage_authorized") is False else ["DOCTOR_AUTHORITY_ESCALATION"]
def main():
 p=argparse.ArgumentParser();p.add_argument("--manifest",type=Path,required=True);p.add_argument("--doctor",type=Path,required=True);a=p.parse_args()
 try:m=json.loads(a.manifest.read_text());d=json.loads(a.doctor.read_text())
 except (OSError,UnicodeDecodeError,json.JSONDecodeError):print('{"reasons":["INPUT_DOCUMENT_INVALID"],"status":"FAIL"}');return 1
 r=manifest(m) or doctor(d,m);print(json.dumps({"status":"PASS" if not r else "FAIL","reasons":r},sort_keys=True));return 0 if not r else 1
if __name__=="__main__":raise SystemExit(main())
