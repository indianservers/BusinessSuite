using System.Net.Http;
using System.Text.Json;

namespace Business_Suite;

internal sealed record ConnectionSettings(
    bool UseLocal = false,
    string LocalAddress = "http://localhost:1534",
    string RemoteAddress = "")
{
    private static readonly string FilePath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Business Suite", "connection.json");

    private static readonly HttpClient Client = new(new HttpClientHandler { AllowAutoRedirect = false })
    {
        Timeout = TimeSpan.FromSeconds(10)
    };

    public Uri ServerOrigin => ParseOrigin(UseLocal ? LocalAddress : RemoteAddress, UseLocal);
    public Uri ApiBaseAddress => new(ServerOrigin, "/api/v1/");

    public static ConnectionSettings Load()
    {
        if (!File.Exists(FilePath))
            return File.Exists(Path.Combine(AppContext.BaseDirectory, "Start Local Workspace.cmd"))
                ? new(UseLocal: true, LocalAddress: "http://127.0.0.1:15434")
                : new();

        return JsonSerializer.Deserialize<ConnectionSettings>(File.ReadAllText(FilePath))
            ?? throw new JsonException("The settings file is empty.");
    }

    public void Save()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
        string temporaryPath = FilePath + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            File.WriteAllText(temporaryPath, JsonSerializer.Serialize(this));
            WindowsCompatibility.ReplaceFile(temporaryPath, FilePath);
        }
        finally
        {
            File.Delete(temporaryPath);
        }
    }

    public static Uri ParseOrigin(string value, bool local)
    {
        value = value.Trim();
        if (value.IndexOf("://", StringComparison.Ordinal) < 0)
            value = (local ? "http://" : "https://") + value;

        if (!Uri.TryCreate(value, UriKind.Absolute, out Uri? uri)
            || uri.HostNameType == UriHostNameType.Unknown
            || uri.Host.Length == 0
            || uri.Scheme is not ("http" or "https")
            || uri.UserInfo.Length != 0
            || uri.AbsolutePath != "/"
            || uri.Query.Length != 0
            || uri.Fragment.Length != 0)
        {
            throw new FormatException("Enter a website or server address without a page path.");
        }

        if (!local && uri.Scheme != "https")
            throw new FormatException("Remote connections require an HTTPS address.");

        return new Uri(uri.GetLeftPart(UriPartial.Authority));
    }

    public async Task<bool> CheckHealthAsync(CancellationToken cancellationToken)
    {
        using HttpResponseMessage response = await Client.GetAsync(
            new Uri(ServerOrigin, "/health"), cancellationToken);
        if (!response.IsSuccessStatusCode)
            throw new ApiResponseException("The health check failed.", response.StatusCode);

        using JsonDocument payload = JsonDocument.Parse(
            await response.Content.ReadAsStreamAsync());
        if (payload.RootElement.ValueKind != JsonValueKind.Object
            || !payload.RootElement.TryGetProperty("status", out JsonElement status)
            || !payload.RootElement.TryGetProperty("db", out JsonElement database)
            || status.ValueKind != JsonValueKind.String
            || database.ValueKind != JsonValueKind.String
            || status.GetString() is not ("healthy" or "degraded")
            || database.GetString() is not ("ok" or "error"))
        {
            throw new JsonException("Unexpected health response.");
        }

        return status.GetString() == "healthy" && database.GetString() == "ok";
    }
}
