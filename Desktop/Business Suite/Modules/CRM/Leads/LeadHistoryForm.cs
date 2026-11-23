using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class LeadHistoryForm : Form
{
    private readonly int lead;
    private readonly bool potential;
    private readonly CancellationTokenSource lifetime=new();
    private LeadKey? editKey;
    private DataRow? scoringDetails;
    private bool canRecalculateScore;

    public LeadHistoryForm() => InitializeComponent();

    internal LeadHistoryForm(int lead,bool potential,string title) : this()
    {
        this.lead=lead;
        this.potential=potential;
        heading.Text=title;
    }

    private async void RefreshClicked(object sender,EventArgs e) => await LoadAsync();

    private async void TeamUpdateClicked(object sender,EventArgs e)
    {
        if (!teamUpdateButton.Enabled || editKey is not LeadKey key)
            return;
        using var dialog=new LeadTeamNoteForm(key);
        if (dialog.ShowDialog(this)==DialogResult.OK)
            await LoadAsync();
    }

    private async void LeadScoreClicked(object sender,EventArgs e)
    {
        if (!leadScoreButton.Enabled || editKey is not LeadKey key || scoringDetails is not DataRow row)
            return;
        using var dialog=new LeadScoreForm(key,LeadStore.Text(row,"lead_score_mode"),row["lead_score"] as int? ?? 0,
            LeadStore.Text(row,"rating"),LeadStore.Text(row,"score_override_reason"),canRecalculateScore);
        dialog.ShowDialog(this);
        if (dialog.Changed)
            await LoadAsync();
    }

    private async void AssignOwnerClicked(object sender,EventArgs e)
    {
        if (!assignOwnerButton.Enabled || editKey is not LeadKey key) return;
        using var form=new LeadAssignmentForm(key);
        if (form.ShowDialog(this)==DialogResult.OK)
            await LoadAsync();
    }

    private async void SequenceClicked(object sender,EventArgs e)
    {
        if (!sequenceButton.Enabled || editKey is not LeadKey key)
            return;
        using var dialog=new LeadSequenceForm(key);
        if (dialog.ShowDialog(this)==DialogResult.OK)
            await LoadAsync();
    }

    private async Task LoadAsync()
    {
        if (lead<=0 || !refreshButton.Enabled)
            return;
        var cancellation=lifetime.Token;
        refreshButton.Enabled=teamUpdateButton.Enabled=leadScoreButton.Enabled=sequenceButton.Enabled=assignOwnerButton.Enabled=false;
        editKey=null;
        scoringDetails=null;
        canRecalculateScore=false;
        feedback.Text="Loading Lead details…";
        try
        {
            var result=await LeadStore.LeadPreviewAsync(lead,potential,cancellation);
            if (!cancellation.IsCancellationRequested)
            {
                ShowPreview(result.Details,result.Signals);
                if (result.CanWrite)
                {
                    editKey=LeadStore.Key(result.Details,potential);
                    scoringDetails=result.Details;
                    canRecalculateScore=result.CanScore;
                }
                historyGrid.DataSource=result.History;
                feedback.Text=result.History.Rows.Count==0?"No recorded events yet.":"Select an event to see its description.";
                SelectionChanged(this,EventArgs.Empty);
            }
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
            {
                historyGrid.DataSource=null;
                profileBox.Clear();
                pipelineBox.Clear();
                descriptionBox.Clear();
                feedback.Text=error is UnauthorizedAccessException or InvalidOperationException or ArgumentException
                    ?error.Message:"Could not load Lead history from PostgreSQL.";
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                refreshButton.Enabled=true;
                teamUpdateButton.Enabled=editKey is not null;
                sequenceButton.Enabled=assignOwnerButton.Enabled=editKey is not null&&!potential;
                leadScoreButton.Enabled=scoringDetails is not null;
            }
        }
    }

    private void ShowPreview(DataRow row,LeadSignals signals)
    {
        string Value(string field)=>row.IsNull(field)||string.IsNullOrWhiteSpace(LeadStore.Text(row,field))?"—":LeadStore.Text(row,field);
        heading.Text=$"{Value("full_name")}  #{lead}";
        profileBox.Lines=[$"Company  {Value("company_name")}",$"Email  {Value("email")}",$"Phone  {Value("phone")}",
            $"Need  {Value("need")}"];
        string next=row["follow_up"] is DateTime time?time.ToString("g")+" UTC":"—";
        pipelineBox.Lines=[$"Stage  {Value("status")}   •   Score  {Value("lead_score")} {Value("rating")}"+
            (signals.Stale?"   •   Inactive":""),
            $"Owner  {Value("owner")}   •   Source  {Value("source")}",
            $"Next follow-up  {next}  ({signals.FollowUpLabel})",
            $"First-response deadline  {signals.Deadline:g} UTC"+(signals.SlaBreached?"  (Missed)":""),
            $"Next action  {signals.NextAction}"];
    }

    private void SelectionChanged(object sender,EventArgs e)
    {
        var row=historyGrid.CurrentRow?.DataBoundItem as DataRowView;
        string description=row?["description"] as string??"";
        string? recipients=row?["recipients"] as string;
        descriptionBox.Text=string.IsNullOrEmpty(recipients)?description:
            description+Environment.NewLine+"Mentioned teammates  "+recipients;
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
