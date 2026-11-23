using System.Data;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record QuotePdfFile(string Name,byte[] Bytes);

internal sealed partial class QuoteDraftRepository
{
    internal async Task<QuotePdfFile> DraftPdfAsync(int id,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"quotes");
        var row=await LifecycleHeaderAsync(db,tx,id,false,cancellation);
        if (row["sent_at"] is not DBNull)
            throw new InvalidOperationException("Use the original issued PDF for a quotation that has already been issued.");
        var (lines,_)=await LinesAsync(db,tx,id,false,cancellation);
        CheckTotals(row,lines);
        QuotationPdfData data=await ReadPdfDataAsync(db,tx,actor,row,lines,true,cancellation);
        return new($"{SafeName(data.Number)}-{data.Id}-v{data.Version}-draft.pdf",QuotationPdf.Render(data));
    }

    internal async Task<QuotePdfFile> IssuedPdfAsync(int id,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"quotes");
        var row=await LifecycleHeaderAsync(db,tx,id,false,cancellation);
        if (row["sent_at"] is DBNull || row["pdf_file_name"] is not string name ||
            !ValidFileName(name,id,row["version_number"] as int? ?? 1) || (row["pdf_url"] as string)!=PdfUrl(name))
            throw new InvalidOperationException("The quotation has no valid retained issued PDF.");
        string path=PdfPath(name);
        if (!File.Exists(path))
            throw new InvalidOperationException("The retained issued PDF is missing from the configured uploads folder. Restore the original file.");
        var bytes=File.ReadAllBytes(path);
        ValidatePdf(bytes);
        using var evidence=Command(db,tx,@"SELECT metadata_json->>'sha256' FROM public.crm_timeline_events
            WHERE organization_id=@org AND record_type='quotation' AND record_id=@id
              AND event_type='quotation_pdf_issued' AND metadata_json->>'path'=@path ORDER BY id DESC LIMIT 1",
            ("id",NpgsqlDbType.Integer,id),("path",NpgsqlDbType.Text,PdfUrl(name)));
        if (await evidence.ExecuteScalarAsync(cancellation) is string hash && !StringComparer.OrdinalIgnoreCase.Equals(Hash(bytes),hash))
            throw new InvalidOperationException("The retained issued PDF does not match its original hash.");
        return new(name,bytes);
    }

    internal async Task<QuotePdfFile> IssuePdfAsync(QuoteLifecycle original,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireIssuerAsync(db,tx,actor);
        var row=await LifecycleHeaderAsync(db,tx,original.Id,true,cancellation);
        var (lines,lineRevision)=await LinesAsync(db,tx,original.Id,true,cancellation);
        if ((string)row["revision"]!=original.Revision || lineRevision!=original.LineRevision)
            throw new InvalidOperationException("The quotation or its lines changed. Reopen it before issuing.");
        if (!EligibleToIssue(row))
            throw new InvalidOperationException("Only an approved quotation or a draft that does not require approval can be issued.");
        using (var pending=Command(db,tx,@"SELECT status FROM public.crm_approval_requests
            WHERE organization_id=@org AND entity_type='quotation' AND entity_id=@quote
            ORDER BY submitted_at DESC NULLS LAST,id DESC LIMIT 1 FOR SHARE",("quote",NpgsqlDbType.Integer,original.Id)))
            if (await pending.ExecuteScalarAsync(cancellation) is string status && status is "pending" or "rejected")
                throw new InvalidOperationException("Resolve the quotation's approval workflow before issuing.");
        await CrmDirectoryWrites.CheckRequiredFieldsAsync(db,tx,"quotations",settings.OrganizationId,original.Id,cancellation);
        CheckTotals(row,lines);

        QuotationPdfData data=await ReadPdfDataAsync(db,tx,actor,row,lines,false,cancellation);
        byte[] bytes=QuotationPdf.Render(data);
        ValidatePdf(bytes);
        string hash=Hash(bytes);
        string name=$"{SafeName(data.Number)}-{data.Id}-v{data.Version}-{hash.Substring(0,16)}.pdf";
        string path=PdfPath(name);
        StorePdf(path,bytes,hash);
        string url=PdfUrl(name);
        using var update=Command(db,tx,@"UPDATE public.crm_quotations SET status='Sent',approval_status='approved',
            sent_at=now(),pdf_url=@url,pdf_file_name=@name,pdf_status='generated',pdf_generated_at=now(),
            pdf_generated_by_user_id=@actor,updated_at=now(),updated_by_user_id=@actor
            WHERE organization_id=@org AND id=@id",("url",NpgsqlDbType.Text,url),("name",NpgsqlDbType.Text,name),
            ("actor",NpgsqlDbType.Integer,actor.Id),("id",NpgsqlDbType.Integer,original.Id));
        await update.ExecuteNonQueryAsync(cancellation);
        await LifecycleEvidenceAsync(db,tx,actor.Id,original,row,false,"Sent","approved",
            "Issued an offline PDF. No provider delivery was recorded.",cancellation);
        using var audit=Command(db,tx,@"INSERT INTO public.crm_timeline_events
            (organization_id,record_type,record_id,event_type,title,description,metadata_json,actor_user_id)
            VALUES (@org,'quotation',@id,'quotation_pdf_issued','Quotation PDF issued',
                'The original version was retained. No provider delivery was recorded.',@evidence,@actor)",
            ("id",NpgsqlDbType.Integer,original.Id),("actor",NpgsqlDbType.Integer,actor.Id),
            ("evidence",NpgsqlDbType.Json,JsonSerializer.Serialize(new {versionNumber=data.Version,path=url,sha256=hash,
                byteCount=bytes.Length,delivery="not_dispatched"})));
        await audit.ExecuteNonQueryAsync(cancellation);
        tx.Commit();
        return new(name,bytes);
    }

    private async Task<QuotationPdfData> ReadPdfDataAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,
        DataRow quote,List<QuoteDraftLine> lines,bool draft,CancellationToken cancellation)
    {
        int? account=quote["company_id"] as int? ?? quote["account_id"] as int?;
        int? contact=quote["contact_id"] as int?;
        if (account.HasValue)
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"accounts","view");
        if (contact.HasValue)
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"contacts","view");
        using var query=Command(db,tx,@"SELECT COALESCE(NULLIF(s.legal_name,''),s.name),
            concat_ws(', ',NULLIF(s.address,''),NULLIF(s.city,''),NULLIF(s.state,''),NULLIF(s.pincode,''),NULLIF(s.country,'')),
            concat_ws('  /  ',NULLIF(s.email,''),NULLIF(concat_ws(' ',s.phone_country_code,s.phone),'')),
            CASE WHEN NULLIF(s.gstin,'') IS NULL THEN '' ELSE 'GSTIN '||s.gstin END,
            c.id,c.name,concat_ws(', ',NULLIF(c.address,''),NULLIF(c.city,''),NULLIF(c.state,''),NULLIF(c.country,'')),
            concat_ws('  /  ',NULLIF(p.full_name,''),NULLIF(COALESCE(p.email,c.email),''),
                NULLIF(concat_ws(' ',COALESCE(p.phone_country_code,c.phone_country_code),COALESCE(p.phone,c.phone)),'')),p.id
            FROM public.companies s
            LEFT JOIN public.crm_companies c ON c.id=@account AND c.organization_id=@org AND c.deleted_at IS NULL
                AND "+CrmDirectoryWrites.BranchScope("crm_companies","c",includeShares:true)+@"
            LEFT JOIN public.crm_contacts p ON p.id=@contact AND p.organization_id=@org AND p.deleted_at IS NULL
                AND "+CrmDirectoryWrites.BranchScope("crm_contacts","p",includeShares:true)+@"
            WHERE s.id=@org AND s.is_active",
            ("account",NpgsqlDbType.Integer,account),("contact",NpgsqlDbType.Integer,contact));
        using var reader=await query.ExecuteReaderAsync(cancellation);
        if (!await reader.ReadAsync(cancellation) || (account.HasValue&&reader.IsDBNull(4)) || (contact.HasValue&&reader.IsDBNull(8)))
            throw new InvalidOperationException("The quotation's seller, customer or contact is unavailable in this branch.");
        string currency=quote["currency"] as string??"";
        if (currency.Length!=3)
            throw new InvalidOperationException("Set this quotation's currency before producing a PDF.");
        return new((int)quote["id"],quote["version_number"] as int? ?? 1,(string)quote["quote_number"],
            draft?(string)quote["status"]:"Issued",(DateTime)quote["issue_date"],(DateTime)quote["expiry_date"],currency,
            reader.GetString(0),reader.GetString(1),reader.GetString(2),reader.GetString(3),
            reader.IsDBNull(5)?"Customer details not linked":reader.GetString(5),reader.GetString(6),reader.GetString(7),
            quote["terms"] as string??quote["terms_and_conditions"] as string??"",lines,draft);
    }

    private async Task RequireIssuerAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        if (!actor.IsSuperuser || !actor.CanWriteBranch)
            throw new UnauthorizedAccessException("Offline issuance requires a Suite superuser in a writable branch.");
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,Branch,actor,"crm","send",
            "crm_quotes_send","crm_admin","crm_manage");
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Offline issuance requires branch-wide or organization-wide CRM scope.");
    }

    private async Task<bool> CanIssueAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,DataRow quote)
    {
        if (settings.BranchId is null || !EligibleToIssue(quote))
            return false;
        try { await RequireIssuerAsync(db,tx,actor);return true; }
        catch(UnauthorizedAccessException) { return false; }
    }

    private static bool EligibleToIssue(DataRow quote) =>
        quote["sent_at"] is DBNull && quote["converted_srm_sales_order_id"] is DBNull &&
        ((quote["status"] is string status && status.Equals("Approved",StringComparison.OrdinalIgnoreCase) &&
          quote["approval_status"] is string approved && approved.Equals("approved",StringComparison.OrdinalIgnoreCase)) ||
         (quote["status"] is string draft && draft.Equals("Draft",StringComparison.OrdinalIgnoreCase) &&
          quote["approval_status"] is string policy && policy.Equals("not_required",StringComparison.OrdinalIgnoreCase)));

    private string PdfUrl(string file)=>$"/uploads/crm/quotations/{settings.OrganizationId}/{file}";
    private string PdfPath(string file)=>Path.Combine(settings.DocumentsRoot,"crm","quotations",settings.OrganizationId.ToString(),file);
    private static bool ValidFileName(string file,int quote,int version)=>file.Length<=180 &&
        Regex.IsMatch(file,$@"\A[A-Za-z0-9_.-]+-{quote}-v{version}-[0-9a-f]{{16}}\.pdf\z",
            RegexOptions.IgnoreCase|RegexOptions.CultureInvariant);
    private static string SafeName(string number)
    {
        string safe=Regex.Replace(number.Trim(),"[^A-Za-z0-9_-]+","-").Trim('-');
        return safe.Length==0?"quotation":safe.Substring(0,Math.Min(70,safe.Length));
    }
    private static string Hash(byte[] bytes)
    {
        using var sha=SHA256.Create();
        return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
    }
    private static void ValidatePdf(byte[] bytes)
    {
        if (bytes.Length<8 || bytes[0]!='%' || bytes[1]!='P' || bytes[2]!='D' || bytes[3]!='F' || bytes[4]!='-')
            throw new InvalidOperationException("The quotation PDF data is invalid.");
    }
    private static void StorePdf(string path,byte[] bytes,string hash)
    {
        if (File.Exists(path))
        {
            if (!StringComparer.OrdinalIgnoreCase.Equals(Hash(File.ReadAllBytes(path)),hash))
                throw new InvalidOperationException("A different PDF already exists at the retained path.");
            return;
        }
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string staged=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        try
        {
            using (var stream=new FileStream(staged,FileMode.CreateNew,FileAccess.Write,FileShare.None))
            {
                stream.Write(bytes,0,bytes.Length);
                stream.Flush(true);
            }
            File.Move(staged,path);
        }
        finally
        {
            if (File.Exists(staged)) File.Delete(staged);
        }
    }
}
