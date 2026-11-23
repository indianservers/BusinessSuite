using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed class PosCashMovementJournal : SalesIntentJournal<PosCashMovementIntent>
{
    internal PosCashMovementJournal(DesktopDatabaseSettings settings)
        : base(settings, "Cash movements", "", SalesOrderRepository.ValidateCashIntent,
            "A saved cash request could not be verified. Review drawer history before entering another movement.") { }
}

internal class SalesIntentJournal<T> where T : class
{
    private readonly string path;
    private readonly Action<T> validate;
    private readonly string recoveryError;
    private readonly int maximumBytes;

    internal SalesIntentJournal(DesktopDatabaseSettings settings, string directory, string resource, Action<T> validate,
        string recoveryError, int maximumBytes = 32768)
    {
        var endpoint = new NpgsqlConnectionStringBuilder(settings.ConnectionString);
        string scope = string.Join("\n", endpoint.Host?.ToLowerInvariant(), endpoint.Port.ToString(CultureInfo.InvariantCulture),
            endpoint.Database, endpoint.Username, settings.OrganizationId.ToString(CultureInfo.InvariantCulture),
            settings.BranchId?.ToString(CultureInfo.InvariantCulture));
        this.validate = validate;
        this.recoveryError = recoveryError;
        this.maximumBytes = maximumBytes;
        if (resource.Length > 0)
            scope += "\n" + resource;
        using var sha = SHA256.Create();
        string key = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(scope))).Replace("-", "");
        path = Path.Combine(Path.GetDirectoryName(DesktopDatabaseSettings.EnvironmentPath)!, directory, key + ".json");
    }

    internal bool HasPending => File.Exists(path);

    internal FileStream Acquire()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        return new FileStream(path + ".lock", FileMode.OpenOrCreate, FileAccess.Write, FileShare.None);
    }

    internal T? Read()
    {
        if (!HasPending)
            return null;
        try
        {
            if (new FileInfo(path).Length > maximumBytes)
                throw new JsonException();
            var intent = JsonSerializer.Deserialize<T>(File.ReadAllText(path)) ??
                throw new JsonException();
            validate(intent);
            return intent;
        }
        catch (Exception error) when (error is JsonException or ArgumentException)
        {
            throw new InvalidOperationException(recoveryError, error);
        }
    }

    internal void Save(T intent)
    {
        validate(intent);
        using (var stream = new FileStream(path + ".tmp", FileMode.Create, FileAccess.Write, FileShare.None))
        {
            JsonSerializer.Serialize(stream, intent);
            stream.Flush(true);
        }
        WindowsCompatibility.ReplaceFile(path + ".tmp", path);
    }

    internal void Clear() => File.Delete(path);
}

internal sealed partial class SalesOrderRepository
{
    internal PosCashMovementJournal CashMovementJournal() => new PosCashMovementJournal(settings);
}
