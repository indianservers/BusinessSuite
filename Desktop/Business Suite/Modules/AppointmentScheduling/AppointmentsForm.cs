using Telerik.WinControls.UI;
using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class AppointmentsForm : Form
{
    private static readonly string[] Stages = ["", "booked", "checked_in", "in_service", "completed", "cancelled", "no_show"];
    private static readonly string[] Destination = ["checked_in", "in_service", "completed", "cancelled", "no_show"];
    private readonly AppointmentRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private bool ready;
    private bool busy;
    private bool clearingFilters;
    private bool canCreate;
    private bool canEdit;
    private bool canViewBilling;

    public AppointmentsForm()
    {
        InitializeComponent();
        statusFilter.SelectedIndex = 0;
        actionBox.SelectedIndex = 0;
    }

    internal AppointmentsForm(DesktopDatabaseSettings settings) : this() => repository = new(settings);

    private DataRow? Selected => (appointmentsGrid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void AgendaShown(object sender, EventArgs e)
    {
        ready = true;
        await OpenTodayAsync();
    }

    private void AgendaClosed(object sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }

    private async void FilterChanged(object sender, EventArgs e)
    {
        if (!clearingFilters)
            await ReloadAsync();
    }

    private async void ClearFiltersClicked(object? sender, EventArgs e)
    {
        if (busy)
            return;
        clearingFilters = true;
        try
        {
            agendaSearch.Clear();
            statusFilter.SelectedIndex = 0;
            providerFilter.SelectedValue = 0;
            assetFilter.SelectedValue = 0;
            serviceFilter.SelectedValue = "";
        }
        finally
        {
            clearingFilters = false;
        }
        await ReloadAsync();
    }
    private async void RefreshClicked(object sender, EventArgs e) => await ReloadAsync();
    private async void AgendaSearchKeyDown(object? sender, KeyEventArgs e)
    {
        if (e.KeyCode != Keys.Enter)
            return;
        e.SuppressKeyPress = true;
        await ReloadAsync();
    }

    private int AgendaStep => weekCheck.Checked ? 7 : 1;

    private void PreviousDateClicked(object? sender, EventArgs e) => MoveAgenda(-AgendaStep);
    private void NextDateClicked(object? sender, EventArgs e) => MoveAgenda(AgendaStep);

    private void MoveAgenda(int days)
    {
        var next = agendaDate.Value.Date.AddDays(days);
        if (!busy && next >= agendaDate.MinDate.Date && next <= agendaDate.MaxDate.Date)
            agendaDate.Value = next;
    }

    private async void TodayDateClicked(object? sender, EventArgs e) => await OpenTodayAsync();

    private async Task OpenTodayAsync()
    {
        if (busy || repository is null)
            return;
        busy = true;
        UpdateActions();
        var cancellation = lifetime.Token;
        feedback.Text = "Loading the agenda date…";
        try
        {
            DateTime today = await repository.AgendaTodayAsync(cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            agendaDate.Value = today;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { return; }
        catch (Exception error) when (IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text = Friendly(error);
            return;
        }
        finally
        {
            busy = false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
        await ReloadAsync();
    }

    private void SelectionChanged(object sender, EventArgs e) => UpdateActions();

    private void WaitlistClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy)
            return;
        using var dialog = new AppointmentWaitlistForm(repository, canCreate);
        dialog.ShowDialog(this);
    }

    private async void NewClicked(object sender, EventArgs e)
    {
        if (await OpenEditorAsync(null) is int saved)
            await ShowConfirmationAsync(saved);
    }

    private async void RescheduleClicked(object sender, EventArgs e)
    {
        if (rescheduleButton.Enabled && Selected is DataRow row)
            await OpenEditorAsync(Key(row));
    }

    private async Task<int?> OpenEditorAsync(AppointmentKey? key, AppointmentRebookSeed? rebook = null)
    {
        if (repository is null || busy || (key is null ? !canCreate : !canEdit))
            return null;
        using var form = new AppointmentEditorForm(repository, agendaDate.Value.Date, key, rebook);
        var result = form.ShowDialog(this);
        UpdateActions();
        if (result == DialogResult.OK)
        {
            if (form.AgendaDate is DateTime date)
                agendaDate.Value = date;
            await ReloadAsync();
            return form.SavedAppointmentId;
        }
        return null;
    }

    private async void TransitionClicked(object sender, EventArgs e)
    {
        if (!transitionButton.Enabled || Selected is not DataRow row || repository is null)
            return;
        string target = Destination[actionBox.SelectedIndex];
        CancellationToken cancellation = lifetime.Token;
        busy = true;
        UpdateActions();
        try
        {
            await repository.TransitionAsync(Key(row), target, reasonBox.Text.Trim(), cancellation);
            if (!cancellation.IsCancellationRequested)
                reasonBox.Clear();
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { return; }
        catch (Exception error) when (IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text = Friendly(error);
            return;
        }
        finally
        {
            busy = false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }

        if (!cancellation.IsCancellationRequested)
            await ReloadAsync();
    }

    private async Task ReloadAsync()
    {
        if (!ready || busy || repository is null)
            return;
        CancellationToken cancellation = lifetime.Token;
        busy = true;
        UpdateActions();
        feedback.Text = "Loading the agenda…";
        try
        {
            int provider = providerFilter.SelectedValue is int providerId ? providerId : 0;
            int asset = assetFilter.SelectedValue is int assetId ? assetId : 0;
            AppointmentPage result = await repository.FilterAgendaAsync(agendaDate.Value.Date, weekCheck.Checked,
                Stages[statusFilter.SelectedIndex], agendaSearch.Text, provider, asset, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            canCreate = result.CanCreate;
            canEdit = result.CanEdit;
            canViewBilling = result.CanViewBilling;
            bool providerAvailable = BindAgendaResources(providerFilter, result.Providers, "All providers", provider);
            bool assetAvailable = BindAgendaResources(assetFilter, result.Assets, "All resources", asset);
            string service = serviceFilter.SelectedValue as string ?? "";
            var services = result.Rows.Rows.Cast<DataRow>().Select(row => row.Field<string>("service"))
                .Where(name => !string.IsNullOrEmpty(name)).Cast<string>();
            if (service.Length != 0)
                services = services.Append(service);
            serviceFilter.DataSource = new[] { new AgendaServiceChoice("", "All services") }
                .Concat(services.Distinct(StringComparer.Ordinal).OrderBy(name => name)
                    .Select(name => new AgendaServiceChoice(name, name))).ToList();
            serviceFilter.SelectedValue = service;
            var visible = result.Rows;
            if (service.Length != 0)
            {
                visible = result.Rows.Clone();
                foreach (DataRow row in result.Rows.Rows)
                    if (string.Equals(row.Field<string>("service"), service, StringComparison.Ordinal))
                        visible.ImportRow(row);
            }
            appointmentsGrid.DataSource = visible;
            if (!providerAvailable || !assetAvailable)
            {
                feedback.Text = "A selected filter is no longer available. Apply the updated filters to refresh.";
                return;
            }
            feedback.Text = visible.Rows.Count == 0 ? "No appointments in this agenda." :
                $"{visible.Rows.Count:N0} appointments · {visible.Rows[0]["timezone"]}";
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                canCreate = canEdit = false;
                appointmentsGrid.DataSource = null;
                feedback.Text = Friendly(error);
            }
        }
        finally
        {
            busy = false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    private sealed record AgendaServiceChoice(string Service, string Label);

    private static bool BindAgendaResources(RadDropDownList filter, List<AppointmentOption> available, string all, int selected)
    {
        bool valid = selected == 0 || available.Any(option => option.Id == selected);
        filter.DataSource = new List<AppointmentOption> { new(0, all) }.Concat(available).ToList();
        filter.SelectedValue = valid ? selected : 0;
        return valid;
    }

    private void HistoryClicked(object sender, EventArgs e)
    {
        if (busy || repository is null || Selected is not DataRow row)
            return;
        using var dialog = new AppointmentHistoryForm(repository, Key(row).Id);
        dialog.ShowDialog(this);
    }

    private async void ConfirmationClicked(object sender, EventArgs e)
    {
        if (!busy && Selected is DataRow row)
            await ShowConfirmationAsync(Key(row).Id);
    }

    private async void BillingClicked(object? sender,EventArgs e)
    {
        if (repository is null || !billingButton.Enabled || Selected is not DataRow row)
            return;
        using var billing = new AppointmentBillingForm(repository,Key(row).Id);
        billing.ShowDialog(this);
        if (billing.Changed)
            await ReloadAsync();
    }

    private async void ResourcesClicked(object? sender,EventArgs e)
    {
        if (repository is null || !resourcesButton.Enabled)
            return;
        using var resources=new AppointmentResourcesForm(repository);
        resources.ShowDialog(this);
        if (resources.Changed)
            await ReloadAsync();
    }

    private async void TimelineClicked(object? sender,EventArgs e)
    {
        if (repository is null || !timelineButton.Enabled)
            return;
        using var timeline=new AppointmentTimelineForm(repository,agendaDate.Value.Date,weekCheck.Checked);
        if (timeline.ShowDialog(this)!=DialogResult.OK)
            return;
        if (timeline.ExistingBooking is int existing)
            await ShowConfirmationAsync(existing);
        else if (timeline.NewBooking is { } seed && await OpenEditorAsync(null,seed) is int saved)
            await ShowConfirmationAsync(saved);
    }

    private async Task ShowConfirmationAsync(int id)
    {
        if (repository is null)
            return;
        while (!IsDisposed)
        {
            using var dialog = new AppointmentConfirmationForm(repository, id, canCreate);
            if (dialog.ShowDialog(this) != DialogResult.OK || dialog.NewBooking is not { } seed ||
                await OpenEditorAsync(null, seed) is not int saved)
                return;
            id = saved;
        }
    }

    private void UpdateActions()
    {
        clearFilters.Enabled = serviceFilter.Enabled = providerFilter.Enabled = assetFilter.Enabled = agendaSearch.Enabled = agendaDate.Enabled = weekCheck.Enabled = statusFilter.Enabled = refreshButton.Enabled = !busy;
        previousDate.Enabled = !busy && agendaDate.Value.Date.AddDays(-AgendaStep) >= agendaDate.MinDate.Date;
        nextDate.Enabled = !busy && agendaDate.Value.Date.AddDays(AgendaStep) <= agendaDate.MaxDate.Date;
        todayDate.Enabled = !busy && repository is not null;
        newButton.Enabled = !busy && canCreate;
        waitlistButton.Enabled = ready && !busy && repository is not null;
        resourcesButton.Enabled = ready && !busy && repository is not null;
        timelineButton.Enabled = ready && !busy && repository is not null;
        newButton.Text = canCreate && repository?.RecoveryJournal().HasPending == true
            ? "Resume booking" : "New appointment";
        DataRow? row = Selected;
        historyButton.Enabled = !busy && row is not null;
        confirmationButton.Enabled = historyButton.Enabled;
        billingButton.Enabled = historyButton.Enabled && canViewBilling;
        string status = Convert.ToString(row?["status"]) ?? "";
        rescheduleButton.Enabled = !busy && canEdit && status == "booked" && row?["can_reschedule"] is true;
        string target = actionBox.SelectedIndex < 0 ? "" : Destination[actionBox.SelectedIndex];
        bool allowed = status switch
        {
            "booked" => target is "checked_in" or "cancelled" ||
                (target == "no_show" && row?["starts_at"] is DateTime start && start <= DateTime.UtcNow),
            "checked_in" => target is "in_service" or "cancelled",
            "in_service" => target == "completed",
            _ => false
        };
        actionBox.Enabled = !busy && canEdit && row is not null;
        reasonBox.Enabled = actionBox.Enabled && (target is "cancelled" or "no_show");
        transitionButton.Enabled = actionBox.Enabled && allowed && (!reasonBox.Enabled || reasonBox.Text.Trim().Length>0);
    }

    private static AppointmentKey Key(DataRow row) => new((int)row["id"],(int)row["revision"]);
    internal static bool IsExpected(Exception error) => error is InvalidOperationException or ArgumentException or
        UnauthorizedAccessException or NpgsqlException or IOException or TimeoutException or FormatException or JsonException;
    internal static string Friendly(Exception error) => error is InvalidOperationException or UnauthorizedAccessException or ArgumentException
        ? error.Message : "Could not complete the appointment operation. Check scheduling data and PostgreSQL.";
}
