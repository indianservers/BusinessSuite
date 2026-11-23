using System.Security.Cryptography;
using System.Text.RegularExpressions;
using Npgsql;

namespace Business_Suite;

internal sealed record EmployeeAttachment(string Name, byte[] Content);

internal sealed partial class EmployeeAdministrationRepository
{
    private const int MaxEmployeeAttachmentBytes = 10 * 1024 * 1024;
    private static readonly Regex EmployeeAttachmentName = new(@"\A[a-f0-9]{32}\.(pdf|docx?|jpe?g|png)\z",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    private static readonly string[] DocumentTypes = { "Education", "Experience", "Identity", "Other" };

    internal async Task<int> UploadEmployeeAttachmentAsync(int employee, string revision, string type, string? name,
        DateTime? expiry, string source, CancellationToken cancellation)
    {
        if (!DocumentTypes.Contains(type))
            throw new InvalidOperationException("Choose a document type.");
        string fileName = Path.GetFileName(source);
        string extension = Path.GetExtension(fileName).ToLowerInvariant();
        if (!EmployeeAttachmentName.IsMatch(new string('a', 32) + extension))
            throw new InvalidOperationException("Choose a PDF, Word document, JPEG or PNG.");
        name = Clean(name, 200) ?? Clean(fileName, 200) ??
            throw new InvalidOperationException("Enter a document name.");

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, true, cancellation);
        if (revision != await ReadQualificationRevisionAsync(db, tx, employee, true, cancellation))
            throw new InvalidOperationException("The employee profile changed. Refresh before uploading.");
        actor = await AuthorizeAsync(db, tx, true, cancellation);
        await RequireDocumentAccessAsync(db, tx, actor, employee, cancellation);
        byte[] bytes = await ReadAttachmentBytesAsync(source, cancellation);
        await EnsureEmployeeLocalStorageAsync(db, tx, bytes.Length, cancellation);
        string generated = Guid.NewGuid().ToString("N") + extension;
        string relative = $"employee_docs/{employee}/{generated}";
        string target = EmployeeAttachmentPath(employee, generated, create: true);
        bool created = false;
        bool committing = false;
        try
        {
            using (var file = new FileStream(target, FileMode.CreateNew, FileAccess.Write, FileShare.None, 81920, useAsync: true))
            {
                created = true;
                await file.WriteAsync(bytes, 0, bytes.Length, cancellation);
                file.Flush(true);
            }

            using var write = new NpgsqlCommand(@"
                INSERT INTO public.file_storage_objects(organization_id,module,relative_path,filename,content_type,
                    size,sha256,provider,status,versions,uploaded_by)
                VALUES(@company,'hrms',@relative,@name,@mime,@size,@digest,'local','local','[]'::json,@actor);
                INSERT INTO public.employee_documents(employee_id,document_type,document_name,file_url,expiry_date,
                    verification_status,is_verified)
                VALUES(@employee,@type,@name,'/uploads/'||@relative,@expiry,'Pending',false) RETURNING id", db, tx);
            SetScope(write);
            write.Parameters.AddWithValue("relative", relative);
            write.Parameters.AddWithValue("name", name);
            write.Parameters.AddWithValue("type", type);
            write.Parameters.AddWithValue("employee", employee);
            write.Parameters.AddWithValue("actor", actor.Id);
            write.Parameters.AddWithValue("mime", extension switch
            {
                ".pdf" => "application/pdf", ".doc" => "application/msword",
                ".docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".png" => "image/png", _ => "image/jpeg"
            });
            write.Parameters.AddWithValue("size", bytes.Length);
            write.Parameters.AddWithValue("digest", AttachmentDigest(bytes));
            write.Parameters.Add("expiry", NpgsqlTypes.NpgsqlDbType.Date).Value = (object?)expiry?.Date ?? DBNull.Value;
            int id = (int)(await write.ExecuteScalarAsync(cancellation))!;
            var after = await QualificationValuesAsync(db, tx, employee, id, DocumentResource, cancellation);
            await FinishQualificationAsync(db, tx, actor.Id, employee, id, false, false, DocumentResource,
                new Dictionary<string, string?>(), after, cancellation);

            committing = true;
            await tx.CommitAsync(cancellation);
            return id;
        }
        finally
        {
            if (created && !committing)
            {
                try { File.Delete(target); }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
            }
        }
    }

    internal async Task<EmployeeAttachment> ReadEmployeeAttachmentAsync(int employee, int document, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, false, cancellation);
        await RequireDocumentAccessAsync(db, tx, actor, employee, cancellation);
        await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, settings.BranchId!.Value,
            actor, "hrms", "view", "employee_view");
        using var query = new NpgsqlCommand(@"
            SELECT ed.file_url,ed.document_name,s.provider,s.status,s.size,s.sha256
            FROM public.employee_documents ed LEFT JOIN public.file_storage_objects s
              ON s.organization_id=@company AND s.module='hrms' AND '/uploads/'||s.relative_path=ed.file_url
            WHERE ed.id=@document AND ed.employee_id=@employee" + QualificationScope, db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("document", document);
        query.Parameters.AddWithValue("employee", employee);
        query.Parameters.AddWithValue("resource", DocumentResource);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("The document is unavailable.");
        string prefix = $"/uploads/employee_docs/{employee}/";
        string reference = row.IsDBNull(0) ? "" : row.GetString(0);
        if (!reference.StartsWith(prefix, StringComparison.Ordinal) || !EmployeeAttachmentName.IsMatch(reference.Substring(prefix.Length)))
            throw new InvalidOperationException("This attachment has no supported local file reference.");
        if (!row.IsDBNull(2) && (row.GetString(2) != "local" || row.GetString(3) != "local"))
            throw new InvalidOperationException("This attachment requires its configured storage provider.");
        string fileName = reference.Substring(prefix.Length);
        string source = EmployeeAttachmentPath(employee, fileName, create: false);
        if (!File.Exists(source))
            throw new InvalidOperationException("The attachment was not found in the configured local storage folder.");
        byte[] bytes = await ReadAttachmentBytesAsync(source, cancellation);
        if (!row.IsDBNull(4) && (bytes.Length != row.GetInt32(4) || !string.Equals(AttachmentDigest(bytes),
            row.GetString(5), StringComparison.OrdinalIgnoreCase)))
            throw new InvalidOperationException("The local attachment did not match its recorded size or checksum.");
        string suggested = row.IsDBNull(1) ? "" : row.GetString(1);
        string safeName = string.Concat(suggested.Select(ch => Path.GetInvalidFileNameChars().Contains(ch) ? '_' : ch)).Trim('.', ' ');
        return new EmployeeAttachment((safeName.Length == 0 ? "Employee document" : Path.GetFileNameWithoutExtension(safeName)) +
            Path.GetExtension(fileName), bytes);
    }

