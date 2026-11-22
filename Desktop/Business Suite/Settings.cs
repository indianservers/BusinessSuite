using System.Net.Http;
using System.Text.Json;

namespace Business_Suite;

public partial class Settings : Form
{
    private static readonly string LocalLauncher = Path.Combine(AppContext.BaseDirectory, "Start Local Workspace.cmd");
    private static readonly Color Canvas = Color.FromArgb(243, 246, 251);
    private static readonly Color Navy = Color.FromArgb(18, 27, 49);
    private static readonly Color Ink = Color.FromArgb(24, 35, 58);
    private static readonly Color Muted = Color.FromArgb(84, 100, 124);
    private static readonly Color Blue = Color.FromArgb(47, 79, 217);
    private static readonly Color PaleBlue = Color.FromArgb(233, 239, 255);

    private readonly RadioButton remote = new();
    private readonly RadioButton local = new();
    private readonly CueTextBox address = new();
    private readonly Label addressLabel = new();
    private readonly Label addressHint = new();
    private readonly Label status = new();
    private readonly Button test = new();
    private readonly Button save = new();
    private ConnectionSettings draft = new();
    private bool editingLocal;
    private bool updatingAddress;
    private CancellationTokenSource? connectionCheck;

    public Settings()
    {
        InitializeComponent();
        SuspendLayout();
        BackColor = Canvas;
        ForeColor = Ink;
        Font = new Font("Segoe UI", 10);
        BuildLayout();

        string? loadError = null;
        try
        {
            draft = ConnectionSettings.Load();
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException)
        {
            loadError = "Saved settings could not be read. Enter your server address to continue.";
        }

        remote.CheckedChanged += (_, _) => { if (remote.Checked) ShowMode(false); };
        local.CheckedChanged += (_, _) => { if (local.Checked) ShowMode(true); };
        address.TextChanged += (_, _) => { if (!updatingAddress) ClearFeedback(); };
        test.Click += async (_, _) => await TestConnectionAsync();
        save.Click += (_, _) => SaveSettings();
        FormClosed += (_, _) => connectionCheck?.Cancel();
        AcceptButton = save;

        if (draft.UseLocal)
            local.Checked = true;
        else
            remote.Checked = true;

        if (loadError is not null)
            SetStatus(loadError, Color.Firebrick);

        ResumeLayout(false);
    }

    private void BuildLayout()
    {
        var sidebar = new Panel { BackColor = Navy, Bounds = new Rectangle(0, 0, 234, 620) };
        Controls.Add(sidebar);

        var mark = new Label { BackColor = Blue, ForeColor = Color.White, Text = "BS",
            TextAlign = ContentAlignment.MiddleCenter, Font = new Font("Segoe UI Semibold", 12),
            Bounds = new Rectangle(24, 32, 42, 42) };
        sidebar.Controls.Add(mark);
        AddLabel(sidebar, "Business Suite", 78, 32, 148, 24, 12, Color.White, true);
        AddLabel(sidebar, "Desktop", 79, 57, 130, 20, 9, Color.FromArgb(172, 189, 220));
        var selected = new Panel { BackColor = Color.FromArgb(35, 49, 80),
            Bounds = new Rectangle(16, 121, 202, 46) };
        sidebar.Controls.Add(selected);
        selected.Controls.Add(new Panel { BackColor = Color.FromArgb(124, 151, 255),
            Bounds = new Rectangle(0, 0, 3, 46) });
        AddLabel(selected, "Company Settings", 16, 11, 174, 26, 10, Color.White, true);

        AddLabel(this, "Company Settings", 274, 36, 620, 48, 29, Ink, true);
        AddLabel(this, "Choose how this desktop app connects to your Business Suite server.",
            277, 90, 620, 28, 11, Muted);

        var card = new Panel { BackColor = Color.White, Bounds = new Rectangle(274, 143, 626, 350) };
        Controls.Add(card);
        AddLabel(card, "Server connection", 26, 22, 570, 36, 18, Ink, true);
        AddLabel(card, "Connection mode", 26, 72, 570, 24, 10, Ink, true);
        ConfigureMode(card, remote, "Remote", 26);
        ConfigureMode(card, local, "Local", 322);
        AddLabel(card, "Hosted company website", 26, 151, 276, 23, 9, Muted);
        AddLabel(card, "Server on this PC or network", 322, 151, 276, 23, 9, Muted);

        ConfigureLabel(addressLabel, card, "", 26, 197, 574, 24, 10, Ink, true);
        address.SetBounds(26, 228, 574, 32);
        address.Font = new Font("Segoe UI", 13);
        address.MaxLength = 2048;
        address.AccessibleName = "Server address";
        card.Controls.Add(address);
        ConfigureLabel(addressHint, card, "", 26, 269, 574, 23, 9, Muted);
        ConfigureLabel(status, card, "", 26, 304, 574, 36, 9, Muted);
        status.AccessibleRole = AccessibleRole.StaticText;

        if (File.Exists(LocalLauncher))
        {
            var open = new Button();
            ConfigureButton(open, "Open local workspace", 274, 526, 166, false);
            open.Click += (_, _) => WorkspaceForm.OpenPage(this, "/");

            var sync = new Button();
            ConfigureButton(sync, "Sync", 450, 526, 94, false);
            sync.Click += (_, _) => OpenSync();
        }

        ConfigureButton(test, "Test connection", 552, 526, 166, false);
        ConfigureButton(save, "Save settings", 734, 526, 166, true);
    }

