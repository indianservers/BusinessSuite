using System.Net.Http;
using System.Net;
using System.Text.Json;

namespace Business_Suite;

internal sealed partial class SyncWindow : Form
{
    private readonly NoteApi local = new(new Uri("http://127.0.0.1:15434"));
    private readonly NoteApi remote;
    private readonly NoteSync sync;
    private readonly CancellationTokenSource lifetime = new();
    private bool busy;

    public SyncWindow()
    {
        InitializeComponent();
        remote = new(new Uri("https://localhost"));
        sync = new(local, remote);
        ShowConflict();
    }

    public SyncWindow(Uri website) : this()
    {
        remote = new(website);
        sync = new(local, remote);
        websiteLabel.Text = $"Company website · {website.Authority}";
    }

    private async void Run_Click(object sender, EventArgs e) => await RunAsync();
    private async void Compare_Click(object sender, EventArgs e) => await CompareAsync();
    private async void KeepLocal_Click(object sender, EventArgs e) => await ResolveAsync(true);
    private async void KeepServer_Click(object sender, EventArgs e) => await ResolveAsync(false);
    private void Conflicts_SelectedIndexChanged(object sender, EventArgs e) => ShowConflict();

    private void SyncWindow_FormClosing(object sender, FormClosingEventArgs e)
    {
        if (busy)
        {
            e.Cancel = true;
            lifetime.Cancel();
        }
    }

    private void SyncWindow_FormClosed(object sender, FormClosedEventArgs e) => lifetime.Dispose();

    private async Task RunAsync()
    {
        if (!CredentialsReady())
            return;

        conflicts.Items.Clear();
        await WithStatusAsync("Signing in and comparing notes…", async cancellation =>
        {
            await SignInBothAsync(cancellation);

            status.Text = "Copying new notes and checking existing versions…";
            NoteSync.Result result = await sync.RunAsync(cancellation);
            foreach (NoteConflict conflict in result.Conflicts)
                conflicts.Items.Add(conflict);
            if (conflicts.Items.Count > 0)
                conflicts.SelectedIndex = 0;
            status.Text = $"{result.Uploaded} uploaded · {result.Downloaded} downloaded · {result.Conflicts.Count} to review";
            if (result.Unavailable > 0)
                status.Text += $" · {result.Unavailable} unavailable or changed during sync";
        });
    }

    private async Task CompareAsync()
    {
        if (!CredentialsReady())
            return;

        await WithStatusAsync("Reading business records from both installations…", async cancellation =>
        {
            await SignInBothAsync(cancellation);
            ComparisonResult result = await BusinessComparison.CompareAsync(local, remote, cancellation);
            using var preview = new BusinessComparisonWindow(result);
            preview.ShowDialog(this);
            status.Text = "Business records comparison complete.";
        });
    }

    private bool CredentialsReady()
    {
        bool ready = (local.Identity is not null || localEmail.Text.Trim().Length > 0 && localPassword.Text.Length > 0)
            && (remote.Identity is not null || remoteEmail.Text.Trim().Length > 0 && remotePassword.Text.Length > 0);
        if (!ready)
            status.Text = "Enter the email and password for both accounts.";
        return ready;
    }

    private async Task SignInBothAsync(CancellationToken cancellation)
    {
        await SignInAsync(local, localEmail, localPassword, "Local workspace", cancellation);
        await SignInAsync(remote, remoteEmail, remotePassword, "Company website", cancellation);
        if (!string.Equals(local.Identity!.Email, remote.Identity!.Email, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Use the same email on both accounts. Close this window to sign in again.");
    }

    private async Task SignInAsync(NoteApi api, TextBox email, TextBox password, string source,
        CancellationToken cancellation)
    {
        if (api.Identity is not null)
            return;
        await api.SignInAsync(email.Text.Trim(), password.Text, () => AskForMfa(source), cancellation);
        password.Clear();
        email.Enabled = password.Enabled = false;
    }

    private (string Code, string Method)? AskForMfa(string source)
    {
        using var dialog = new VerificationForm { Text = $"{source} verification" };
        return dialog.ShowDialog(this) == DialogResult.OK && dialog.Code.Length > 0
            ? (dialog.Code, dialog.Method)
            : null;
    }

    private async Task ResolveAsync(bool useLocal)
    {
        if (conflicts.SelectedItem is not NoteConflict conflict)
            return;

        await WithStatusAsync("Applying the selected version…", async cancellation =>
        {
            await sync.ResolveAsync(conflict, useLocal, cancellation);
            conflicts.Items.Remove(conflict);
            if (conflicts.Items.Count > 0)
                conflicts.SelectedIndex = 0;
            status.Text = conflicts.Items.Count > 0
                ? $"Version applied. {conflicts.Items.Count} changes still need review."
                : "Version applied. All changes have been reviewed.";
        });
    }

    private async Task WithStatusAsync(string message, Func<CancellationToken, Task> work)
    {
        busy = true;
        run.Enabled = compare.Enabled = conflicts.Enabled = false;
        ShowConflict();
        status.Text = message;
        try
        {
            await work(lifetime.Token);
        }
        catch (OperationCanceledException)
        {
            status.Text = "Sync canceled or timed out. Run sync again to continue.";
        }
        catch (ApiResponseException error) when (error.StatusCode == HttpStatusCode.Unauthorized)
        {
            status.Text = error.Message + " Reopen Sync to sign in again if the session expired.";
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException
            or HttpRequestException or InvalidOperationException or JsonException)
        {
            status.Text = error.Message;
        }
        finally
        {
            busy = false;
            if (lifetime.IsCancellationRequested)
                Close();
            else
            {
                run.Enabled = compare.Enabled = conflicts.Enabled = true;
                ShowConflict();
            }
        }
    }

    private void ShowConflict()
    {
        NoteConflict? selection = conflicts.SelectedItem as NoteConflict;
        localPreview.Text = Describe(selection?.Local.Note);
        serverPreview.Text = Describe(selection?.Remote.Note);
        keepLocal.Enabled = keepServer.Enabled = !busy && selection is not null;
    }

    private static string Describe(NoteContent? note)
    {
        if (note is null)
            return "";
        string labels = string.Join(", ", new[]
        {
            note.Trashed ? "In trash" : "Active", note.Archived ? "Archived" : "",
            note.Pinned ? "Pinned" : "", note.Favorite ? "Favorite" : ""
        }.Where(value => value.Length != 0));
        return $"{note.Title}\r\n{labels}\r\n{string.Join(", ", note.Tags)}\r\n\r\n{note.Content}";
    }

}
