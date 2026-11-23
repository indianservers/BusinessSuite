using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealForecastForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly string search="";
    private readonly string status="";
    private readonly bool archived;
    private readonly CrmDealFilters initial=new();
    private readonly CancellationTokenSource lifetime=new();
    private bool ready;
    private bool busy;

    public CrmDealForecastForm() => InitializeComponent();
    internal CrmDealForecastForm(CrmDealRepository repository,string search,string status,bool archived,CrmDealFilters initial) : this()
    {
        this.repository=repository;
        this.search=search;
        this.status=status;
        this.archived=archived;
        this.initial=initial;
    }

    internal CrmDealFilters? DrillFilters {get;private set;}

    private async void FormShown(object sender,EventArgs e)
    {
        ready=true;
        await LoadAsync();
    }

    private async void GroupChanged(object sender,EventArgs e) => await LoadAsync();
    private void SelectionChanged(object sender,EventArgs e) => UpdateActions();

    private async Task LoadAsync()
    {
        if (!ready || busy || repository is null || groupingBox.SelectedIndex<0)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        groupingBox.Enabled=false;
        UpdateActions();
        feedback.Text="Calculating forecast…";
        try
        {
            var forecast=await repository.ForecastAsync(search,status,archived,initial,(DealForecastGroup)groupingBox.SelectedIndex,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            groupsGrid.DataSource=forecast.Groups;
            totalsGrid.DataSource=forecast.Currencies;
            var counts=forecast.Counts;
            string rate=counts["win_rate"] is decimal value?$"{value:N2}%":"—";
            summary.Text=$"Open {counts["opened"]:N0}   •   Closing this month {counts["closing_month"]:N0}   •   Won this month {counts["won_month"]:N0}   •   Lost this month {counts["lost_month"]:N0}   •   Win rate {rate}"
                +Environment.NewLine+$"Overdue next action {counts["overdue"]:N0}   •   No next action {counts["missing_action"]:N0}   •   No activity {counts["missing_activity"]:N0}";
            feedback.Text=forecast.Groups.Rows.Count==0?"No open Deals match these filters.":"Select a dated or assigned group to open its Deals.";
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or UnauthorizedAccessException or
            ArgumentException or InvalidOperationException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
            {
                groupsGrid.DataSource=totalsGrid.DataSource=null;
                summary.Text="";
                feedback.Text=error is UnauthorizedAccessException or ArgumentException or InvalidOperationException
                    ?error.Message:"Could not calculate the forecast from PostgreSQL.";
            }
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
            {
                groupingBox.Enabled=true;
                UpdateActions();
            }
        }
    }

    private void DrillClicked(object sender,EventArgs e)
    {
        if (!drillButton.Enabled)
            return;
        DrillFilters=SelectedFilters();
        if (DrillFilters is not null)
            DialogResult=DialogResult.OK;
    }

    private void UpdateActions() => drillButton.Enabled=ready&&!busy&&tabs.SelectedTab==groupsTab&&SelectedFilters() is not null;

    private CrmDealFilters? SelectedFilters()
    {
        if (groupsGrid.CurrentRow?.DataBoundItem is not DataRowView row || row["currency_key"] is not string currency)
            return null;
        var current=initial with {Currency=currency};
        var grouping=(DealForecastGroup)groupingBox.SelectedIndex;
        if (grouping is DealForecastGroup.Month or DealForecastGroup.Quarter)
        {
            if (row["period_start"] is not DateTime start)
                return null;
            DateTime end=start.AddMonths(grouping==DealForecastGroup.Month?1:3).AddDays(-1);
            return current with {
                From=current.From is DateTime from && from>start?from:start,
                Until=current.Until is DateTime until && until<end?until:end
            };
        }
        if (row["group_id"] is not int id)
            return null;
        return grouping switch
        {
            DealForecastGroup.Owner=>current with {Owner=id},
            DealForecastGroup.Stage=>current with {Stage=id},
            DealForecastGroup.Pipeline=>current with {Pipeline=id},
            _=>null
        };
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
