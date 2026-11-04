"""Read-only QuickBooks/Zoho imports. OAuth never grants local posting authority."""
import json
import os
import secrets
import time
from urllib.parse import urlencode
from uuid import uuid4
import httpx
from fastapi import HTTPException
from app.ai_operator.providers import cipher
from app.shared.import_models import ImportConnection

REGIONS = {"com", "in", "eu", "com.au", "jp", "ca", "sa"}
PROVIDERS = {"quickbooks": "QuickBooks Online", "zoho": "Zoho Books"}


def config(provider):
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown finance connector")
    prefix = "IMPORT_QUICKBOOKS" if provider == "quickbooks" else "IMPORT_ZOHO"
    from app.core.config import settings
    return {key: os.environ.get(f"{prefix}_{key.upper()}", getattr(settings, f"{prefix}_{key.upper()}", "")) for key in ("client_id", "client_secret", "redirect_uri")}


def seal(value):
    return cipher().encrypt(json.dumps(value).encode()).decode()


def unseal(connection):
    try:
        return json.loads(cipher().decrypt(connection.secret.encode()))
    except Exception:
        raise HTTPException(409, "Reconnect this finance account")


def token_url(connection):
    return "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer" if connection.provider == "quickbooks" else f"https://accounts.zoho.{connection.region}/oauth/v2/token"


def request_json(method, url, **kwargs):
    # All callers construct URLs from pinned provider names and validated IDs.
    try:
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            if len(response.content) > 12 * 1024 * 1024:
                raise HTTPException(413, "Provider response too large; use a smaller export")
            data = response.json()
        if not isinstance(data, dict):
            raise HTTPException(502,"Provider returned an unsupported response")
        if data.get("error") or data.get("Fault") or data.get("code", 0):
            raise HTTPException(422, "Provider rejected the request. Check account access and reconnect if needed")
        return data
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Finance provider could not be reached or authorization expired. Reconnect and try again")


def start(db, user, ctx, provider, region):
    credentials = config(provider)
    if not all(credentials.values()):
        raise HTTPException(409, "This connector needs administrator OAuth setup. Configure its client ID, client secret and redirect URI first")
    if region not in REGIONS:
        raise HTTPException(422, "Choose a supported Zoho data centre")
    nonce = secrets.token_urlsafe(32)
    connection = ImportConnection(id=str(uuid4()), organization_id=ctx.company_id, branch_id=ctx.branch_id, created_by=user.id, provider=provider, region=region, account_id="pending", secret=seal({"nonce":nonce,"expires":time.time()+600}))
    db.add(connection)
    db.commit()
    state = connection.id + "." + nonce
    params = dict(client_id=credentials["client_id"], redirect_uri=credentials["redirect_uri"], response_type="code", state=state)
    if provider == "quickbooks":
        url = "https://appcenter.intuit.com/connect/oauth2"
        params["scope"] = "com.intuit.quickbooks.accounting"
    else:
        url = f"https://accounts.zoho.{region}/oauth/v2/auth"
        params.update(scope="ZohoBooks.settings.READ,ZohoBooks.invoices.READ,ZohoBooks.banking.READ", access_type="offline", prompt="consent")
    return {"url": url + "?" + urlencode(params)}


def get_connection(db, identity, user, ctx):
    connection = db.query(ImportConnection).filter_by(id=identity, created_by=user.id, organization_id=ctx.company_id, branch_id=ctx.branch_id).with_for_update().first()
    if not connection:
        raise HTTPException(404, "Connection not found")
    return connection


def complete(db, user, ctx, provider, state, code, account_id):
    identity, separator, nonce = state.partition(".")
    connection = get_connection(db, identity, user, ctx)
    saved = unseal(connection)
    if connection.provider != provider or connection.account_id != "pending" or not separator or not secrets.compare_digest(saved.get("nonce", ""), nonce) or saved.get("expires", 0) < time.time():
        raise HTTPException(409, "Authorization expired or already used. Connect again")
    if not account_id.isascii() or not account_id.isdigit() or len(account_id) > 100:
        raise HTTPException(422, "Enter a valid provider company/organization ID")
    credentials = config(provider)
    payload = dict(grant_type="authorization_code", code=code, redirect_uri=credentials["redirect_uri"])
    extra = {"auth":(credentials["client_id"],credentials["client_secret"])} if provider == "quickbooks" else {}
    if provider == "zoho":
        payload.update(client_id=credentials["client_id"],client_secret=credentials["client_secret"])
    tokens = request_json("POST", token_url(connection), data=payload, **extra)
    if not tokens.get("access_token") or not tokens.get("refresh_token"):
        raise HTTPException(422, "Provider did not grant offline access. Reconnect and grant the requested permissions")
    tokens["expires_at"] = time.time() + int(tokens.get("expires_in",3600))-60
    connection.secret, connection.account_id = seal(tokens), account_id
    db.commit()
    return {"id": connection.id, "provider":provider, "account_id":account_id}


