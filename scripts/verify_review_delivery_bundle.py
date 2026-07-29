#!/usr/bin/env python3
import argparse,json,re
from pathlib import Path
F={"schema_version","bundle_id","target_commit","target_identity_manifest_sha256","status","findings","evidence_refs","limitations","recommendations","human_disposition","next_stage_authorized"};R={"collect_evidence","draft_lhe_proposal","request_human_decision"}
def ss(x):return isinstance(x,list) and bool(x) and all(isinstance(i,str) and i for i in x) and len(x)==len(set(x))
def v(x,expected=None,expected_identity_manifest_sha256=None):
 if not isinstance(x,dict) or set(x)!=F:return ["BUNDLE_FIELD_SET_INVALID"]
 if x.get("schema_version")!="1.0.0" or not isinstance(x.get("bundle_id"),str) or not re.fullmatch(r"BUNDLE-[A-Z0-9-]+",x["bundle_id"]) or not isinstance(x.get("target_commit"),str) or not re.fullmatch(r"[0-9a-f]{40}",x["target_commit"]) or not isinstance(x.get("target_identity_manifest_sha256"),str) or not re.fullmatch(r"[0-9a-f]{64}",x["target_identity_manifest_sha256"]) or not isinstance(x.get("status"),str) or x["status"] not in {"blocked","unverified","requires_human_decision"}:return ["BUNDLE_IDENTITY_INVALID"]
 if expected is not None and x["target_commit"]!=expected:return ["BUNDLE_TARGET_MISMATCH"]
 if expected_identity_manifest_sha256 is not None and x["target_identity_manifest_sha256"]!=expected_identity_manifest_sha256:return ["BUNDLE_TARGET_IDENTITY_MISMATCH"]
 if not ss(x.get("findings")) or not ss(x.get("evidence_refs")) or not ss(x.get("limitations")) or not ss(x.get("recommendations")) or any(i not in R for i in x["recommendations"]):return ["BUNDLE_EVIDENCE_INVALID"]
 return [] if x.get("human_disposition")=="pending" and x.get("next_stage_authorized") is False else ["BUNDLE_AUTHORITY_ESCALATION"]
def main():
 p=argparse.ArgumentParser();p.add_argument("--bundle",type=Path,required=True);p.add_argument("--expected-target-commit",required=True);p.add_argument("--expected-target-identity-manifest-sha256",required=True);a=p.parse_args()
 try:x=json.loads(a.bundle.read_text())
 except Exception:print('{"reasons":["INPUT_DOCUMENT_INVALID"],"status":"FAIL"}');return 1
 r=v(x,a.expected_target_commit,a.expected_target_identity_manifest_sha256);print(json.dumps({"status":"PASS" if not r else "FAIL","reasons":r}));return 0 if not r else 1
if __name__=="__main__":raise SystemExit(main())
