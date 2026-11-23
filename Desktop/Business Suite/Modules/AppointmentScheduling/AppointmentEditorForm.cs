using System.Security.Cryptography;

namespace Business_Suite;

public sealed partial class AppointmentEditorForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly AppointmentKey? key;
    private readonly AppointmentRebookSeed? rebook;
    private readonly DateTime initialStart;
    private readonly CancellationTokenSource lifetime = new();
    private AppointmentRecoveryJournal? journal;
    private FileStream? journalLock;
    private bool saving;
    private bool checking;
    private AppointmentOptions? options;
    private AppointmentDraft? pending;
    private int dealLoadVersion;
    private GroupedScheduleVersion? grouped;
    private GroupedSchedulePreview? groupedPreview;
    private DateTime? resourceStartUtc;
    private int resourceTimeVersion;
    private bool settingResourceTime;
    private bool resourceTimeUnavailable;
    private bool translatingResourceTime;

    public AppointmentEditorForm() => InitializeComponent();

    internal AppointmentEditorForm(AppointmentRepository repository, DateTime date, AppointmentKey? key)
        : this(repository, date, key, null) { }

    internal AppointmentEditorForm(AppointmentRepository repository, DateTime date, AppointmentKey? key,
        AppointmentRebookSeed? rebook) : this()
    {
        this.repository=repository;
        this.key=key;
        this.rebook=rebook;
        startsPicker.Value=date.AddHours(10);
        initialStart = startsPicker.Value;
        if (key is not null)
        {
            heading.Text="Reschedule appointment";
            saveButton.Text="Save schedule";
            projectLabel.Visible=projectBox.Visible=false;
            dealLabel.Visible=dealBox.Visible=false;
            customerBox.Enabled=serviceBox.Enabled=notesBox.Enabled=customerNotesBox.Enabled=walkInBox.Enabled=false;
        }
    }

    internal DateTime? AgendaDate { get; private set; }
    internal int? SavedAppointmentId { get; private set; }

    private async void EditorShown(object sender,EventArgs e)
    {
        if (repository is null)
            return;
        CancellationToken cancellation=lifetime.Token;
        try
        {
            if (key is null)
            {
                journal = repository.RecoveryJournal();
                journalLock = journal.Acquire();
                pending = journal.Read();
            }
            var choices=await repository.OptionsAsync(cancellation);
            var edit=key is null?null:await repository.EditDataAsync(key,cancellation);
            grouped=edit?.Grouped;
            if (grouped is not null)
                heading.Text="Reschedule grouped service";
            if (key is null)
            {
                var projects = await repository.ProjectOptionsAsync(cancellation);
                if (cancellation.IsCancellationRequested)
                    return;
                projects.Insert(0,new AppointmentOption(0,"No project"));
                if (pending?.Project is int recovered && projects.All(option => option.Id != recovered))
                    projects.Add(new AppointmentOption(recovered,$"Project #{recovered}"));
                projectBox.DisplayMember=nameof(AppointmentOption.Name);
                projectBox.ValueMember=nameof(AppointmentOption.Id);
                projectBox.DataSource=projects;
                projectBox.SelectedValue=pending?.Project ?? 0;
            }
            if (cancellation.IsCancellationRequested)
                return;
            options=choices;
            var slot = edit?.Slot ?? pending?.Slot ?? rebook?.Slot;
            if (pending is null && rebook?.ResourceStartUtc.HasValue==true && slot is not null &&
                slot.Extras.Any(id=>choices.Resources.All(resource=>resource.Id!=id)))
                throw new InvalidOperationException("The selected timeline resource is no longer available. Refresh the timeline.");
            Bind(customerBox,choices.Customers,edit?.Customer ?? pending?.Customer ?? rebook?.Customer);
            Bind(serviceBox,choices.Services,edit?.Service ?? pending?.Service ?? rebook?.Service);
            BindProviders(slot?.Provider);
            resourceList.DisplayMember=nameof(AppointmentOption.Name);
            foreach (var option in choices.Resources)
                resourceList.Items.Add(option,slot?.Extras.Contains(option.Id)==true);
            if (slot is not null)
            {
                startsPicker.Value=slot.LocalTime;
                if (slot.Minutes >= durationBox.Minimum && slot.Minutes <= durationBox.Maximum)
                    durationBox.Value=slot.Minutes;
            }
            if (pending is null)
                resourceStartUtc=rebook?.ResourceStartUtc;
            if (pending is not null)
            {
                notesBox.Text = pending.Notes;
                customerNotesBox.Text = pending.CustomerNotes;
                walkInBox.Checked = pending.WalkIn;
                SetRecoveryState();
                return;
            }
            if (choices.Customers.Count==0||choices.Services.Count==0||choices.Providers.Count==0)
            {
                feedback.Text="An active customer, configured service policy and provider are required.";
                return;
            }
            feedback.Text=grouped is not null ? "Check availability before saving the new grouped service schedule." :
                resourceStartUtc.HasValue ? "Resource and time selected. Choose a customer, service and provider." :
                rebook is { Slot: not null, Service: null } ? "Provider time selected. Choose a customer and eligible service." : rebook?.Slot is null
                ? "Availability is checked again when you save. Payment is collected separately."
                : "Repeated as a draft for tomorrow. Review the time, resources and availability.";
            saveButton.Enabled=checkButton.Enabled=true;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                if (pending is not null)
                    SetRecoveryState();
                else if (error is IOException)
                    feedback.Text="Booking recovery is unavailable or another appointment window is open.";
                else
                    feedback.Text=AppointmentsForm.Friendly(error);
            }
        }

    }

    private void SetRecoveryState()
    {
        customerBox.Enabled=serviceBox.Enabled=providerBox.Enabled=startsPicker.Enabled=durationBox.Enabled=
            notesBox.Enabled=customerNotesBox.Enabled=walkInBox.Enabled=resourceList.Enabled=false;
        heading.Text = "Resume booking";
        saveButton.Text = "Retry same booking";
        checkButton.Text = "Check request status";
        saveButton.Enabled = checkButton.Enabled = true;
        CustomerChanged(this, EventArgs.Empty);
        feedback.Text = "A saved booking is awaiting confirmation. Check its status or retry the same request.";
    }

    private void CustomerChanged(object? sender, EventArgs e)
    {
        if (customerContextButton is not null)
            customerContextButton.Enabled = options is not null && key is null && pending is null &&
                !checking && !saving && customerBox.SelectedItem is AppointmentOption;
        UpdateSlotPicker();
    }

    private async void CustomerSelectionChanged(object? sender,EventArgs e)
    {
        CustomerChanged(sender,e);
        if (key is not null || dealBox is null || repository is null)
            return;
        int version = ++dealLoadVersion;
        dealBox.DataSource = null;
        dealBox.Items.Clear();
        dealBox.Enabled = false;
        if (customerBox.SelectedItem is not AppointmentOption customer)
            return;
        try
        {
            var deals = await repository.DealOptionsAsync(customer.Id,lifetime.Token);
            if (lifetime.IsCancellationRequested || version != dealLoadVersion)
                return;
            deals.Insert(0,new AppointmentOption(0,"No linked opportunity"));
            if (pending?.Deal is int recovered && deals.All(option => option.Id != recovered))
                deals.Add(new AppointmentOption(recovered,$"Opportunity #{recovered}"));
            dealBox.DisplayMember=nameof(AppointmentOption.Name);
            dealBox.ValueMember=nameof(AppointmentOption.Id);
            dealBox.DataSource=deals;
            dealBox.SelectedValue=pending?.Deal ?? 0;
            UpdateSlotPicker();
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!lifetime.IsCancellationRequested && version == dealLoadVersion)
                feedback.Text = AppointmentsForm.Friendly(error);
        }
    }

    private void UpdateSlotPicker()
    {
        if (projectBox is not null)
            projectBox.Enabled = key is null && pending is null && !checking && !saving && projectBox.Items.Count > 1;
        if (dealBox is not null)
            dealBox.Enabled = key is null && pending is null && !checking && !saving && dealBox.Items.Count > 1;
        if (slotPickerButton is not null)
            slotPickerButton.Enabled = options is not null && pending is null &&
                !checking && !saving && serviceBox.SelectedItem is AppointmentOption service &&
                options.Eligibility.TryGetValue(service.Id, out var providerIds) &&
                options.Providers.Any(provider => providerIds.Contains(provider.Id));
        if (seriesButton is not null)
        {
            bool recoveringSeries = key is null && repository?.SeriesJournal().HasPending == true;
            seriesButton.Visible = key is null;
            seriesButton.Text = recoveringSeries ? "Resume recurring booking" : "Recurring booking";
            seriesButton.Enabled = key is null && pending is null && !checking && !saving &&
                (recoveringSeries || (SelectedProject is null && SelectedDeal is null && options is not null && customerBox.SelectedItem is AppointmentOption &&
                    serviceBox.SelectedItem is AppointmentOption && providerBox.SelectedItem is AppointmentOption));
        }
    }

    private int? SelectedProject => projectBox?.SelectedValue is int id && id > 0 ? id : null;
    private void ProjectChanged(object? sender,Telerik.WinControls.UI.Data.PositionChangedEventArgs e) => UpdateSlotPicker();
    private int? SelectedDeal => dealBox?.SelectedValue is int id && id > 0 ? id : null;
    private void DealChanged(object? sender,Telerik.WinControls.UI.Data.PositionChangedEventArgs e) => UpdateSlotPicker();

    private void SeriesClicked(object? sender, EventArgs e)
    {
        if (!seriesButton.Enabled || repository is null)
            return;
        AppointmentDraft? draft = null;
        string zone = "";
        if (!repository.SeriesJournal().HasPending &&
            customerBox.SelectedItem is AppointmentOption customer && serviceBox.SelectedItem is AppointmentOption service &&
            providerBox.SelectedItem is AppointmentOption provider)
        {
            draft = new(customer.Id, service.Id, ReadSlot(provider.Id), notesBox.Text.Trim(),
                Guid.NewGuid(), customerNotesBox.Text.Trim(), walkInBox.Checked);
            zone = provider.Zone;
        }
        using var dialog = new AppointmentSeriesForm(repository, draft, zone);
        dialog.ShowDialog(this);
        if (dialog.Saved is not null)
        {
            AgendaDate = dialog.AgendaDate;
            DialogResult = DialogResult.OK;
        }
        UpdateSlotPicker();
    }

    private void SlotPickerClicked(object? sender, EventArgs e)
    {
        if (!slotPickerButton.Enabled || repository is null || serviceBox.SelectedItem is not AppointmentOption service)
            return;
        if (!options!.Eligibility.TryGetValue(service.Id, out var eligible))
            return;
        var providers = options.Providers.Where(provider => eligible.Contains(provider.Id)).ToList();
        var preferred = providerBox.SelectedItem as AppointmentOption ?? providers.FirstOrDefault();
        if (preferred is null)
            return;
        using var picker = new AppointmentSlotPickerForm(repository, service.Id, ReadSlot(preferred.Id), key, providers);
        if (picker.ShowDialog(this) == DialogResult.OK && picker.SelectedStart is DateTime starts &&
            picker.SelectedProvider is int provider)
        {
            BindProviders(provider);
            startsPicker.Value = starts;
            feedback.Text = "Selected time passed the availability check. It will be checked again when you save.";
        }
    }

    private void CustomerContextClicked(object? sender, EventArgs e)
    {
        if (!customerContextButton.Enabled || repository is null || customerBox.SelectedItem is not AppointmentOption customer)
            return;
        int? service = (serviceBox.SelectedItem as AppointmentOption)?.Id;
        int? provider = (providerBox.SelectedItem as AppointmentOption)?.Id;
        var eligible = service is int serviceId && options!.Eligibility.TryGetValue(serviceId, out var ids) ? ids : null;
        bool replace = service.HasValue || startsPicker.Value != initialStart || resourceList.CheckedItems.Count > 0 ||
            notesBox.Text.Length > 0 || customerNotesBox.Text.Length > 0 || walkInBox.Checked;
        using var visits = new AppointmentCustomerContextForm(repository, customer.Id, service, provider, startsPicker.Value, eligible, replace);
        if (visits.ShowDialog(this) != DialogResult.OK)
            return;
        if (visits.RepeatDraft is { } seed)
            ApplyRepeatedVisit(seed);
        else if (visits.SuggestedProvider is int selected)
            BindProviders(selected);
    }

    private void ApplyRepeatedVisit(AppointmentRebookSeed seed)
    {
        serviceBox.SelectedIndex = options!.Services.FindIndex(service => service.Id == seed.Service);
        BindProviders(seed.Slot?.Provider);
        if (seed.Slot is { } slot)
        {
            startsPicker.Value = slot.LocalTime;
            if (slot.Minutes >= durationBox.Minimum && slot.Minutes <= durationBox.Maximum)
                durationBox.Value = slot.Minutes;
        }
        for (int index = 0; index < resourceList.Items.Count; index++)
            resourceList.SetItemChecked(index, seed.Slot?.Extras.Contains(((AppointmentOption)resourceList.Items[index]).Id) == true);
        notesBox.Clear();
        customerNotesBox.Clear();
        walkInBox.Checked = false;
        feedback.Text = "Visit copied into a new draft. Review the time, latest price and availability.";
    }

    private static void Bind(ComboBox control,List<AppointmentOption> choices,int? selected)
    {
        control.DisplayMember=nameof(AppointmentOption.Name);
        control.DataSource=choices;
        control.SelectedIndex=selected.HasValue?choices.FindIndex(choice=>choice.Id==selected):-1;
    }

    private void BindProviders(int? currentProvider)
    {
        if (options is null)
            return;
        var choices=serviceBox.SelectedItem is AppointmentOption service
            && options.Eligibility.TryGetValue(service.Id,out var providers)
            ? options.Providers.Where(provider=>providers.Contains(provider.Id)).ToList() : new List<AppointmentOption>();
        Bind(providerBox,choices,currentProvider);
    }

    private void ServiceChanged(object sender,EventArgs e)
    {
        int? preferred=(providerBox.SelectedItem as AppointmentOption)?.Id;
        if (preferred is null && key is null && pending is null && rebook is { Slot: not null, Service:null } timeline)
            preferred=timeline.Slot.Provider;
        BindProviders(preferred);
        if (key is null && serviceBox.SelectedItem is AppointmentOption service)
            durationBox.Value=service.DefaultMinutes;
        UpdateSlotPicker();
    }

    private async void CheckClicked(object sender,EventArgs e)
    {
        if (!checkButton.Enabled||checking||saving||translatingResourceTime||resourceTimeUnavailable||repository is null)
            return;
        CancellationToken cancellation=lifetime.Token;
        checking=true;
        CustomerChanged(this, EventArgs.Empty);
        checkButton.Enabled=saveButton.Enabled=false;
        try
        {
            groupedPreview=null;
            if (pending is not null)
            {
                if (await repository.ConfirmedRequestAsync(pending,cancellation) is int confirmed)
                {
                    journal!.Clear();
                    Finish(pending.Slot, confirmed);
                }
                else
                    feedback.Text="No confirmed booking was found. You can safely retry the same request.";
                return;
            }
            if (serviceBox.SelectedItem is not AppointmentOption service)
                throw new ArgumentException("Choose a service.");
            var slot = ReadSlot();
            AppointmentQuote quote = key is null
                ? await repository.CheckAsync(service.Id,slot,cancellation)
                : await repository.CheckRescheduleAsync(key,slot,cancellation);
            if (!cancellation.IsCancellationRequested)
            {
                if (grouped is not null)
                {
                    if (quote.Grouped?.Version!=grouped)
                        throw new InvalidOperationException("The service occurrence changed. Reopen the schedule.");
                    groupedPreview=quote.Grouped;
                    feedback.Text="Selected slot is available. Save to update the visit and service occurrence.";
                }
                else
                    feedback.Text=$"Selected slot is available. Estimated service price: {quote.Currency} {quote.Price:N2} before {quote.Tax:N2}% tax.";
            }
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=AppointmentsForm.Friendly(error);
        }
        finally
        {
            checking=false;
            if (!cancellation.IsCancellationRequested && !IsDisposed)
            {
                checkButton.Enabled=saveButton.Enabled=true;
                CustomerChanged(this, EventArgs.Empty);
            }
        }
    }

    private AppointmentSlot ReadSlot()
    {
        if (providerBox.SelectedItem is not AppointmentOption provider)
            throw new ArgumentException("Choose a provider.");
        return ReadSlot(provider.Id);
    }

    private AppointmentSlot ReadSlot(int provider)
    {
        DateTime selected=startsPicker.Value;
        return new AppointmentSlot(new DateTime(selected.Year,selected.Month,selected.Day,selected.Hour,selected.Minute,0),
            (int)durationBox.Value,provider,resourceList.CheckedItems.Cast<AppointmentOption>().Select(item=>item.Id).ToArray());
    }

    private async void ProviderChanged(object sender,EventArgs e)
    {
        timezoneLabel.Text=providerBox.SelectedItem is AppointmentOption provider ? $"Provider timezone: {provider.Zone}" : "Choose a provider";
        UpdateSlotPicker();
        if (resourceStartUtc is not DateTime instant || repository is null || pending is not null)
            return;
        int version=++resourceTimeVersion;
        if (providerBox.SelectedItem is not AppointmentOption selected)
        {
            translatingResourceTime=resourceTimeUnavailable=false;
            RestoreResourceTimeActions();
            return;
        }
        translatingResourceTime=true;
        resourceTimeUnavailable=false;
        saveButton.Enabled=checkButton.Enabled=false;
        try
        {
            var local=await repository.TimelineProviderLocalAsync(instant,selected.Id,lifetime.Token);
            if (version!=resourceTimeVersion || lifetime.IsCancellationRequested)
                return;
            settingResourceTime=true;
            try { startsPicker.Value=local; }
            finally { settingResourceTime=false; }
            feedback.Text="The selected resource time is shown in the provider's timezone.";
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (version==resourceTimeVersion && !lifetime.IsCancellationRequested)
            {
                resourceTimeUnavailable=true;
                feedback.Text=AppointmentsForm.Friendly(error);
            }
        }
        finally
        {
            if (version==resourceTimeVersion && !lifetime.IsCancellationRequested)
            {
                translatingResourceTime=false;
                RestoreResourceTimeActions();
            }
        }
    }

    private void StartsEdited(object? sender,EventArgs e)
    {
        if (settingResourceTime || resourceStartUtc is null)
            return;
        resourceStartUtc=null;
        resourceTimeVersion++;
        translatingResourceTime=resourceTimeUnavailable=false;
        RestoreResourceTimeActions();
    }

    private void RestoreResourceTimeActions()
    {
        if (options is { Customers.Count: >0, Services.Count: >0, Providers.Count: >0 } && !saving && !checking)
            saveButton.Enabled=checkButton.Enabled=!resourceTimeUnavailable && !translatingResourceTime;
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (!saveButton.Enabled||saving||checking||translatingResourceTime||resourceTimeUnavailable||repository is null)
            return;
        CancellationToken cancellation=lifetime.Token;
        saving=true;
        CustomerChanged(this, EventArgs.Empty);
        saveButton.Enabled=checkButton.Enabled=cancelButton.Enabled=false;
        try
        {
            var slot=pending?.Slot ?? ReadSlot();
            if (key is not null)
            {
                if (grouped is null)
                    await repository.RescheduleAsync(key,slot,cancellation);
                else
                {
                    var preview=groupedPreview;
                    if (preview is null || preview.Slot.LocalTime!=slot.LocalTime || preview.Slot.Minutes!=slot.Minutes ||
                        preview.Slot.Provider!=slot.Provider || !preview.Slot.Extras.SequenceEqual(slot.Extras))
                        throw new InvalidOperationException("Check availability for this grouped service schedule before saving.");
                    await repository.RescheduleGroupedAsync(key,preview,cancellation);
                }
            }
            else
            {
                if (pending is null)
                {
                    if (customerBox.SelectedItem is not AppointmentOption customer||serviceBox.SelectedItem is not AppointmentOption service)
                        throw new ArgumentException("Choose a customer and service.");
                    var draft = new AppointmentDraft(customer.Id,service.Id,slot,notesBox.Text.Trim(),Guid.NewGuid(),
                        customerNotesBox.Text.Trim(),walkInBox.Checked,SelectedProject,SelectedDeal);
                    journal!.Save(draft);
                    pending = draft;
                }
                int confirmed = await repository.CreateAsync(pending,cancellation);
                journal!.Clear();
                Finish(slot, confirmed);
                return;
            }
            Finish(slot);
        }
        catch (Exception error) when (AppointmentsForm.IsExpected(error) || error is CryptographicException)
        {
            if (pending is not null && (error is InvalidOperationException or ArgumentException or UnauthorizedAccessException))
            {
                try
                {
                    if (await repository.ConfirmedRequestAsync(pending,cancellation) is null && options is not null)
                    {
                        journal!.Clear();
                        pending=null;
                        providerBox.Enabled=startsPicker.Enabled=durationBox.Enabled=resourceList.Enabled=
                            customerBox.Enabled=serviceBox.Enabled=notesBox.Enabled=customerNotesBox.Enabled=walkInBox.Enabled=true;
                        saveButton.Text="Confirm booking";
                        checkButton.Text="Check availability";
                        heading.Text="New appointment";
                    }
                }
                catch (Exception recoveryError) when (AppointmentsForm.IsExpected(recoveryError)) { }
            }
            if (pending is not null)
                SetRecoveryState();
            else
                feedback.Text=error is CryptographicException or IOException
                    ? "Booking recovery could not be saved. No new request was sent."
                    : AppointmentsForm.Friendly(error);
        }
        finally
        {
            saving=false;
            if (!IsDisposed)
            {
                saveButton.Enabled=cancelButton.Enabled=true;
                checkButton.Enabled=true;
                CustomerChanged(this, EventArgs.Empty);
            }
        }
    }

    private void Finish(AppointmentSlot slot, int? confirmed = null)
    {
        AgendaDate = slot.LocalTime.Date;
        SavedAppointmentId = confirmed;
        saving = checking = false;
        DialogResult = DialogResult.OK;
        Close();
    }

    private void EditorClosing(object sender,FormClosingEventArgs e)=>e.Cancel=saving || checking;
    private void EditorClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
        journalLock?.Dispose();
    }
}
