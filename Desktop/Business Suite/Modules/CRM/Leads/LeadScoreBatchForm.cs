using Npgsql;

namespace Business_Suite;

public sealed partial class LeadScoreBatchForm : Form
{
    private readonly CancellationTokenSource lifetime=new();

    public LeadScoreBatchForm() => InitializeComponent();

    private void ManageRulesClicked(object sender,EventArgs e)
    {
        using var form=new LeadScoringRulesForm();
        form.ShowDialog(this);
        FormShown(this,EventArgs.Empty);
    }

    private void FormShown(object sender,EventArgs e)
    {
        try
        {
            var settings=DesktopDatabaseSettings.Load();
            scopeLabel.Text=settings.BranchId is int branch
                ?$"Company #{settings.OrganizationId} · Branch #{branch}"
                :$"Company #{settings.OrganizationId} · All branches";
            calculateButton.Enabled=true;
        }
        catch(Exception error) when(error is ArgumentException or InvalidOperationException or IOException or UnauthorizedAccessException)
        {
            feedback.Text=error.Message;
        }
    }

    private async void CalculateClicked(object sender,EventArgs e)
    {
        if (!calculateButton.Enabled)
            return;
        var cancellation=lifetime.Token;
        calculateButton.Enabled=false;
        manageRulesButton.Enabled=false;
        feedback.Text="Recalculating automatic Lead scores…";
        try
        {
            var result=await LeadStore.RecalculateAutomaticLeadScoresAsync(cancellation);
            if (!cancellation.IsCancellationRequested)
                feedback.Text=$"{result.Updated:N0} automatic scores recalculated. {result.Manual:N0} manual scores retained.";
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
            {
                feedback.Text=error is UnauthorizedAccessException or InvalidOperationException or ArgumentException
                    ?error.Message:"Could not recalculate Lead scores from PostgreSQL.";
                calculateButton.Enabled=true;
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
                manageRulesButton.Enabled=true;
        }
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
