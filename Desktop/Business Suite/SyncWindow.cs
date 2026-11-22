using System.Net.Http;
using System.Net;
using System.Text.Json;

namespace Business_Suite;

internal sealed class SyncWindow : Form
{
    private readonly NoteApi local = new(new Uri("http://127.0.0.1:15434"));
    private readonly NoteApi remote;
    private readonly NoteSync sync;
    private readonly CueTextBox localEmail = new();
    private readonly CueTextBox localPassword = new();
    private readonly CueTextBox remoteEmail = new();
    private readonly CueTextBox remotePassword = new();
    private readonly Button run = new();
    private readonly Button compare = new();
    private readonly Button keepLocal = new();
    private readonly Button keepServer = new();
    private readonly ListBox conflicts = new();
    private readonly TextBox localPreview = new();
    private readonly TextBox serverPreview = new();
    private readonly Label status = new();
    private readonly CancellationTokenSource lifetime = new();
    private bool busy;

    public SyncWindow(Uri website)
    {
        remote = new(website);
        sync = new(local, remote);
        Text = "Business Suite | Sync and compare";
        StartPosition = FormStartPosition.CenterParent;
        AutoScaleDimensions = new SizeF(96, 96);
        AutoScaleMode = AutoScaleMode.Dpi;
        ClientSize = new Size(870, 648);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        BackColor = Color.FromArgb(243, 246, 251);
        ForeColor = Color.FromArgb(24, 35, 58);
        Font = new Font("Segoe UI", 10);

        LabelAt("Sync personal notes", 24, 18, 810, 40, 22);
        LabelAt("Copy new standalone private notes. Review changes before replacing an existing note.",
            25, 63, 810, 24);
        LabelAt("Local workspace", 24, 106, 394, 25, 12);
        LabelAt($"Company website · {website.Authority}", 452, 106, 394, 25, 12);
        Input(localEmail, "Local email", 24, 136);
        Input(localPassword, "Local password", 24, 173, true);
        Input(remoteEmail, "Company email", 452, 136);
        Input(remotePassword, "Company password", 452, 173, true);
        ButtonAt(run, "Sync notes", 696, 214, 150, primary: true);
        status.SetBounds(24, 215, 650, 39);
        status.TextAlign = ContentAlignment.MiddleLeft;
        status.Text = "Start the local workspace before signing in and syncing.";
        Controls.Add(status);
        LabelAt("Changes to review", 24, 269, 822, 24, 12);
        conflicts.SetBounds(24, 301, 822, 86);
        conflicts.AccessibleName = "Notes with conflicts";
        Controls.Add(conflicts);
        LabelAt("Local version", 24, 394, 394, 24);
        LabelAt("Server version", 452, 394, 394, 24);
        Preview(localPreview, "Local note version", 24);
        Preview(serverPreview, "Server note version", 452);

        ButtonAt(keepLocal, "Keep local version", 490, 584, 166);
        ButtonAt(keepServer, "Keep server version", 670, 584, 176);
        ButtonAt(compare, "Compare business records", 24, 584, 232);
        run.Click += async (_, _) => await RunAsync();
        compare.Click += async (_, _) => await CompareAsync();
        keepLocal.Click += async (_, _) => await ResolveAsync(true);
        keepServer.Click += async (_, _) => await ResolveAsync(false);
        conflicts.SelectedIndexChanged += (_, _) => ShowConflict();
        AcceptButton = run;
        FormClosing += (_, args) =>
        {
            if (busy)
            {
                args.Cancel = true;
                lifetime.Cancel();
            }
        };
        FormClosed += (_, _) => lifetime.Dispose();
        ShowConflict();
    }

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
        using var dialog = new Form
        {
            Text = $"{source} verification", StartPosition = FormStartPosition.CenterParent,
            ClientSize = new Size(410, 156), FormBorderStyle = FormBorderStyle.FixedDialog,
            MaximizeBox = false, MinimizeBox = false, Font = Font
        };
        var code = new CueTextBox { Bounds = new Rectangle(18, 16, 374, 30), AccessibleName = "Verification code",
            PlaceholderText = "Verification code", UseSystemPasswordChar = true, MaxLength = 128 };
        var recovery = new CheckBox { Text = "Use a recovery code", Bounds = new Rectangle(18, 53, 374, 28) };
        var verify = new Button { Text = "Verify", Bounds = new Rectangle(278, 95, 114, 40), DialogResult = DialogResult.OK };
        dialog.Controls.AddRange([code, recovery, verify]);
        dialog.AcceptButton = verify;
        return dialog.ShowDialog(this) == DialogResult.OK && code.Text.Trim().Length > 0
            ? (code.Text.Trim(), recovery.Checked ? "recovery" : "totp")
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

    private void LabelAt(string text, int x, int y, int width, int height, float fontSize = 10)
    {
        Controls.Add(new Label { Text = text, Bounds = new Rectangle(x, y, width, height),
            Font = new Font(fontSize > 10 ? "Segoe UI Semibold" : "Segoe UI", fontSize) });
    }

    private void Input(CueTextBox field, string label, int x, int y, bool password = false)
    {
        field.SetBounds(x, y, 394, 32);
        field.AccessibleName = label;
        field.PlaceholderText = label;
        field.UseSystemPasswordChar = password;
        field.MaxLength = password ? 128 : 254;
        Controls.Add(field);
    }

    private void Preview(TextBox field, string label, int x)
    {
        field.SetBounds(x, 421, 394, 146);
        field.AccessibleName = label;
        field.Multiline = true;
        field.ReadOnly = true;
        field.ScrollBars = ScrollBars.Vertical;
        Controls.Add(field);
    }

    private void ButtonAt(Button field, string text, int x, int y, int width, bool primary = false)
    {
        field.Text = text;
        field.SetBounds(x, y, width, 42);
        field.FlatStyle = FlatStyle.Flat;
        field.BackColor = primary ? Color.FromArgb(47, 79, 217) : Color.White;
        field.ForeColor = primary ? Color.White : ForeColor;
        Controls.Add(field);
    }
}
