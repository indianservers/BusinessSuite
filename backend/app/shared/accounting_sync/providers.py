"""Pinned-host GET-only adapters. Full snapshots reconcile payments and removals."""
import time
from decimal import Decimal, InvalidOperation
import httpx
from fastapi import HTTPException
from app.shared import import_connectors as oauth

ENTITIES = ("customers", "invoices", "payments")
MAX_RECORDS = 50000

class ProviderError(Exception):
    pass

def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite(): raise ValueError()
        return str(amount)
    except (InvalidOperation, ValueError, TypeError):
        raise ProviderError("Provider returned an invalid monetary amount")

def get_json(url, headers, params):
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
                with client.stream("GET", url, headers=headers, params=params) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt == 2: raise ProviderError("Provider unavailable or rate limited; retry sync later")
                        delay = min(5, max(1, int(response.headers.get("Retry-After", "1"))))
                        time.sleep(delay)
                        continue
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 12 * 1024 * 1024: raise ProviderError("Provider page exceeds size limit")
                    import json
                    result = json.loads(body)
                    if not isinstance(result, dict) or result.get("Fault") or result.get("code", 0):
                        raise ProviderError("Provider rejected the read request; verify authorization")
                    return result
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt == 2: raise ProviderError("Provider could not be reached; retry sync later")
            time.sleep(attempt + 1)
        except (httpx.HTTPError, ValueError):
            raise ProviderError("Provider request failed; verify access and reconnect if needed")
    raise ProviderError("Provider read failed")

def normalize(provider, entity, row):
    qb = provider == "quickbooks"
    id_key = "Id" if qb else {"customers":"contact_id", "invoices":"invoice_id", "payments":"payment_id"}[entity]
    identity = str(row.get(id_key) or "")
    if not identity or len(identity) > 160: raise ProviderError("Provider record has no valid stable ID")
    currency = (row.get("CurrencyRef") or {}).get("value") if qb else row.get("currency_code")
    result = {"external_id":identity, "currency":currency or "Unknown"}
    if entity == "customers":
        result.update(name=row.get("DisplayName") if qb else row.get("contact_name"),
                      email=(row.get("PrimaryEmailAddr") or {}).get("Address") if qb else row.get("email"),
                      active=row.get("Active", True) if qb else row.get("status") != "inactive")
    else:
        customer = (row.get("CustomerRef") or {}).get("value") if qb else row.get("customer_id")
        if not customer: raise ProviderError("Provider transaction has no customer ID")
        result.update(customer_external_id=str(customer), date=row.get("TxnDate") if qb else row.get("date"),
                      amount=money(row.get("TotalAmt") if qb else row.get("total") if entity == "invoices" else row.get("amount")))
        if entity == "invoices":
            result.update(number=row.get("DocNumber") if qb else row.get("invoice_number"),
                          due_date=row.get("DueDate") if qb else row.get("due_date"),
                          outstanding=money(row.get("Balance") if qb else row.get("balance")),
                          status="provider_reported" if qb else row.get("status"))
        else:
            result["reference"] = row.get("PaymentRefNum") if qb else row.get("reference_number")
    return result

def pull(db, connection, source):
    if source.provider != connection.provider or source.account_id != connection.account_id:
        raise ProviderError("Accounting authorization no longer matches this connection")
    if not source.account_id.isascii() or not source.account_id.isdigit(): raise ProviderError("Invalid provider account ID")
    if source.region not in oauth.REGIONS: raise ProviderError("Unsupported provider data centre")
    try: token = oauth.access_token(db, source)
    except HTTPException: raise ProviderError("Accounting authorization expired; reconnect the account")
    result = {}
    qb = connection.provider == "quickbooks"
    for entity in ENTITIES:
        records = []
        kind = {"customers":"Customer", "invoices":"Invoice", "payments":"Payment"}[entity] if qb else {"customers":"contacts", "invoices":"invoices", "payments":"customerpayments"}[entity]
        for page in range(1, 252):
            if qb:
                host = "sandbox-quickbooks.api.intuit.com" if connection.sandbox else "quickbooks.api.intuit.com"
                query = f"select * from {kind}" + (" where Active IN (true, false)" if entity == "customers" else "")
                query += f" startposition {(page-1)*1000+1} maxresults 1000"
                data = get_json(f"https://{host}/v3/company/{source.account_id}/query", {"Authorization":f"Bearer {token}","Accept":"application/json"}, {"query":query})
                container = data.get("QueryResponse")
                if not isinstance(container, dict): raise ProviderError("Invalid QuickBooks query response")
                batch = container.get(kind, [])
                more = len(batch) == 1000 if isinstance(batch, list) else False
            else:
                params = {"organization_id":source.account_id,"page":page,"per_page":200}
                if entity == "customers":
                    params["contact_type"] = "customer"
                    params["filter_by"] = "Status.All"
                data = get_json(f"https://www.zohoapis.{source.region}/books/v3/{kind}", {"Authorization":f"Zoho-oauthtoken {token}"}, params)
                batch = data.get(kind)
                context = data.get("page_context")
                if not isinstance(context, dict) or not isinstance(context.get("has_more_page"), bool): raise ProviderError("Zoho response is missing pagination metadata")
                more = context.get("has_more_page", False)
            if not isinstance(batch, list): raise ProviderError("Provider returned an invalid record list")
            records.extend(normalize(connection.provider,entity,row) for row in batch)
            if len(records) > MAX_RECORDS: raise ProviderError("Sync limit exceeded; narrow the integration scope")
            if not more: break
        else: raise ProviderError("Provider pagination did not complete")
        result[entity] = records
    return result
