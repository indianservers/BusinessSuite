using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using Npgsql;

namespace Business_Suite;

internal sealed partial class EmployeeAdministrationRepository
{
    internal async Task<string> UploadSettlementBrandAsync(string kind,string sourcePath,string revision,CancellationToken cancellation)
    {
        if (kind is not ("logo" or "signature"))
            throw new InvalidOperationException("Choose a company logo or authorized signature image.");

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireSettlementTemplateWriteAsync(db,tx,actor);

        var png = PreparePayrollBrandImage(sourcePath);
        const string container = "payroll-branding";
        string companyFolder = settings.OrganizationId.ToString(System.Globalization.CultureInfo.InvariantCulture);
        string filename = kind + "_" + Guid.NewGuid().ToString("N") + ".png";
        string relative = container + "/" + companyFolder + "/" + filename;
        string folderPath = Path.Combine(settings.DocumentsRoot,container,companyFolder);
        for (DirectoryInfo? folder = new DirectoryInfo(folderPath); folder is not null; folder = folder.Parent)
            if (folder.Exists && (folder.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new InvalidOperationException("The payroll branding folder uses an unsupported redirect.");
        Directory.CreateDirectory(folderPath);
        string path = Path.Combine(folderPath,filename);
        bool savedFile = false;
        bool committing = false;
        try
        {
            using (var stream = new FileStream(path,FileMode.CreateNew,FileAccess.Write,FileShare.None))
            {
                savedFile = true;
                await stream.WriteAsync(png,0,png.Length,cancellation);
                stream.Flush(true);
            }
            using var save = new NpgsqlCommand(@"
                INSERT INTO public.payroll_delivery_profiles(company_id,ytd_basis,fy_start_month,regular_template,
                    settlement_template,branding,payout_mode,updated_by,updated_at)
                SELECT @company,'financial',4,'{}'::json,'{}'::json,jsonb_build_object(@kind,@relative)::json,'test',@actor,now()
                WHERE @revision='' OR EXISTS (SELECT 1 FROM public.payroll_delivery_profiles p
                    WHERE p.company_id=@company AND p.xmin::text=@revision)
                ON CONFLICT (company_id) DO UPDATE SET
                    branding=(coalesce(payroll_delivery_profiles.branding::jsonb,'{}'::jsonb) || excluded.branding::jsonb)::json,
                    updated_by=excluded.updated_by,updated_at=excluded.updated_at
                WHERE payroll_delivery_profiles.xmin::text=@revision RETURNING xmin::text",db,tx);
            save.Parameters.AddWithValue("company",settings.OrganizationId);
            save.Parameters.AddWithValue("kind",kind);
            save.Parameters.AddWithValue("relative",relative);
            save.Parameters.AddWithValue("actor",actor.Id);
            save.Parameters.AddWithValue("revision",revision);
            if (await save.ExecuteScalarAsync(cancellation) is not string changed)
                throw new InvalidOperationException("The payroll profile changed. Reopen the editor and try again.");
            using var audit = new NpgsqlCommand(@"
                INSERT INTO public.suite_access_audit(actor_id,company_id,operation,reason,outcome,after_json)
                VALUES(@actor,@company,'payroll_branding_uploaded','Payroll branding image','success',json_build_object('kind',@kind))",db,tx);
            audit.Parameters.AddWithValue("company",settings.OrganizationId);
            audit.Parameters.AddWithValue("kind",kind);
            audit.Parameters.AddWithValue("actor",actor.Id);
            await audit.ExecuteNonQueryAsync(cancellation);
            cancellation.ThrowIfCancellationRequested();
            committing = true;
            await tx.CommitAsync(CancellationToken.None);
            return changed;
        }
        catch
        {
            if (savedFile && !committing)
            {
                try { File.Delete(path); }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
            }
            throw;
        }
    }

    private static byte[] PreparePayrollBrandImage(string path)
    {
        using var input = new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read);
        if (input.Length is < 8 or > 2_097_152)
            throw new InvalidOperationException("Choose a nonempty PNG or JPEG image up to 2 MB.");
        using (var header = new BinaryReader(input,System.Text.Encoding.UTF8,leaveOpen:true))
        {
            var bytes = header.ReadBytes(8);
            if (!(bytes[0] == 0xff && bytes[1] == 0xd8 && bytes[2] == 0xff) &&
                !bytes.SequenceEqual(new byte[] { 137,80,78,71,13,10,26,10 }))
                throw new InvalidOperationException("Choose a valid PNG or JPEG image.");
            input.Position = 0;
        }
        try
        {
            using var original = Image.FromStream(input,false,true);
            if (!(original.RawFormat.Equals(ImageFormat.Png) || original.RawFormat.Equals(ImageFormat.Jpeg)) ||
                original.Width < 1 || original.Height < 1 || (long)original.Width * original.Height > 12_000_000)
                throw new InvalidOperationException("Choose a valid PNG or JPEG image with at most 12 million pixels.");
            using var normalized = new Bitmap(original.Width,original.Height,PixelFormat.Format32bppArgb);
            using (var painter = Graphics.FromImage(normalized))
            {
                painter.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceCopy;
                painter.DrawImageUnscaled(original,0,0);
            }
            using var output = new MemoryStream();
            normalized.Save(output,ImageFormat.Png);
            return output.ToArray();
        }
        catch (ArgumentException ex)
        {
            throw new InvalidOperationException("Choose a valid PNG or JPEG image.",ex);
        }
        catch (ExternalException ex)
        {
            throw new InvalidOperationException("The selected image could not be decoded.",ex);
        }
    }
}
