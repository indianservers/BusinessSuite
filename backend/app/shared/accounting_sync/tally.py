"""Local-only Tally XML export reader. No Import/Create/Alter requests exist here.

Bill-wise accounting is required. Unsupported monetary/currency formats fail closed.
Validate exported methods against the customer's TallyPrime edition during pilot.
"""
from decimal import Decimal
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
import httpx
from app.shared.accounting_sync.providers import ProviderError, money

def xml_root(content):
    if len(content)>24*1024*1024 or b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ProviderError("Unsafe or oversized Tally XML response")
    try: root=ET.fromstring(content)
    except ET.ParseError: raise ProviderError("Tally returned invalid XML")
    if root.find(".//LINEERROR") is not None: raise ProviderError("Tally rejected the export; verify selected company")
    if root.find(".//COLLECTION") is None: raise ProviderError("Tally response is missing the requested collection")
    return root

def value(node,key): return (node.findtext(key) or "").strip()
def amount(text):
    # Reject currency suffixes and exchange-rate expressions rather than guessing.
    return Decimal(money(text.replace(",", "")))

def export_request(company,kind,child=None):
    fields={"Company":"Name,GUID", "Ledger":"Name,GUID,Email,IsBillWiseOn", "Voucher":"GUID,Date,VoucherNumber,VoucherTypeName,PartyLedgerName,IsCancelled,AllLedgerEntries.*,AllLedgerEntries.BillAllocations.*", "Bills":"Name,ClosingBalance,BillDate,OpeningBalance"}[kind]
    extra=""
    if kind=="Ledger": extra="<CHILDOF>Sundry Debtors</CHILDOF><BELONGSTO>Yes</BELONGSTO>"
    if child is not None: extra=f"<CHILDOF>{escape(child)}</CHILDOF>"
    return f"""<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>SuiteReadOnly</ID></HEADER><BODY><DESC><STATICVARIABLES><SVCURRENTCOMPANY>{escape(company)}</SVCURRENTCOMPANY><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT><SVFROMDATE TYPE="Date">19000101</SVFROMDATE><SVTODATE TYPE="Date">20991231</SVTODATE></STATICVARIABLES><TDL><TDLMESSAGE><COLLECTION NAME="SuiteReadOnly" ISMODIFY="No"><TYPE>{kind}</TYPE>{extra}<FETCH>{fields}</FETCH></COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"""

class TallyReader:
    def __init__(self, company, account_id, currency, port=9000):
        if not 1<=port<=65535: raise ProviderError("Invalid Tally port")
        if len(currency)!=3 or not currency.isascii() or not currency.isalpha(): raise ProviderError("An explicit three-letter base currency is required")
        self.company=company; self.account_id=account_id; self.currency=currency.upper(); self.url=f"http://127.0.0.1:{port}"
    def collection(self,kind,child=None):
        with httpx.Client(timeout=60,follow_redirects=False,trust_env=False) as client:
            with client.stream("POST",self.url,content=export_request(self.company,kind,child).encode(),headers={"Content-Type":"text/xml; charset=utf-8"}) as response:
                response.raise_for_status(); content=bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content)>24*1024*1024: raise ProviderError("Tally response exceeds local export limit")
        return xml_root(bytes(content))
    def snapshot(self):
        companies=self.collection("Company").findall(".//COMPANY")
        if not any(value(c,"GUID")==self.account_id and (c.get("NAME") or value(c,"NAME"))==self.company for c in companies):
            raise ProviderError("Tally company name and GUID do not match")
        customers=[]; names={}; bills={}
        for ledger in self.collection("Ledger").findall(".//LEDGER"):
            name=ledger.get("NAME") or value(ledger,"NAME"); ident=value(ledger,"GUID")
            if not name or not ident: raise ProviderError("Tally customer has no stable GUID")
            if value(ledger,"ISBILLWISEON").lower()!="yes": raise ProviderError("Enable bill-wise details for all synced customer ledgers")
            names[name]=ident
            customers.append({"external_id":ident,"name":name,"email":value(ledger,"EMAIL") or None,"currency":self.currency,"active":True})
            for bill in self.collection("Bills",name).findall(".//BILL"):
                reference=bill.get("NAME") or value(bill,"NAME")
                closing=amount(value(bill,"CLOSINGBALANCE"))
                if closing>0: raise ProviderError("Customer credit bill requires accountant mapping before publishing")
                if closing: bills[(name,reference)]=abs(closing)
        invoices=[]; payments=[]; used=set()
        for voucher in self.collection("Voucher").findall(".//VOUCHER"):
            if value(voucher,"ISCANCELLED").lower()=="yes": continue
            kind=value(voucher,"VOUCHERTYPENAME") or voucher.get("VCHTYPE")
            party=value(voucher,"PARTYLEDGERNAME")
            entries=[e for e in voucher.findall("ALLLEDGERENTRIES.LIST") if value(e,"LEDGERNAME") in names]
            if not entries: continue
            if kind not in {"Sales","Receipt"}:
                # Other vouchers affect bill balances, but are outside this sales/receipt mirror.
                if kind in {"Credit Note","Debit Note","Payment","Journal","Contra"}: continue
                raise ProviderError("Custom customer voucher types require an explicit Tally mapping")
            ident=value(voucher,"GUID")
            if not ident: raise ProviderError("Tally voucher has no GUID")
            date=value(voucher,"DATE")
            date=f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date)==8 else date
            if kind=="Receipt":
                for entry in entries:
                    customer=names[value(entry,"LEDGERNAME")]
                    payments.append({"external_id":ident+":"+customer,"customer_external_id":customer,"currency":self.currency,"amount":str(abs(amount(value(entry,"AMOUNT")))),"date":date,"reference":value(voucher,"VOUCHERNUMBER")})
                continue
            if len(entries)!=1 or party not in names: raise ProviderError("Sales voucher needs exactly one mapped customer ledger")
            entry=entries[0]; allocations=entry.findall("BILLALLOCATIONS.LIST")
            refs=[value(a,"NAME") for a in allocations if value(a,"BILLTYPE")=="New Ref"]
            if not refs: raise ProviderError("Sales invoice lacks a bill-wise new reference")
            outstanding=Decimal(0)
            for ref in refs:
                key=(party,ref)
                if key in used: raise ProviderError("Bill reference is shared by multiple sales invoices")
                used.add(key); outstanding+=bills.get(key,Decimal(0))
            invoices.append({"external_id":ident,"customer_external_id":names[party],"number":value(voucher,"VOUCHERNUMBER"),"date":date,"due_date":None,"currency":self.currency,"amount":str(abs(amount(value(entry,"AMOUNT")))),"outstanding":str(outstanding),"status":"open" if outstanding else "paid"})
        if any(key not in used for key in bills): raise ProviderError("Unmapped opening bills or customer credits require accountant mapping before publishing")
        return {"account_id":self.account_id,"customers":customers,"invoices":invoices,"payments":payments}
