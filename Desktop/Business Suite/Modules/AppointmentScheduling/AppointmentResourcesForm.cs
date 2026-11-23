using System.Data;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class AppointmentResourcesForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly CancellationTokenSource lifetime=new();
    private AppointmentResourcePage? page;
    private AppointmentKey? editing;
    private Guid request;
    private int? retainedEmployee;
    private bool retainedProvider;
    private bool editorOpen;
    private bool busy;
    internal bool Changed { get; private set; }

    public AppointmentResourcesForm() => InitializeComponent();
    internal AppointmentResourcesForm(AppointmentRepository repository) : this() => this.repository=repository;

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private RadCheckBox[] Days => [dayMon,dayTue,dayWed,dayThu,dayFri,daySat,daySun];
    private bool Provider => type.SelectedIndex is >=0 and <=5;
    private async void ResourcesLoaded(object? sender,EventArgs e) => await RunAsync(ReloadAsync);
    private async void RefreshClicked(object? sender,EventArgs e) => await RunAsync(ReloadAsync);
    private void CloseClicked(object? sender,EventArgs e) => Close();
    private void PoliciesClicked(object? sender,EventArgs e)
    {
        if (repository is null || !policies.Enabled)
            return;
        using var panel=new AppointmentPolicyForm(repository);
        panel.ShowDialog(this);
        Changed|=panel.Changed;
    }
    private void ResourceTypeChanged(object? sender,Telerik.WinControls.UI.Data.PositionChangedEventArgs e)
    {
        if (Provider) capacity.Value=1;
        UpdateActions();
    }
    private void SelectionChanged(object sender,CurrentRowChangedEventArgs e) => UpdateActions();

    private async Task ReloadAsync()
    {
        var next=await repository!.ReadAppointmentResourcesAsync(lifetime.Token);
        if (lifetime.IsCancellationRequested)
            return;
        page=next;
        editorOpen=false;
        grid.DataSource=next.Rows.DefaultView;
        zone.DataSource=next.Zones;
        status.Text=next.Rows.Rows.Count==0 ? "No scheduling resources in this branch." : "Select a resource or add a new one.";
    }

    private void AddClicked(object? sender,EventArgs e)
    {
        if (page?.CanCreate!=true || busy)
            return;
        editing=null;
        retainedEmployee=null;
        retainedProvider=false;
        request=Guid.NewGuid();
        editorOpen=true;
        Fill("","room","active",new JsonObject());
        UpdateActions();
    }

    private void OpenClicked(object? sender,EventArgs e)
    {
        if (page?.CanEdit!=true || busy || Selected is not DataRow row)
            return;
        try
        {
            var metadata=JsonNode.Parse(row.Field<string>("metadata")!)!.AsObject();
            retainedEmployee=metadata["employee_id"]?.GetValue<int>();
            editing=new AppointmentKey(row.Field<int>("id"),row.Field<int>("revision"));
            request=Guid.Empty;
            editorOpen=true;
            Fill(row.Field<string>("title")!,row.Field<string>("resource_type")!,row.Field<string>("status")!,metadata);
            retainedProvider=Provider;
            UpdateActions();
        }
        catch (Exception error) when (error is JsonException or InvalidOperationException or FormatException or ArgumentException)
        {
            editorOpen=false;
            status.Text="The stored resource configuration requires review.";
            UpdateActions();
        }
    }

    private void Fill(string name,string kind,string resourceStatus,JsonObject metadata)
    {
        resourceName.Text=name;
        type.SelectedIndex=type.FindStringExact(kind);
        state.SelectedIndex=state.FindStringExact(resourceStatus);
        capacity.Value=metadata["capacity"]?.GetValue<int>() ?? 1;
        zone.SelectedIndex=zone.FindStringExact(metadata["timezone"]?.ToString() ?? "Asia/Kolkata");
        if (zone.SelectedIndex<0)
            zone.SelectedIndex=zone.FindStringExact("Asia/Kolkata");
        var people=new List<AppointmentOption>{new(0,"Choose an HRMS employee")};
        people.AddRange(page!.Employees);
        if (retainedEmployee is int retained && people.All(person=>person.Id!=retained))
            people.Add(new AppointmentOption(retained,$"Employee #{retained}"));
        employee.DisplayMember=nameof(AppointmentOption.Name);
        employee.ValueMember=nameof(AppointmentOption.Id);
        employee.DataSource=people;
        employee.SelectedValue=retainedEmployee ?? 0;
        opens.Value=DateTime.Today+ReadTime("opens","09:00");
        closes.Value=DateTime.Today+ReadTime("closes","19:00");
        var checkedDays=metadata["weekdays"]?.Deserialize<int[]>() ?? [0,1,2,3,4,5];
        for (int day=0;day<Days.Length;day++) Days[day].Checked=checkedDays.Contains(day);
        color.SelectedIndex=color.FindStringExact(metadata["assigned_color"]?.ToString() ?? "Lavender");
        location.Text=metadata["location"]?.ToString() ?? "";
        access.Text=metadata["accessibility"]?.ToString() ?? "";
        facilities.Text=metadata["facilities"]?.ToString() ?? "";
        status.Text=editing is null ? "New resource" : "Editing resource #"+editing.Id;

        TimeSpan ReadTime(string key,string fallback) =>
            TimeSpan.FromMinutes((int)TimeSpan.Parse(metadata[key]?.ToString() ?? fallback,CultureInfo.InvariantCulture).TotalMinutes);
    }

    private async void SaveClicked(object? sender,EventArgs e)
    {
        if (!save.Enabled)
            return;
        int? employeeId=editing is not null ? retainedEmployee :
            Provider && employee.SelectedValue is int chosen && chosen>0 ? chosen : null;
        var draft=new AppointmentResourceDraft(resourceName.Text,type.Text,state.Text,(int)capacity.Value,zone.Text,
            Days.Select((box,index)=>new {box.Checked,index}).Where(day=>day.Checked).Select(day=>day.index).ToArray(),
            RoundTime(opens.Value),RoundTime(closes.Value),location.Text,access.Text,facilities.Text,color.Text,employeeId,request);
        await RunAsync(async () =>
        {
            await repository!.SaveAppointmentResourceAsync(editing,draft,lifetime.Token);
            Changed=true;
            await ReloadAsync();
            status.Text="Resource saved.";
        });
    }

    private static TimeSpan RoundTime(DateTime value) => new(value.Hour,value.Minute,0);

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy=true;
        UpdateActions();
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!lifetime.IsCancellationRequested)
                status.Text=AppointmentsForm.Friendly(error);
        }
        finally
        {
            busy=false;
            if (!IsDisposed) UpdateActions();
        }
    }

    private void UpdateActions()
    {
        add.Enabled=!busy && page?.CanCreate==true;
        open.Enabled=!busy && page?.CanEdit==true && Selected is not null;
        refresh.Enabled=!busy;
        policies.Enabled=!busy && page is not null;
        bool canEdit=!busy && editorOpen;
        resourceName.Enabled=state.Enabled=zone.Enabled=opens.Enabled=closes.Enabled=color.Enabled=
            location.Enabled=access.Enabled=facilities.Enabled=save.Enabled=canEdit;
        foreach (var day in Days) day.Enabled=canEdit;
        type.Enabled=canEdit && !retainedProvider;
        capacity.Enabled=canEdit && !Provider;
        employee.Enabled=canEdit && editing is null && Provider;
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        base.OnFormClosed(e);
    }
}