    private static void ConfigureMode(Control parent, RadioButton button, string text, int left)
    {
        button.SetBounds(left, 103, 278, 43);
        button.Appearance = Appearance.Button;
        button.FlatStyle = FlatStyle.Flat;
        button.FlatAppearance.BorderColor = Color.FromArgb(208, 218, 236);
        button.FlatAppearance.CheckedBackColor = PaleBlue;
        button.Cursor = Cursors.Hand;
        button.Text = text;
        button.TextAlign = ContentAlignment.MiddleCenter;
        parent.Controls.Add(button);
    }

    private void ConfigureButton(Button button, string text, int x, int y, int width, bool primary)
    {
        button.SetBounds(x, y, width, 44);
        button.Text = text;
        button.Font = new Font("Segoe UI Semibold", 10);
        button.BackColor = primary ? Blue : Color.White;
        button.ForeColor = primary ? Color.White : Ink;
        button.FlatStyle = FlatStyle.Flat;
        button.FlatAppearance.BorderSize = primary ? 0 : 1;
        button.FlatAppearance.BorderColor = Color.FromArgb(208, 218, 236);
        button.Cursor = Cursors.Hand;
        Controls.Add(button);
    }

    private static void AddLabel(Control parent, string text, int x, int y, int width,
        int height, float size, Color color, bool bold = false)
    {
        ConfigureLabel(new Label(), parent, text, x, y, width, height, size, color, bold);
    }

    private static void ConfigureLabel(Label label, Control parent, string text, int x, int y,
        int width, int height, float size, Color color, bool bold = false)
    {
        label.SetBounds(x, y, width, height);
        label.Text = text;
        label.Font = new Font(bold ? "Segoe UI Semibold" : "Segoe UI", size);
        label.ForeColor = color;
        label.TextAlign = ContentAlignment.MiddleLeft;
        parent.Controls.Add(label);
    }

    private void OpenSync()
    {
        try
        {
            Uri website = ConnectionSettings.ParseOrigin(CaptureDraft().RemoteAddress, local: false);
            using var window = new SyncWindow(website);
            window.ShowDialog(this);
        }
        catch (FormatException)
        {
            remote.Checked = true;
            SetStatus("Enter your company website to sync or compare records.", Color.Firebrick);
            address.Focus();
        }
    }

    private void ShowMode(bool useLocal)
    {
        if (addressLabel.Text.Length != 0)
            draft = CaptureDraft();

        editingLocal = useLocal;
        updatingAddress = true;
        addressLabel.Text = useLocal ? "Local server address" : "Company website";
        address.PlaceholderText = useLocal ? "http://localhost:1534" : "suite.yourcompany.com";
        address.Text = useLocal ? draft.LocalAddress : draft.RemoteAddress;
        addressHint.Text = useLocal
            ? "Use localhost for this PC or enter your local network server address."
            : "Enter the company website where Business Suite is hosted.";
        updatingAddress = false;
        ClearFeedback();
    }

    private ConnectionSettings CaptureDraft() => editingLocal
        ? draft with { UseLocal = true, LocalAddress = address.Text }
        : draft with { UseLocal = false, RemoteAddress = address.Text };

    private bool TryGetSettings(out ConnectionSettings settings)
    {
        settings = CaptureDraft();
        try
        {
            string origin = settings.ServerOrigin.GetLeftPart(UriPartial.Authority);
            settings = editingLocal
                ? settings with { LocalAddress = origin }
                : settings with { RemoteAddress = origin };
            return true;
        }
        catch (FormatException error)
        {
            SetStatus(error.Message, Color.Firebrick);
            address.Focus();
            return false;
        }
    }

    private void SaveSettings()
    {
        ClearFeedback();
        if (!TryGetSettings(out ConnectionSettings settings))
            return;

        try
        {
            settings.Save();
            draft = settings;
            updatingAddress = true;
            address.Text = settings.ServerOrigin.GetLeftPart(UriPartial.Authority);
            updatingAddress = false;
            SetStatus("Connection settings saved for this Windows user.", Color.DarkGreen);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            SetStatus("Settings could not be saved. Check your Windows profile permissions.", Color.Firebrick);
        }
    }

    private async Task TestConnectionAsync()
    {
        ClearFeedback();
        if (!TryGetSettings(out ConnectionSettings settings))
            return;

        using var check = new CancellationTokenSource();
        connectionCheck = check;
        test.Enabled = false;
        SetStatus("Checking the server and its database…", Muted);
        try
        {
            bool healthy = await settings.CheckHealthAsync(check.Token);
            if (!check.IsCancellationRequested)
            {
                SetStatus(healthy ? "Connected. The server and database are ready."
                    : "The server responded, but its database is unavailable.",
                    healthy ? Color.DarkGreen : Color.Firebrick);
            }
        }
        catch (OperationCanceledException)
        {
            if (!check.IsCancellationRequested)
                SetStatus("The connection timed out. Check the address and try again.", Color.Firebrick);
        }
        catch (HttpRequestException error)
        {
            if (!check.IsCancellationRequested)
            {
                SetStatus(error is ApiResponseException response
                    ? $"The server returned HTTP {(int)response.StatusCode}."
                    : "Could not connect. Check the address and make sure the server is running.", Color.Firebrick);
            }
        }
        catch (JsonException)
        {
            if (!check.IsCancellationRequested)
                SetStatus("This address did not return a Business Suite health response.", Color.Firebrick);
        }
        finally
        {
            if (ReferenceEquals(connectionCheck, check))
            {
                connectionCheck = null;
                if (!IsDisposed)
                    test.Enabled = true;
            }
        }
    }

    private void ClearFeedback()
    {
        connectionCheck?.Cancel();
        connectionCheck = null;
        test.Enabled = true;
        SetStatus("", Muted);
    }

    private void SetStatus(string text, Color color)
    {
        status.ForeColor = color;
        status.Text = text;
        status.AccessibilityObject.Name = text;
    }
}
