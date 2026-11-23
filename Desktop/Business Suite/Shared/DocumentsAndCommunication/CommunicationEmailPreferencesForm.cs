using Npgsql;

namespace Business_Suite;

public sealed partial class CommunicationEmailPreferencesForm : Form
{
    private readonly CommunicationCustomerRepository? repository;
    private readonly int recipient;
    private readonly CancellationTokenSource lifetime = new();
    private CustomerEmailPreferences? current;
    private bool busy;

    public CommunicationEmailPreferencesForm() => InitializeComponent();

    internal CommunicationEmailPreferencesForm(CommunicationCustomerRepository repository, int recipient) : this()
    {
        this.repository = repository;
        this.recipient = recipient;
    }

    private CustomerEmailConsent Values => new(transactional.Checked, marketing.Checked, greeting.Checked);

    private async void RefreshClicked(object? sender, EventArgs e) => await RefreshAsync(null);

    private async Task RefreshAsync(string? message)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        var cancellation = lifetime.Token;
        try
        {
            var value = await repository.EmailPreferencesAsync(recipient, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            current = value;
            heading.Text = value.Name;
            address.Text = string.IsNullOrEmpty(value.Email) ? "No email address on file" : value.Email;
            transactional.Checked = value.Consent.Transactional;
            marketing.Checked = value.Consent.Marketing;
            greeting.Checked = value.Consent.Greeting;
            sourceBox.Clear();
            recent.Text = value.Recorded is DateTime date ? $"Last recorded {date:g} · {value.Source}" : "No consent evidence recorded.";
            feedback.Text = message ?? (value.CanEdit
                ? (value.CanOptIn ? "Record consent separately for each email purpose." : "Your access permits opt-outs only.")
                : "Your access permits viewing these preferences.");
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                current = null;
                feedback.Text = Friendly(error);
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                busy = false;
                UpdateActions();
            }
        }
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (repository is null || !saveButton.Enabled || current is not { } value)
            return;
        var cancellation = lifetime.Token;
        busy = true;
        UpdateActions();
        bool saved = false;
        feedback.Text = "Saving email preferences…";
        try
        {
            await repository.SaveEmailPreferencesAsync(recipient, value.Revision, Values, sourceBox.Text, cancellation);
            saved = true;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text = Friendly(error);
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                busy = false;
                UpdateActions();
            }
        }
        if (saved && !cancellation.IsCancellationRequested)
            await RefreshAsync("Email preferences saved.");
    }

    private void InputChanged(object? sender, EventArgs e) => UpdateActions();

    private void UpdateActions()
    {
        if (saveButton is null)
            return;
        bool edit = !busy && current?.CanEdit == true;
        bool optIn = current?.CanOptIn == true && !string.IsNullOrWhiteSpace(current.Email);
        transactional.Enabled = edit && (optIn || current!.Consent.Transactional);
        marketing.Enabled = edit && (optIn || current!.Consent.Marketing);
        greeting.Enabled = edit && (optIn || current!.Consent.Greeting);
        sourceBox.Enabled = edit;
        refreshButton.Enabled = !busy;
        saveButton.Enabled = edit && Values != current!.Consent && !string.IsNullOrWhiteSpace(sourceBox.Text);
    }

    private static bool IsExpected(Exception error) => error is NpgsqlException or TimeoutException
        or UnauthorizedAccessException or InvalidOperationException or ArgumentException;

    private static string Friendly(Exception error) => error is NpgsqlException or TimeoutException
        ? "Could not read or save email preferences in PostgreSQL." : error.Message;

    private void ClosedPreferences(object? sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