    private async Task EnsureEmployeeLocalStorageAsync(NpgsqlConnection db, NpgsqlTransaction tx, int size, CancellationToken cancellation)
    {
        using (var company = new NpgsqlCommand("SELECT id FROM public.companies WHERE id=@company FOR UPDATE", db, tx))
        {
            SetScope(company);
            await company.ExecuteNonQueryAsync(cancellation);
        }
        using var policy = new NpgsqlCommand(@"
            SELECT EXISTS (SELECT 1 FROM public.file_storage_policies p WHERE p.organization_id=@company AND p.enabled
                AND (coalesce(p.routes::jsonb->'hrms','null'::jsonb) NOT IN ('null'::jsonb,'{}'::jsonb) OR
                    coalesce(p.routes::jsonb->'default','null'::jsonb) NOT IN ('null'::jsonb,'{}'::jsonb)))",
            db, tx);
        SetScope(policy);
        if (await policy.ExecuteScalarAsync(cancellation) is true)
            throw new InvalidOperationException("Employee uploads are routed to a provider unavailable in offline desktop mode.");
        using var allowance = new NpgsqlCommand(@"
            WITH settings AS (
                SELECT p.id AS plan,coalesce(p.config_json::jsonb,'{}')||coalesce(s.config_json::jsonb,'{}') AS options
                FROM public.tenant_subscriptions s LEFT JOIN public.tenant_subscription_plans p ON p.id=s.plan_id
                WHERE s.company_id=@company
            ), effective AS (
                SELECT original.plan,original.options,
                    (original.options->'scheduled_change'->>'effective_at')::timestamptz <= clock_timestamp() AS due,
                    (original.options->'scheduled_change'->>'plan_id')::integer AS scheduled_plan
                FROM settings original
            ), calculated AS (
                SELECT e.plan,e.due,p.id AS next_plan, e.options ||
                    CASE WHEN e.due THEN coalesce(p.config_json::jsonb,'{}') ELSE '{}'::jsonb END AS options
                FROM effective e LEFT JOIN public.tenant_subscription_plans p ON p.id=e.scheduled_plan
            )
            SELECT coalesce((SELECT plan IS NULL OR (due IS TRUE AND next_plan IS NULL)
                OR (coalesce((options->>'enforce')::boolean,false) AND coalesce((options->>'storage_mib')::numeric,0)>0
                    AND (SELECT coalesce(sum(o.size),0) FROM public.file_storage_objects o WHERE o.organization_id=@company)
                        + @size > (options->>'storage_mib')::numeric*1048576)
                FROM calculated),false)", db, tx);
        SetScope(allowance);
        allowance.Parameters.AddWithValue("size", size);
        if (await allowance.ExecuteScalarAsync(cancellation) is true)
            throw new InvalidOperationException("The company storage allowance is unavailable or has been reached.");
    }

    private string EmployeeAttachmentPath(int employee, string name, bool create)
    {
        string root = Path.GetFullPath(settings.DocumentsRoot);
        string documentFolder = Path.Combine(root, "employee_docs", employee.ToString(System.Globalization.CultureInfo.InvariantCulture));
        for (DirectoryInfo? folder = new(documentFolder); folder is not null; folder = folder.Parent)
            if (folder.Exists && (folder.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new InvalidOperationException("The document storage path uses an unsupported redirect.");
        if (create)
            Directory.CreateDirectory(documentFolder);
        string file = Path.Combine(documentFolder, name);
        if (File.Exists(file) && (File.GetAttributes(file) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidOperationException("The attachment uses an unsupported redirect.");
        return file;
    }

    private static async Task<byte[]> ReadAttachmentBytesAsync(string file, CancellationToken cancellation)
    {
        using var source = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.Read, 81920, useAsync: true);
        if (source.Length is <= 0 or > MaxEmployeeAttachmentBytes)
            throw new InvalidOperationException("Choose a nonempty document up to 10 MB.");
        var result = new byte[(int)source.Length];
        int offset = 0;
        while (offset < result.Length)
        {
            int read = await source.ReadAsync(result, offset, result.Length - offset, cancellation);
            if (read == 0)
                throw new IOException("The file changed while being read.");
            offset += read;
        }
        return result;
    }

    private static string AttachmentDigest(byte[] bytes)
    {
        using var sha = SHA256.Create();
        return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }
}
