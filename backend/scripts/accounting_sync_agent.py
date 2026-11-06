"""Run beside TallyPrime. Secrets come from environment, never command arguments."""
import argparse
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from app.shared.accounting_sync.tally import TallyReader

class AgentSession:
    def __init__(self,base,access_token,refresh_token,bridge_token,branch,tenant=None,organization=None):
        self.base=base;self.access=access_token;self.refresh=refresh_token
        self.headers={"X-Suite-Branch":str(branch),"X-Accounting-Bridge-Token":bridge_token}
        if tenant:self.headers["X-Suite-Tenant"]=tenant
        if organization:self.headers["X-Suite-Organization"]=str(organization)
    def renew(self,client):
        if not self.refresh:raise RuntimeError("Authorized session expired; configure a renewable agent session")
        response=client.post(self.base+"/api/v1/auth/refresh",json={"refresh_token":self.refresh},headers={k:v for k,v in self.headers.items() if k in {"X-Suite-Tenant","X-Suite-Organization"}})
        if response.status_code!=200:raise RuntimeError("Agent session revoked or expired; reconnect the agent")
        data=response.json();self.access=data["access_token"];self.refresh=data["refresh_token"]
    def upload(self,client,connection,snapshot):
        if not self.access:self.renew(client)
        url=self.base+"/api/v1/accounting-sync/connections/"+connection+"/snapshot"
        response=client.post(url,headers={**self.headers,"Authorization":"Bearer "+self.access},json=snapshot)
        if response.status_code==401:
            self.renew(client)
            response=client.post(url,headers={**self.headers,"Authorization":"Bearer "+self.access},json=snapshot)
        if response.status_code>=400:raise RuntimeError("Snapshot upload rejected (HTTP "+str(response.status_code)+"); check session, branch and bridge authorization")
        data=response.json()
        if data.get("status")!="completed":raise RuntimeError("Tally snapshot was not published; check sync history")
        return data

def run_cycle(reader,session,connection):
    snapshot=reader.snapshot()
    with httpx.Client(timeout=120,follow_redirects=False,trust_env=False) as client:
        return session.upload(client,connection,snapshot)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company",required=True)
    parser.add_argument("--company-guid",required=True)
    parser.add_argument("--currency",required=True)
    parser.add_argument("--connection",required=True)
    parser.add_argument("--branch",required=True,type=int)
    parser.add_argument("--organization",type=int)
    parser.add_argument("--port",type=int,default=9000)
    parser.add_argument("--watch",action="store_true",help="Repeat read-only exports in the background")
    parser.add_argument("--interval-seconds",type=int,default=900)
    args=parser.parse_args()
    if not 300<=args.interval_seconds<=86400:parser.error("Interval must be between 300 and 86400 seconds")
    base=os.environ["BUSINESSSUITE_URL"].rstrip("/")
    parsed=urlsplit(base)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        parser.error("BUSINESSSUITE_URL must be an HTTPS origin")
    try:UUID(args.connection)
    except ValueError:parser.error("Connection must be a UUID")
    session=AgentSession(base,os.environ.get("BUSINESSSUITE_ACCESS_TOKEN", ""),os.environ.get("BUSINESSSUITE_REFRESH_TOKEN", ""),os.environ["BUSINESSSUITE_BRIDGE_TOKEN"],args.branch,os.environ.get("BUSINESSSUITE_TENANT"),args.organization)
    reader=TallyReader(args.company,args.company_guid,args.currency,args.port)
    failures=0
    try:
        while True:
            try:
                run_cycle(reader,session,args.connection);failures=0;print("Sync completed",flush=True)
            except Exception:
                failures+=1;print("Sync failed; previous snapshot retained. Check server history, local Tally and session configuration.",file=sys.stderr,flush=True)
                if not args.watch:return 1
            if not args.watch:return 0
            time.sleep(min(21600,args.interval_seconds*2**min(failures,5)))
    except KeyboardInterrupt:return 0

if __name__=="__main__":raise SystemExit(main())
