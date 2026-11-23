using Npgsql;

namespace Business_Suite;

public sealed partial class CommunicationDeliveryForm : Form
{
    private readonly Func<string, bool, Task<List<CommunicationDeliveryRow>>>? load;
    private readonly CommunicationCustomerRepository? reminders;
    private bool busy;

    public CommunicationDeliveryForm() => InitializeComponent();

    internal CommunicationDeliveryForm(CommunicationDeliveryRepository delivery) : this()
    {
        channelFilter.Visible = deliveryStatus.Visible = true;
        load = (search, issues) => delivery.ListFilteredAsync(search, issues, channelFilter.SelectedValue as string ?? "",
            deliveryStatus.SelectedValue as string ?? "");
    }

    internal CommunicationDeliveryForm(CommunicationCustomerRepository customers) : this()
    {
        Text = "My customer reminders";
        searchBox.NullText = "Search customer reminders";
        searchBox.AccessibleName = "Search customer reminders";
        detailLabel.Text = "Reminder details";
        detailBox.AccessibleName = "Selected reminder details";
        issuesCheck.Text = "Unread only";
        markReadButton.Visible = markAllReadButton.Visible = true;
        reminders = customers;
        load = customers.ReminderHistoryAsync;
    }

    internal CommunicationDeliveryForm(CommunicationCustomerRepository customers, int recipient) : this()
    {
        Text = "Customer email history";
        load = async (search, issues) =>
        {
            var messages = await customers.EmailHistoryAsync(recipient);
            var term = search.Trim();
            return messages
                .Where(row => !issues || row.Status is "failed" or "blocked" or "reconciliation_required")
                .Where(row => term.Length == 0 || $"{row.Subject} {row.Body} {row.Status} {row.Direction}"
                    .IndexOf(term, StringComparison.OrdinalIgnoreCase) >= 0)
                .Select(row => new CommunicationDeliveryRow(row.Subject, $"{row.Direction} email",
                    "Customer communications", row.Status, row.Recorded, row.Body)).ToList();
        };
    }

    private async void RefreshClicked(object? sender, EventArgs e) => await RefreshAsync();

    private async Task RefreshAsync(string? notice = null)
    {
        if (load is null || busy)
            return;
        busy = true;
        UpdateActions();
        deliveryGrid.DataSource = null;
        detailBox.Clear();
        statusLabel.Text = "Loading records…";
        try
        {
            var rows = await load(searchBox.Text, issuesCheck.Checked);
            if (IsDisposed)
                return;
            deliveryGrid.DataSource = rows;
            string count = rows.Count switch
            {
                0 => "No records match the filters.",
                250 or 300 => $"Showing {rows.Count:N0} matching records. Refine the search for specific records.",
                _ => $"{rows.Count:N0} matching {(reminders is null ? "delivery records" : "reminders")}."
            };
            statusLabel.Text = notice is null ? count : $"{notice} {count}";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is UnauthorizedAccessException or InvalidOperationException
                    ? error.Message : "Could not load records from PostgreSQL.";
        }
        finally
        {
            if (!IsDisposed)
            {
                busy = false;
                UpdateActions();
            }
        }
    }

    private void SelectionChanged(object? sender, EventArgs e)
    {
        detailBox.Text = deliveryGrid.CurrentRow?.DataBoundItem is CommunicationDeliveryRow row
            ? (row.Detail.Length == 0 ? "No additional details were recorded." : row.Detail) : "";
        UpdateActions();
    }

    private CommunicationDeliveryRow? SelectedReminder => deliveryGrid.CurrentRow?.DataBoundItem as CommunicationDeliveryRow;

    private void UpdateActions()
    {
        refreshButton.Enabled = issuesCheck.Enabled = channelFilter.Enabled = deliveryStatus.Enabled = !busy;
        markReadButton.Enabled = !busy && reminders is not null &&
            SelectedReminder is { ReminderId: not null, Status: "Unread" };
        markAllReadButton.Enabled = !busy && reminders is not null;
    }

    private async void MarkReadClicked(object? sender, EventArgs e)
    {
        if (SelectedReminder is { ReminderId: int id, Status: "Unread" })
            await MarkReadAsync(id);
    }

    private async void MarkAllReadClicked(object? sender, EventArgs e) => await MarkReadAsync(null);

    private async Task MarkReadAsync(int? id)
    {
        if (reminders is null || busy)
            return;
        busy = true;
        UpdateActions();
        int count;
        try
        {
            count = await reminders.MarkRemindersReadAsync(id);
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is UnauthorizedAccessException or InvalidOperationException
                    ? error.Message : "Could not update reminder read status in PostgreSQL.";
            return;
        }
        finally
        {
            if (!IsDisposed)
            {
                busy = false;
                UpdateActions();
            }
        }
        if (!IsDisposed)
            await RefreshAsync(count == 0 ? "No unread reminders were updated." : $"Marked {count:N0} read.");
    }
}
