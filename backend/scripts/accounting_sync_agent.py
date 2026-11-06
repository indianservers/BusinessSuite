"""Run beside TallyPrime. Secrets come from environment, never command arguments."""
import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from app.shared.accounting_sync.tally import TallyReader

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company",required=True)
    parser.add_argument("--company-guid",required=True)
    parser.add_argument("--currency",required=True)
    parser.add_argument("--connection",required=True)
    parser.add_argument("--branch",required=True,type=int)
    parser.add_argument("--port",type=int,default=9000)
    args=parser.parse_args()
    base=os.environ["BUSINESSSUITE_URL"].rstrip("/")
    parsed=urlsplit(base)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        parser.error("BUSINESSSUITE_URL must be an HTTPS origin")
    from uuid import UUID
    try: UUID(args.connection)
    except ValueError: parser.error("Connection must be a UUID")
    snapshot=TallyReader(args.company,args.company_guid,args.currency,args.port).snapshot()
    headers={"Authorization":"Bearer "+os.environ["BUSINESSSUITE_ACCESS_TOKEN"],"X-Suite-Branch":str(args.branch),"X-Accounting-Bridge-Token":os.environ["BUSINESSSUITE_BRIDGE_TOKEN"]}
    with httpx.Client(timeout=120,follow_redirects=False,trust_env=False) as client:
        response=client.post(base+"/api/v1/accounting-sync/connections/"+args.connection+"/snapshot",headers=headers,json=snapshot)
        if response.status_code>=400: raise SystemExit("Snapshot upload rejected (HTTP "+str(response.status_code)+"); check session, branch and bridge authorization")
        result=response.json()
    print("Sync "+result["status"])
    if result["status"]!="completed": raise SystemExit(1)

if __name__=="__main__": main()
