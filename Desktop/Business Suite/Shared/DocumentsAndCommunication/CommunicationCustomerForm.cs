using Npgsql;

namespace Business_Suite;

public sealed partial class CommunicationCustomerForm : Form
{
    private readonly CommunicationCustomerRepository? repository;
    private bool busy;
    private bool canAdd;
    private readonly Dictionary<int, string> draftNotes = new();
    private int? activeRecipient;
    private CommunicationCustomerRow? Customer => customerGrid.CurrentRow?.DataBoundItem as CommunicationCustomerRow;

    public CommunicationCustomerForm() => InitializeComponent();

    internal CommunicationCustomerForm(CommunicationCustomerRepository repository) : this() => this.repository = repository;

    private async void RefreshClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy)
            return;
        await RunAsync(async () =>
        {
            var customers = await repository.CustomersAsync(searchBox.Text);
            if (IsDisposed)
                return;
            customerGrid.DataSource = customers;
            await LoadNotesAsync();
        });
    }

    private async void CustomerChanged(object? sender, EventArgs e)
    {
        if (repository is null || busy)
            return;
        await RunAsync(LoadNotesAsync);
    }

    private async Task LoadNotesAsync()
    {
        canAdd = false;
        notesGrid.DataSource = null;
        notePreview.Clear();
        activeRecipient = Customer?.Id;
        noteBox.Text = activeRecipient is int id && draftNotes.TryGetValue(id, out string? draft) ? draft : "";
        assigneeList.DataSource = null;
        followUpCheck.Checked = false;
        followUpPicker.Value = DateTime.Now.AddDays(1);
        if (repository is null || Customer is not { } customer)
        {
            statusLabel.Text = "No customers match the search.";
            return;
        }
        var notes = await repository.NotesAsync(customer.Id);
        if (IsDisposed)
            return;
        notesGrid.DataSource = notes.Rows;
        assigneeList.DataSource = new[] { new CommunicationNoteAssignee(0, "Unassigned") }
            .Concat(notes.Assignees).ToList();
        assigneeList.SelectedIndex = 0;
        canAdd = notes.CanAdd;
        statusLabel.Text = notes.Rows.Count == 0 ? "No internal notes for this customer."
            : $"Showing {notes.Rows.Count:N0} latest internal notes.";
    }

    private async void AddNoteClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy || !canAdd || Customer is not { } customer)
            return;
        await RunAsync(async () =>
        {
            int? assignee = assigneeList.SelectedValue is int id && id > 0 ? id : null;
            DateTimeOffset? followUp = null;
            if (followUpCheck.Checked)
            {
                var time = DateTime.SpecifyKind(followUpPicker.Value, DateTimeKind.Unspecified);
                if (TimeZoneInfo.Local.IsInvalidTime(time) || TimeZoneInfo.Local.IsAmbiguousTime(time))
                    throw new ArgumentException("Choose an unambiguous follow-up time in this workstation's time zone.");
                followUp = new DateTimeOffset(time, TimeZoneInfo.Local.GetUtcOffset(time));
            }
            await repository.AddNoteAsync(customer.Id, noteBox.Text, assignee, followUp);
            if (IsDisposed)
                return;
            draftNotes.Remove(customer.Id);
            noteBox.Clear();
            await LoadNotesAsync();
            if (!IsDisposed)
                statusLabel.Text = "Internal note saved.";
        });
    }

    private void EmailHistoryClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy || Customer is not { } customer)
            return;
        using var history = new CommunicationDeliveryForm(repository, customer.Id);
        history.ShowDialog(this);
    }

    private async void ProcessRemindersClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy || !canAdd)
            return;
        await RunAsync(async () =>
        {
            int count = await repository.ProcessOwnDueRemindersAsync();
            if (IsDisposed)
                return;
            await LoadNotesAsync();
            if (!IsDisposed)
                statusLabel.Text = count == 0 ? "No eligible reminders are due for your notes."
                    : $"Created {count:N0} in-app {(count == 1 ? "reminder" : "reminders")} for your notes.";
        });
    }

    private void MyRemindersClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy)
            return;
        using var history = new CommunicationDeliveryForm(repository);
        history.ShowDialog(this);
    }

    private void EmailPreferencesClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy || Customer is not { } customer)
            return;
        using var preferences = new CommunicationEmailPreferencesForm(repository, customer.Id);
        preferences.ShowDialog(this);
    }

    private async Task RunAsync(Func<Task> operation)
    {
        busy = true;
        UpdateButtons();
        try
        {
            await operation();
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException
            or InvalidOperationException or ArgumentException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException
                    ? "Could not complete the request. Refresh customer history to check the saved state."
                    : error.Message;
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
                UpdateButtons();
        }
    }

    private void NoteSelectionChanged(object? sender, EventArgs e)
    {
        if (notesGrid.CurrentRow?.DataBoundItem is not CommunicationCustomerNote note)
        {
            notePreview.Clear();
            return;
        }
        var details = new List<string>();
        if (note.Assignee.Length > 0)
            details.Add($"Assigned to {note.Assignee}");
        if (note.FollowUp is DateTime time)
            details.Add($"Follow-up {time:g}" + (note.Reminded ? " · Reminder processed" : ""));
        notePreview.Text = details.Count == 0 ? note.Body : string.Join(" · ", details) + Environment.NewLine + note.Body;
    }

    private void FollowUpChanged(object? sender, EventArgs e) => UpdateButtons();

    private void NoteTextChanged(object? sender, EventArgs e)
    {
        if (activeRecipient is int id)
        {
            if (noteBox.Text.Length == 0)
                draftNotes.Remove(id);
            else
                draftNotes[id] = noteBox.Text;
        }
        UpdateButtons();
    }

    private void UpdateButtons()
    {
        refreshButton.Enabled = customerGrid.Enabled = !busy;
        emailHistoryButton.Enabled = !busy && Customer is not null;
        emailPreferencesButton.Enabled = emailHistoryButton.Enabled;
        remindersButton.Enabled = !busy && canAdd;
        myRemindersButton.Enabled = !busy && repository is not null;
        noteBox.Enabled = !busy && canAdd;
        assigneeList.Enabled = followUpCheck.Enabled = !busy && canAdd;
        followUpPicker.Enabled = !busy && canAdd && followUpCheck.Checked;
        addButton.Enabled = !busy && canAdd && !string.IsNullOrWhiteSpace(noteBox.Text);
    }
}
