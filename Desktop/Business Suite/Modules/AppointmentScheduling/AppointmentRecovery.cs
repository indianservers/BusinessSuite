using System.Security.Cryptography;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed class AppointmentRecoveryJournal(DesktopDatabaseSettings settings)
    : ProtectedAppointmentJournal<AppointmentDraft>(settings, "Appointment recovery", AppointmentRepository.ValidateDraft);

internal class ProtectedAppointmentJournal<T> where T : class
{
    private sealed record ProtectedAttempt(byte[] Data);
    private readonly SalesIntentJournal<ProtectedAttempt> file;
    private readonly Action<T> validate;
    private readonly string openError;

    internal ProtectedAppointmentJournal(DesktopDatabaseSettings settings, string directory, Action<T> validate,
        int maximumBytes = 131072,
        string readError = "The saved booking request could not be verified. Review the agenda before booking again.",
        string openError = "The saved booking request could not be opened for this Windows account.",string resource = "")
    {
        this.validate = validate;
        this.openError = openError;
        file = new(settings, directory, settings.ExpectedAddress + resource, value =>
            {
                if (value.Data is null || value.Data.Length == 0)
                    throw new ArgumentException("Recovery data is missing.");
            }, readError, maximumBytes);
    }

    internal FileStream Acquire() => file.Acquire();
    internal bool HasPending => file.HasPending;
    internal void Clear() => file.Clear();

    internal T? Read()
    {
        var saved = file.Read();
        if (saved is null)
            return null;
        try
        {
            byte[] data = ProtectedData.Unprotect(saved.Data, null, DataProtectionScope.CurrentUser);
            var draft = JsonSerializer.Deserialize<T>(data) ?? throw new JsonException();
            validate(draft);
            return draft;
        }
        catch (Exception error) when (error is JsonException or CryptographicException or ArgumentException)
        {
            throw new InvalidOperationException(openError, error);
        }
    }

    internal void Save(T draft)
    {
        validate(draft);
        byte[] data = ProtectedData.Protect(JsonSerializer.SerializeToUtf8Bytes(draft), null, DataProtectionScope.CurrentUser);
        file.Save(new(data));
    }
}

internal sealed partial class AppointmentRepository
{
    internal AppointmentRecoveryJournal RecoveryJournal() => new(settings);

    internal async Task<int?> ConfirmedRequestAsync(AppointmentDraft draft, CancellationToken cancellation)
    {
        ValidateDraft(draft);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, "view", cancellation);
        using var query = Query(db, tx, @"SELECT r.id,r.data->>'_request_digest'
            FROM public.srm_industry_records r WHERE r.organization_id=@org AND r.branch_id=@branch
                AND r.request_id=@request AND r.created_by=@actor AND r.kind='appointment' AND " + Legacy,
            ("request",NpgsqlDbType.Text,draft.Request.ToString()),("actor",NpgsqlDbType.Integer,actor.Id));
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            return null;
        if (row.IsDBNull(1) || row.GetString(1) != Digest(draft))
            throw new InvalidOperationException("The existing booking request has different details.");
        return row.GetInt32(0);
    }

    internal static void ValidateDraft(AppointmentDraft draft)
    {
        if (draft.Customer<=0 || draft.Service<=0 || draft.Project is <= 0 || draft.Deal is <= 0 || draft.Request==Guid.Empty ||
            draft.Notes is null || draft.CustomerNotes is null || draft.Notes.Length>4000 ||
            draft.CustomerNotes.Length>4000 || draft.Slot is null || draft.Slot.Extras is null ||
            draft.Slot.Provider<=0 || draft.Slot.Extras.Length>9)
            throw new ArgumentException("Choose a customer, service and provider, and enter notes up to 4,000 characters.");
    }
}
