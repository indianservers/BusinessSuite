using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Business_Suite;

internal sealed record NoteContent(string Title, string Content, string[] Tags,
    bool Favorite, bool Pinned, bool Archived, bool Trashed)
{
    public bool Matches(NoteContent other) =>
        (this with { Tags = other.Tags }) == other && Tags.SequenceEqual(other.Tags);
}

internal sealed record SyncNote(Guid Id, int Version, NoteContent Note);
internal sealed record NotePage(string? Tenant, int? CompanyId, SyncNote[] Items, int? Next);
internal sealed record LoginReply(string? AccessToken, int UserId, string? Email, string? MfaToken);
internal sealed record NoteConflict(SyncNote Local, SyncNote Remote, string Reason)
{
    public override string ToString() => $"{Local.Note.Title} — {Reason}";
}

internal sealed class NoteApi(Uri origin)
{
    private const string Notes = "project-management/desktop-sync/notes";
    private static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
    };

    private static readonly HttpClient Http = new(new HttpClientHandler { AllowAutoRedirect = false, UseCookies = false })
    {
        Timeout = TimeSpan.FromSeconds(40)
    };

    public LoginReply? Identity { get; private set; }

    public async Task SignInAsync(string email, string password, Func<(string Code, string Method)?> requestMfa,
        CancellationToken cancellation)
    {
        LoginReply login = await SendAsync<LoginReply>(HttpMethod.Post, "auth/login",
            new { Email = email, Password = password }, cancellation);

        if (login.MfaToken is string token && login.AccessToken is null)
        {
            var challenge = requestMfa() ?? throw new OperationCanceledException();
            login = await SendAsync<LoginReply>(HttpMethod.Post, "auth/mfa/verify",
                new { MfaToken = token, challenge.Code, challenge.Method }, cancellation);
        }

        if (string.IsNullOrEmpty(login.AccessToken) || login.UserId <= 0 || string.IsNullOrEmpty(login.Email))
            throw new InvalidOperationException("The server did not return a complete sign-in session.");

        Identity = login;
    }

    public async Task<(string Scope, Dictionary<Guid, SyncNote> Notes)> ReadAllAsync(CancellationToken cancellation)
    {
        int cursor = 0;
        string? scope = null;
        var notes = new Dictionary<Guid, SyncNote>();
        do
        {
            NotePage page = await SendAsync<NotePage>(HttpMethod.Get, $"{Notes}?after={cursor}", null, cancellation);
            string pageScope = JsonSerializer.Serialize(new { origin = origin.AbsoluteUri, page.Tenant,
                page.CompanyId, Identity!.UserId, Identity.Email });
            if (scope is not null && scope != pageScope)
                throw new InvalidOperationException("The company or account changed during sync.");
            scope = pageScope;
            if (page.Items is null)
                throw new JsonException("The server did not include its note list.");
            foreach (SyncNote note in page.Items)
            {
                var id = Validate(note).Id;
                if (notes.ContainsKey(id))
                    throw new JsonException("The server returned the same note twice.");
                notes.Add(id, note);
            }
            if (page.Next is int next && next <= cursor)
                throw new InvalidOperationException("The server returned an invalid sync cursor.");
            cursor = page.Next ?? 0;
        } while (cursor != 0);

        return (scope!, notes);
    }

    public async Task<SyncNote> ReadAsync(Guid id, CancellationToken cancellation) =>
        Validate(await SendAsync<SyncNote>(HttpMethod.Get, $"{Notes}/{id}", null, cancellation), id);

    public async Task<SyncNote> ApplyAsync(SyncNote source, int expectedVersion, CancellationToken cancellation) =>
        Validate(await SendAsync<SyncNote>(HttpMethod.Put, $"{Notes}/{source.Id}",
            new { ExpectedVersion = expectedVersion, source.Note }, cancellation), source.Id);

    internal Task<JsonElement> GetAsync(string path, CancellationToken cancellation) =>
        SendAsync<JsonElement>(HttpMethod.Get, path, null, cancellation);

    private static SyncNote Validate(SyncNote note, Guid? expectedId = null)
    {
        if (note is null || note.Id == Guid.Empty || note.Version <= 0
            || (expectedId.HasValue && expectedId.Value != note.Id)
            || note.Note?.Title is null || note.Note.Content is null || note.Note.Tags is null)
            throw new JsonException("The server returned an invalid note.");
        return note;
    }

    private async Task<T> SendAsync<T>(HttpMethod method, string path, object? body, CancellationToken cancellation)
    {
        using var request = new HttpRequestMessage(method, new Uri(origin, "/api/v1/" + path));
        if (Identity?.AccessToken is string token)
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        if (body is not null)
            request.Content = new StringContent(JsonSerializer.Serialize(body, Json), Encoding.UTF8, "application/json");

        using HttpResponseMessage response = await Http.SendAsync(request, cancellation);
        if (!response.IsSuccessStatusCode)
        {
            if (response.Headers.Contains("X-Suite-Setup-Required"))
                throw new InvalidOperationException($"{origin.Authority} — Complete company setup before syncing.");
            string message = response.StatusCode switch
            {
                HttpStatusCode.Unauthorized => "Sign-in failed or expired.",
                HttpStatusCode.Forbidden => "This account does not have permission for the operation.",
                HttpStatusCode.NotFound => "The sync API or note is unavailable.",
                HttpStatusCode.Conflict => "The note changed while sync was running.",
                (HttpStatusCode)429 => "Too many attempts. Try again later.",
                _ => $"The server returned HTTP {(int)response.StatusCode}."
            };
            throw new ApiResponseException($"{origin.Authority} — {message}", response.StatusCode);
        }

        return JsonSerializer.Deserialize<T>(await response.Content.ReadAsStringAsync(), Json)
            ?? throw new JsonException("The sync response was empty.");
    }
}

