using System.Data;
using System.Text.Json;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class AppointmentPolicyForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly CancellationTokenSource lifetime=new();
    private ServiceBookingPolicyPage? page;
    private int? editingService;
    private int? revision;
    private bool busy;
    internal bool Changed { get; private set; }

    public AppointmentPolicyForm() => InitializeComponent();
    internal AppointmentPolicyForm(AppointmentRepository repository) : this() => this.repository=repository;

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private async void PolicyLoaded(object? sender,EventArgs e) => await RunAsync(ReloadAsync);
    private async void RefreshClicked(object? sender,EventArgs e) => await RunAsync(ReloadAsync);
    private void CloseClicked(object? sender,EventArgs e) => Close();
    private void EligibilityClicked(object? sender,EventArgs e)
    {
        if (repository is null || busy || Selected?.Field<int?>("id") is not int policy)
            return;
        using var specialists=new AppointmentEligibilityForm(repository,policy);
        specialists.ShowDialog(this);
        Changed|=specialists.Changed;
    }
    private void SelectionChanged(object sender,CurrentRowChangedEventArgs e) => UpdateActions();

    private async Task ReloadAsync()
    {
        var next=await repository!.ReadBookingPoliciesAsync(lifetime.Token);
        if (lifetime.IsCancellationRequested) return;
        page=next;
        editingService=null;
        grid.DataSource=next.Rows.DefaultView;
        status.Text=next.Rows.Rows.Count==0 ? "No available services in this branch." : "Open a service to review or configure its booking policy.";
    }

    private void EditClicked(object? sender,EventArgs e)
    {
        if (busy || Selected is not DataRow row) return;
        try
        {
            revision=row.Field<int?>("revision");
            service.Text=row.Field<string>("title") ?? "";
            minimum.Value=row.Field<int?>("min_duration_minutes") ?? 15;
            defaultMinutes.Value=row.Field<int?>("default_duration_minutes") ?? 30;
            maximum.Value=row.Field<int?>("max_duration_minutes") ?? 120;
            active.Checked=row.Field<bool?>("active") ?? true;
            required.Checked=row.Field<bool?>("booking_required") ?? true;
            overrides.Checked=row.Field<bool?>("allow_duration_override") ?? false;
            categories.Text=string.Join(Environment.NewLine,JsonSerializer.Deserialize<string[]>(row.Field<string>("categories") ?? "[]") ?? []);
            var assets=JsonSerializer.Deserialize<string[]>(row.Field<string>("assets") ?? "[]") ?? [];
            room.Checked=assets.Contains("room");
            chair.Checked=assets.Contains("chair");
            equipment.Checked=assets.Contains("equipment");
            location.Checked=assets.Contains("location");
            editingService=row.Field<int>("service");
            status.Text=revision.HasValue ? "Editing policy revision "+revision : "No saved policy. Confirm the desired booking rules.";
        }
        catch (Exception error) when (error is JsonException or InvalidOperationException or ArgumentException)
        {
            editingService=null;
            status.Text="The stored service configuration requires review.";
        }
        UpdateActions();
    }

    private async void SaveClicked(object? sender,EventArgs e)
    {
        if (!save.Enabled || editingService is not int id) return;
        var assets=new List<string>();
        if (room.Checked) assets.Add("room");
        if (chair.Checked) assets.Add("chair");
        if (equipment.Checked) assets.Add("equipment");
        if (location.Checked) assets.Add("location");
        var policy=new ServiceBookingPolicyDraft(id,revision,(int)defaultMinutes.Value,(int)minimum.Value,(int)maximum.Value,
            active.Checked,required.Checked,overrides.Checked,
            categories.Text.Split(new[]{'\r','\n'},StringSplitOptions.RemoveEmptyEntries).Where(value=>!string.IsNullOrWhiteSpace(value)).ToArray(),
            assets.ToArray());
        await RunAsync(async () =>
        {
            await repository!.SaveBookingPolicyAsync(policy,lifetime.Token);
            Changed=true;
            await ReloadAsync();
            status.Text="Service booking policy saved.";
        });
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy) return;
        busy=true;
        UpdateActions();
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!lifetime.IsCancellationRequested) status.Text=AppointmentsForm.Friendly(error);
        }
        finally
        {
            busy=false;
            if (!IsDisposed) UpdateActions();
        }
    }

    private void UpdateActions()
    {
        edit.Enabled=!busy && Selected is not null;
        refresh.Enabled=!busy;
        eligibility.Enabled=!busy && Selected?.Field<int?>("id") is int;
        bool allowed=!busy && editingService.HasValue && page?.CanSave==true;
        save.Enabled=minimum.Enabled=defaultMinutes.Enabled=maximum.Enabled=active.Enabled=required.Enabled=overrides.Enabled=
            categories.Enabled=room.Enabled=chair.Enabled=equipment.Enabled=location.Enabled=allowed;
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        base.OnFormClosed(e);
    }
}