def access_token(db, connection):
    tokens = unseal(connection)
    if tokens.get("expires_at",0) <= time.time():
        credentials = config(connection.provider)
        payload = dict(grant_type="refresh_token",refresh_token=tokens["refresh_token"])
        extra = {"auth":(credentials["client_id"],credentials["client_secret"])} if connection.provider == "quickbooks" else {}
        if connection.provider == "zoho":
            payload.update(client_id=credentials["client_id"],client_secret=credentials["client_secret"])
        fresh = request_json("POST",token_url(connection),data=payload,**extra)
        if not fresh.get("access_token"):
            raise HTTPException(409,"Reconnect this finance account")
        tokens.update(fresh)
        tokens["expires_at"] = time.time()+int(fresh.get("expires_in",3600))-60
        connection.secret = seal(tokens)
        db.flush()
    return tokens["access_token"]


def nature(value):
    value = str(value).lower()
    if value in {"bank","cash","accounts receivable","accounts_receivable","other current asset","other_asset","fixed_asset","stock","payment_clearing"} or "asset" in value:
        return "asset"
    if "liability" in value or "payable" in value or "credit card" in value or value == "credit_card":
        return "liability"
    if "expense" in value or "cost" in value:
        return "expense"
    if "income" in value or "revenue" in value:
        return "income"
    return "equity" if "equity" in value else ""


def fetch_rows(db, connection, entity):
    if entity not in {"ledgers","outstanding_bills"}:
        raise HTTPException(422,"Use a bank CSV/XLSX export for bank statement imports")
    token = access_token(db, connection)
    records = []
    page_limit = 6 if connection.provider == "quickbooks" else 26
    for page in range(1, page_limit + 1):
        if connection.provider == "quickbooks":
            kind = "Account" if entity == "ledgers" else "Invoice"
            data = request_json("GET",f"https://quickbooks.api.intuit.com/v3/company/{connection.account_id}/query",headers={"Authorization":f"Bearer {token}","Accept":"application/json"},params={"query":f"select * from {kind} startposition {(page-1)*1000+1} maxresults 1000"})
            rows = data.get("QueryResponse",{}).get(kind,[])
            more = len(rows) == 1000
        else:
            kind = "chartofaccounts" if entity == "ledgers" else "invoices"
            data = request_json("GET",f"https://www.zohoapis.{connection.region}/books/v3/{kind}",headers={"Authorization":f"Zoho-oauthtoken {token}"},params={"organization_id":connection.account_id,"page":page,"per_page":200})
            rows = data.get("chartofaccounts" if entity == "ledgers" else "invoices",[])
            more = bool(data.get("page_context",{}).get("has_more_page"))
        records.extend(rows)
        if len(records)>5000 or page == page_limit and more:
            raise HTTPException(413,"Provider data exceeds this import's limit. Export a filtered spreadsheet instead; no records were imported")
        if not more:
            break
    normalized=[]
    for row in records:
        qb = connection.provider == "quickbooks"
        if entity == "ledgers":
            normalized.append({"ledger_code":str(row.get("AcctNum") or row.get("Id")) if qb else str(row.get("account_code") or row.get("account_id")),"ledger_name":row.get("Name") if qb else row.get("account_name"),"nature":nature(row.get("AccountType") if qb else row.get("account_type")),"provider_account_id":str(row.get("Id") if qb else row.get("account_id"))})
        else:
            balance = row.get("Balance",0) if qb else row.get("balance",0)
            if DecimalNumber(balance)<=0:
                continue
            normalized.append({"bill_number":row.get("DocNumber") or row.get("Id") if qb else row.get("invoice_number"),"bill_date":row.get("TxnDate") if qb else row.get("date"),"due_date":row.get("DueDate") if qb else row.get("due_date"),"original_amount":row.get("TotalAmt") if qb else row.get("total"),"outstanding_amount":balance,"bill_type":"invoice","provider_customer_id":str(row.get("CustomerRef",{}).get("value","")) if qb else str(row.get("customer_id","")),"currency":row.get("CurrencyRef",{}).get("value","") if qb else row.get("currency_code","")})
    if not normalized:
        raise HTTPException(422,"No matching records were returned by this account")
    headers=list(normalized[0])
    return {"headers":headers,"rows":[[row.get(key,"") for key in headers] for row in normalized],"rowNumbers":list(range(1,len(normalized)+1)),"sheets":[],"sheet":"","headerRow":1,"total":len(normalized)}


def DecimalNumber(value):
    from decimal import Decimal
    return Decimal(str(value))
