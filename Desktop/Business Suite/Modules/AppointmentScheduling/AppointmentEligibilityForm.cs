using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class AppointmentEligibilityForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly int policy;
    private readonly CancellationTokenSource lifetime=new();
    private AppointmentEligibilityPage? page;
    private bool busy;
    internal bool Changed {get;private set;}

    public AppointmentEligibilityForm()=>InitializeComponent();
    internal AppointmentEligibilityForm(AppointmentRepository repository,int policy):this()
    {
        this.repository=repository;
        this.policy=policy;
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private async void EligibilityLoaded(object? sender,EventArgs e)=>await RunAsync(ReloadAsync);
    private async void RefreshClicked(object? sender,EventArgs e)=>await RunAsync(ReloadAsync);
    private async void ActivateClicked(object? sender,EventArgs e)=>await ChangeAsync(true);
    private async void DisableClicked(object? sender,EventArgs e)=>await ChangeAsync(false);
    private void CloseClicked(object? sender,EventArgs e)=>Close();
    private void SelectionChanged(object sender,CurrentRowChangedEventArgs e)=>UpdateActions();

    private async Task ReloadAsync()
    {
        var fresh=await repository!.ReadAppointmentEligibilityAsync(policy,lifetime.Token);
        if (lifetime.IsCancellationRequested) return;
        page=fresh;
        policyInfo.Text=$"{fresh.Service} · Policy revision {fresh.PolicyRevision} · {(fresh.PolicyActive ? "Active" : "Inactive")}";
        grid.DataSource=fresh.Candidates.DefaultView;
        status.Text=fresh.Candidates.Rows.Count==0 ? "No active HRMS-linked providers in this branch." : "";
    }

    private async Task ChangeAsync(bool eligibility)
    {
        if (!(eligibility ? activate.Enabled : disable.Enabled) || Selected is not DataRow row || page is null)
            return;
        var draft=new AppointmentEligibilityDraft(policy,page.PolicyRevision,row.Field<int>("id"),row.Field<int>("employee"),
            row.Field<int?>("revision"),eligibility);
        await RunAsync(async () =>
        {
            await repository!.SaveAppointmentEligibilityAsync(draft,lifetime.Token);
            Changed=true;
            await ReloadAsync();
            status.Text=eligibility ? "Specialist is eligible." : "Specialist eligibility deactivated.";
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy) return;
        busy=true;
        UpdateActions();
        try {await work();}
        catch(OperationCanceledException) when(lifetime.IsCancellationRequested) { }
        catch(Exception error) when(AppointmentsForm.IsExpected(error))
        {
            if(!lifetime.IsCancellationRequested) status.Text=AppointmentsForm.Friendly(error);
        }
        finally
        {
            busy=false;
            if(!IsDisposed) UpdateActions();
        }
    }

    private void UpdateActions()
    {
        refresh.Enabled=!busy;
        bool allowed=!busy && page?.CanSave==true && Selected is not null;
        bool selectedActive=Selected?.Field<bool>("active")==true;
        activate.Enabled=allowed && page?.PolicyActive==true && !selectedActive;
        disable.Enabled=allowed && selectedActive;
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        base.OnFormClosed(e);
    }
}
