using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealOutcomesForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly string search="";
    private readonly string status="";
    private readonly CrmDealFilters filters=new();
    private readonly CancellationTokenSource lifetime=new();

    public CrmDealOutcomesForm() => InitializeComponent();
    internal CrmDealOutcomesForm(CrmDealRepository repository,string search,string status,CrmDealFilters filters) : this()
    {
        this.repository=repository;
        this.search=search;
        this.status=status;
        this.filters=filters;
    }

    internal CrmDealFilters? DrillFilters {get;private set;}
    internal bool DrillLost {get;private set;}

    private async void LoadClicked(object sender,EventArgs e)
    {
        if (repository is null || !refreshButton.Enabled)
            return;
        var cancellation=lifetime.Token;
        refreshButton.Enabled=drillButton.Enabled=false;
        feedback.Text="Loading recorded outcomes…";
        try
        {
            var conversion=await repository.StageConversionAsync(search,status,filters,cancellation);
            var result=await repository.LossAnalysisAsync(search,filters,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            reasonsGrid.DataSource=result.Reasons;
            competitorsGrid.DataSource=result.Competitors;
            conversionGrid.DataSource=conversion;
            TabChanged(this,EventArgs.Empty);
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or UnauthorizedAccessException or
            InvalidOperationException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
            {
                conversionGrid.DataSource=reasonsGrid.DataSource=competitorsGrid.DataSource=null;
                feedback.Text=error is UnauthorizedAccessException or InvalidOperationException or ArgumentException
                    ?error.Message:"Could not load sales outcomes from PostgreSQL.";
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                refreshButton.Enabled=true;
                UpdateActions(this,EventArgs.Empty);
            }
        }
    }

    private void TabChanged(object sender,EventArgs e)
    {
        if (conversionGrid.DataSource is not null)
        {
            feedback.Text=tabs.SelectedTab==conversionTab
                ?conversionGrid.Rows.Count==0?"No recorded stage entries match these filters.":
                    "Progression uses the current stage order. Terminal stages have no onward rate."
                :reasonsGrid.Rows.Count==0?"No recorded lost Deals match these filters.":
                    "Values are separated by currency. Competitors come from closure or qualification.";
        }
        UpdateActions(sender,e);
    }

    private void UpdateActions(object sender,EventArgs e) =>
        drillButton.Enabled=refreshButton.Enabled&&SelectedFilters() is not null;

    private CrmDealFilters? SelectedFilters()
    {
        if (tabs.SelectedTab==conversionTab && conversionGrid.CurrentRow?.DataBoundItem is DataRowView entry &&
            entry["currency_key"] is string stageCurrency)
            return filters with {EnteredStage=(int)entry["stage_id"],Currency=stageCurrency};
        if (tabs.SelectedTab==reasonsTab && reasonsGrid.CurrentRow?.DataBoundItem is DataRowView reason &&
            reason["currency_key"] is string lossCurrency)
            return filters with {LostReason=(string)reason["name"],Currency=lossCurrency};
        return null;
    }

    private void DrillClicked(object sender,EventArgs e)
    {
        DrillFilters=SelectedFilters();
        DrillLost=tabs.SelectedTab==reasonsTab;
        if (DrillFilters is not null)
            DialogResult=DialogResult.OK;
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