internal sealed class NoteSync(NoteApi local, NoteApi remote)
{
    internal sealed record Versions(int Local, int Remote);
    internal sealed record Result(int Uploaded, int Downloaded, int Unavailable, List<NoteConflict> Conflicts);
    private string? stateFile;
    private Dictionary<Guid, Versions> baseline = new();

    public async Task<Result> RunAsync(CancellationToken cancellation)
    {
        var left = await local.ReadAllAsync(cancellation);
        var right = await remote.ReadAllAsync(cancellation);
        using var sha256 = SHA256.Create();
        string key = BitConverter.ToString(sha256.ComputeHash(Encoding.UTF8.GetBytes(
            JsonSerializer.Serialize(new[] { left.Scope, right.Scope })))).Replace("-", "");
        string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Business Suite", "note-sync");
        Directory.CreateDirectory(folder);
        stateFile = Path.Combine(folder, key + ".json");

        // Serialize sync runs from separate desktop windows for this account pair.
        using var syncLock = new FileStream(stateFile + ".lock", FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        Load();
        int uploaded = 0;
        int downloaded = 0;
        int unavailable = 0;
        var conflicts = new List<NoteConflict>();

        foreach (Guid id in left.Notes.Keys.Union(right.Notes.Keys).Union(baseline.Keys).ToArray())
        {
            cancellation.ThrowIfCancellationRequested();
            left.Notes.TryGetValue(id, out SyncNote? a);
            right.Notes.TryGetValue(id, out SyncNote? b);
            baseline.TryGetValue(id, out Versions? previous);
            try
            {
                if (a is null || b is null)
                {
                    // A previously synced note can become shared, linked or otherwise unavailable.
                    // Keep its baseline and do not recreate it on either side.
                    if (previous is not null)
                    {
                        unavailable++;
                    }
                    else if (a is not null && !a.Note.Trashed)
                    {
                        Remember(a, await remote.ApplyAsync(a, 0, cancellation));
                        uploaded++;
                    }
                    else if (b is not null && !b.Note.Trashed)
                    {
                        Remember(await local.ApplyAsync(b, 0, cancellation), b);
                        downloaded++;
                    }
                }
                else if (a.Note.Matches(b.Note))
                {
                    Remember(a, b);
                }
                else
                {
                    string reason = DescribeDifference(a, b, previous);
                    conflicts.Add(new(a, b, reason));
                }
            }
            catch (ApiResponseException error) when (error.StatusCode == HttpStatusCode.Conflict)
            {
                unavailable++;
            }
        }

        return new(uploaded, downloaded, unavailable, conflicts);
    }

    private static string DescribeDifference(SyncNote local, SyncNote remote, Versions? previous)
    {
        if (previous is null)
            return "Versions differ";

        return (local.Version != previous.Local, remote.Version != previous.Remote) switch
        {
            (true, false) => "Changed locally",
            (false, true) => "Changed on server",
            (true, true) => "Changed on both sides",
            _ => "Versions differ"
        };
    }

    public async Task ResolveAsync(NoteConflict conflict, bool keepLocal, CancellationToken cancellation)
    {
        using var syncLock = new FileStream(stateFile! + ".lock", FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        Load();
        SyncNote a = await local.ReadAsync(conflict.Local.Id, cancellation);
        SyncNote b = await remote.ReadAsync(conflict.Remote.Id, cancellation);
        if (a.Version != conflict.Local.Version || b.Version != conflict.Remote.Version)
            throw new InvalidOperationException("The note changed after this conflict was shown. Run sync again.");

        if (keepLocal)
            Remember(a, await remote.ApplyAsync(a, b.Version, cancellation));
        else
            Remember(await local.ApplyAsync(b, a.Version, cancellation), b);
    }

    private void Load()
    {
        baseline = File.Exists(stateFile)
            ? JsonSerializer.Deserialize<Dictionary<Guid, Versions>>(File.ReadAllText(stateFile!))
                ?? throw new JsonException("The saved sync history is empty.")
            : new();
    }

    private void Remember(SyncNote a, SyncNote b)
    {
        var versions = new Versions(a.Version, b.Version);
        if (baseline.TryGetValue(a.Id, out Versions? current) && current == versions)
            return;

        // Only mark equal content as synchronized. If an API normalizes the
        // payload differently, both versions remain available for review.
        if (!a.Note.Matches(b.Note))
            return;
        baseline[a.Id] = versions;
        string temporary = stateFile + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(baseline));
        WindowsCompatibility.ReplaceFile(temporary, stateFile!);
    }
}
