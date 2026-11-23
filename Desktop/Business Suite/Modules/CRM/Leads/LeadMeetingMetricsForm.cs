using Npgsql;

namespace Business_Suite;

public sealed partial class LeadMeetingMetricsForm : Form
{
    private readonly string search="";
    private readonly string stage="";
    private readonly int? owner;
    private readonly CancellationTokenSource lifetime=new();

    public LeadMeetingMetricsForm() => InitializeComponent();

    internal LeadMeetingMetricsForm(string search,string stage,int? owner) : this()
    {
        this.search=search;
        this.stage=stage;
        this.owner=owner;
    }

    private async void RefreshClicked(object sender,EventArgs e)
    {
        if (!refreshButton.Enabled)
            return;
        var cancellation=lifetime.Token;
        refreshButton.Enabled=false;
        feedback.Text="Loading meeting outcomes…";
        try
        {
            var result=await LeadStore.MeetingMetricsAsync(search,stage,owner,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            metricsGrid.DataSource=result.Counts;
            feedback.Text=result.SalesProcessEnabled?"Company sales process enabled.":"Company sales process setup required.";
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
            {
                metricsGrid.DataSource=null;
                feedback.Text=error is UnauthorizedAccessException or InvalidOperationException or ArgumentException
                    ?error.Message:"Could not load recorded meeting outcomes from PostgreSQL.";
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
                refreshButton.Enabled=true;
        }
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
