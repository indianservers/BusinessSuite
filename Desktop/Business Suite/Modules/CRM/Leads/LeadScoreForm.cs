using Npgsql;

namespace Business_Suite;

public sealed partial class LeadScoreForm : Form
{
    private readonly LeadKey? key;
    private readonly bool manual;
    private readonly bool canRecalculate;
    private readonly CancellationTokenSource lifetime=new();

    public LeadScoreForm() => InitializeComponent();

    internal LeadScoreForm(LeadKey key,string mode,int score,string rating,string reason,bool canRecalculate) : this()
    {
        this.key=key;
        manual=string.Equals(mode,"manual",StringComparison.OrdinalIgnoreCase);
        this.canRecalculate=canRecalculate;
        scoreLabel.Text=$"{score} {rating} · {(manual?"Manual":"Automatic")}";
        manualScoreBox.Value=Math.Min(100,Math.Max(0,score));
        reasonBox.Text=manual?reason:"";
        replaceBox.Visible=manual&&canRecalculate;
        SetEditing(true);
    }

    internal bool Changed {get;private set;}

    private void ReplaceChanged(object sender,EventArgs e) => calculateButton.Enabled=canRecalculate&&!Changed&&replaceBox.Checked;

    private async void CalculateClicked(object sender,EventArgs e)
    {
        if (key is null || !calculateButton.Enabled)
            return;
        await SaveAsync(cancellation=>LeadStore.RecalculateLeadScoreAsync(key,replaceBox.Checked,cancellation),false);
    }

    private async void SaveManualClicked(object sender,EventArgs e)
    {
        if (key is null || !saveManualButton.Enabled)
            return;
        await SaveAsync(cancellation=>LeadStore.SetManualLeadScoreAsync(key,(int)manualScoreBox.Value,reasonBox.Text,cancellation),true);
    }

    private async Task SaveAsync(Func<CancellationToken,Task<LeadScoreResult>> save,bool settingManual)
    {
        var cancellation=lifetime.Token;
        SetEditing(false);
        feedback.Text=settingManual?"Saving manual score…":"Recalculating score…";
        try
        {
            var score=await save(cancellation);
            if (!cancellation.IsCancellationRequested)
            {
                Changed=true;
                scoreLabel.Text=$"{score.Score} {score.Label} · {(settingManual?"Manual":"Automatic")}";
                reasonsGrid.DataSource=score.Reasons;
                replaceBox.Visible=false;
                feedback.Text=settingManual?"Manual score and reason saved.":
                    score.Reasons.Count==0?"No enabled scoring rules. Automatic score is 0.":"Automatic score saved.";
            }
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is UnauthorizedAccessException or InvalidOperationException or ArgumentException
                    ?error.Message:"Could not save the Lead score to PostgreSQL.";
        }
        finally
        {
            if (!cancellation.IsCancellationRequested && !Changed)
                SetEditing(true);
        }
    }

    private void SetEditing(bool enabled)
    {
        replaceBox.Enabled=manualScoreBox.Enabled=reasonBox.Enabled=saveManualButton.Enabled=enabled;
        calculateButton.Enabled=enabled&&canRecalculate&&(!manual||replaceBox.Checked);
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
