using Npgsql;

namespace Business_Suite;

public sealed partial class AppointmentWaitlistForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly bool canCreate;
    private AppointmentOptions? options;
    private WaitlistDraft? pending;
    private bool busy;
    private bool binding;

    public AppointmentWaitlistForm() => InitializeComponent();

    internal AppointmentWaitlistForm(AppointmentRepository repository, bool canCreate) : this()
    {
        this.repository = repository;
        this.canCreate = canCreate;
        from.Value = DateTime.Today;
        until.Value = DateTime.Today.AddDays(7);
        opens.Value = DateTime.Today.AddHours(9);
        closes.Value = DateTime.Today.AddHours(17);
    }

    private async void ShownList(object? sender, EventArgs e) => await RunAsync(async () =>
    {
        if (canCreate)
        {
            var journal = repository!.WaitlistJournal();
            using (journal.Acquire())
                pending = journal.Read();
            options = await repository.OptionsAsync(default);
            binding = true;
            Fill(customer, options.Customers, pending?.Customer);
            Fill(service, options.Services, pending?.Service);
            FillProvider(pending?.Provider);
            foreach (var resource in options.Resources)
                resources.Items.Add(resource, pending?.Resources.Contains(resource.Id) == true);
            if (pending is { } saved)
            {
                from.Value = saved.From;
                until.Value = saved.Until;
                opens.Value = DateTime.Today + saved.Opens;
                closes.Value = DateTime.Today + saved.Closes;
                flexibleProvider.Checked = saved.FlexibleProvider;
                flexibleResources.Checked = saved.FlexibleResources;
                notes.Text = saved.Notes;
            }
            binding = false;
        }
        await LoadListAsync();
    });

    private void ServiceChanged(object? sender, EventArgs e)
    {
        if (!binding)
            FillProvider(null);
    }

    private void FillProvider(int? selected)
    {
        if (options is null)
            return;
        var available = service.SelectedItem is AppointmentOption item && options.Eligibility.TryGetValue(item.Id, out var eligible)
            ? options.Providers.Where(provider => eligible.Contains(provider.Id)) : Enumerable.Empty<AppointmentOption>();
        Fill(provider, available.Prepend(new AppointmentOption(0, "No preferred provider")), selected ?? 0);
    }

    private void ProviderChanged(object? sender, EventArgs e) =>
        zoneLabel.Text = "Timezone: " + (provider.SelectedItem is AppointmentOption { Id: > 0 } option ? option.Zone : "UTC");

    private static void Fill(ComboBox box, IEnumerable<AppointmentOption> choices, int? selected)
    {
        box.Items.Clear();
        box.Items.AddRange(choices.Cast<object>().ToArray());
        box.SelectedItem = box.Items.Cast<AppointmentOption>().FirstOrDefault(item => item.Id == selected);
    }

    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(LoadListAsync);

    private async Task LoadListAsync()
    {
        var list = await repository!.WaitlistAsync(default);
        grid.DataSource = list;
        feedback.Text = pending is not null ? "The previous request is retained. Retry the original save to recover it."
            : list.Count == 0 ? "No waiting preferences in this branch." : $"Showing {list.Count} waiting preference(s).";
    }

    private async void SaveClicked(object? sender, EventArgs e) => await RunAsync(async () =>
    {
        if (!canCreate)
            return;
        var journal = repository!.WaitlistJournal();
        using (journal.Acquire())
        {
            pending = journal.Read();
            if (pending is null)
            {
                if (customer.SelectedItem is not AppointmentOption buyer || service.SelectedItem is not AppointmentOption offering)
                    throw new ArgumentException("Select a customer and a scheduled service.");
                var specialist = provider.SelectedItem is AppointmentOption { Id: > 0 } option ? option : null;
                pending = new(Guid.NewGuid(), buyer.Id, offering.Id, from.Value.Date, until.Value.Date,
                    TimeSpan.FromMinutes(opens.Value.Hour * 60 + opens.Value.Minute),
                    TimeSpan.FromMinutes(closes.Value.Hour * 60 + closes.Value.Minute),
                    specialist?.Zone ?? "UTC", specialist?.Id,
                    resources.CheckedItems.Cast<AppointmentOption>().Select(item => item.Id).ToArray(),
                    flexibleProvider.Checked, flexibleResources.Checked, notes.Text.Trim());
                try { journal.Save(pending); }
                catch { pending = null; throw; }
            }
            try
            {
                int saved = await repository.SaveWaitlistAsync(pending, default);
                journal.Clear();
                pending = null;
                await LoadListAsync();
                feedback.Text = $"Waitlist preference #{saved} saved. No slot was reserved.";
            }
            catch (Exception error) when (error is ArgumentException or UnauthorizedAccessException or InvalidOperationException)
            {
                journal.Clear();
                pending = null;
                throw;
            }
        }
    });

    private async void CancelClicked(object? sender, EventArgs e)
    {
        if (grid.CurrentRow?.DataBoundItem is not WaitlistEntry entry || !canCreate || pending is not null)
            return;
        await RunAsync(async () =>
        {
            await repository!.CancelWaitlistAsync(entry.Id, entry.Revision, default);
            await LoadListAsync();
            feedback.Text = $"Waitlist preference #{entry.Id} cancelled.";
        });
    }

    private async void CheckClicked(object? sender, EventArgs e) => await RunAsync(async () =>
    {
        var journal = repository!.WaitlistJournal();
        using (journal.Acquire())
        {
            pending = journal.Read();
            if (pending is null)
            {
                await LoadListAsync();
                return;
            }
            if (await repository.CheckWaitlistAsync(pending, default) is not int saved)
            {
                feedback.Text = "No saved request was found. Retry the original request.";
                return;
            }
            journal.Clear();
            pending = null;
            await LoadListAsync();
            feedback.Text = $"Verified saved waitlist preference #{saved}.";
        }
    });

    private void SelectionChanged(object? sender, EventArgs e) => UpdateActions();

    private async Task RunAsync(Func<Task> action)
    {
        if (busy || repository is null)
            return;
        busy = true;
        feedback.Text = "Checking waitlist preferences…";
        UpdateActions();
        try
        {
            await action();
        }
        catch (IOException)
        {
            feedback.Text = "Local recovery storage is unavailable. Reopen the waitlist before retrying.";
        }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            feedback.Text = pending is not null && error is NpgsqlException or TimeoutException
                ? "Save outcome could not be confirmed. Retry the original request."
                : AppointmentsForm.Friendly(error);
        }
        finally
        {
            busy = false;
            UpdateActions();
        }
    }

    private void UpdateActions()
    {
        bool editable = !busy && canCreate && options is not null && pending is null;
        entryPanel.Enabled = editable;
        saveButton.Enabled = editable || (!busy && canCreate && pending is not null);
        checkButton.Visible = pending is not null;
        checkButton.Enabled = !busy && pending is not null;
        saveButton.Text = pending is null ? "Save waitlist preference" : "Retry original request";
        cancelButton.Enabled = !busy && canCreate && pending is null && grid.CurrentRow?.DataBoundItem is WaitlistEntry;
        refreshButton.Enabled = !busy;
    }

    private void ClosingList(object? sender, FormClosingEventArgs e) => e.Cancel = busy;
}
