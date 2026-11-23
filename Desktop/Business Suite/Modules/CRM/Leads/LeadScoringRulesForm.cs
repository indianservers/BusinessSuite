using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class LeadScoringRulesForm : Form
{
    private readonly CancellationTokenSource lifetime=new();
    private bool busy;
    private bool editing;
    private LeadScoringRuleKey? editKey;
    private LeadScoringDirectory? directory;

    public LeadScoringRulesForm() => InitializeComponent();

    private DataRowView? Selected => rulesGrid.CurrentRow?.DataBoundItem as DataRowView;
    private async void RefreshClicked(object sender,EventArgs e) => await RunAsync(LoadAsync);
    private void SelectionChanged(object sender,EventArgs e)
    {
        confirmArchiveBox.Checked=false;
        UpdateActions(this,EventArgs.Empty);
    }

    private void NewClicked(object sender,EventArgs e)
    {
        if (!newButton.Enabled)
            return;
        BeginEditing(null,new("","email","exists","",10,true));
    }

    private void EditClicked(object sender,EventArgs e)
    {
        if (!editButton.Enabled || Selected is not DataRowView row)
            return;
        BeginEditing(Key(row),new((string)row["name"],(string)row["field"],(string)row["operator"],
            (string)row["value"],(int)row["points"],(bool)row["active"]));
    }

    private void BeginEditing(LeadScoringRuleKey? key,LeadScoringDraft draft)
    {
        editKey=key;
        editing=true;
        nameBox.Text=draft.Name;
        fieldBox.Text=draft.Field;
        operatorBox.Text=draft.Operator;
        valueBox.Text=draft.Value;
        pointsBox.Value=draft.Points;
        activeBox.Checked=draft.Active;
        feedback.Text=key is null?"Enter the new rule.":"Edit the selected scoring rule.";
        UpdateActions(this,EventArgs.Empty);
        nameBox.Focus();
    }

    private void CancelEditClicked(object sender,EventArgs e)
    {
        editing=false;
        editKey=null;
        feedback.Text="";
        UpdateActions(this,EventArgs.Empty);
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (!saveButton.Enabled)
            return;
        var draft=new LeadScoringDraft(nameBox.Text,fieldBox.Text,operatorBox.Text,valueBox.Text,(int)pointsBox.Value,activeBox.Checked);
        await RunAsync(async cancellation =>
        {
            await LeadStore.SaveLeadScoringRuleAsync(editKey,draft,cancellation);
            editing=false;
            editKey=null;
            await LoadAsync(cancellation);
            if (!cancellation.IsCancellationRequested)
                feedback.Text="Scoring rule saved.";
        });
    }

    private async void ArchiveClicked(object sender,EventArgs e)
    {
        if (!archiveButton.Enabled || Selected is not DataRowView row)
            return;
        await RunAsync(async cancellation =>
        {
            await LeadStore.ArchiveLeadScoringRuleAsync(Key(row),cancellation);
            await LoadAsync(cancellation);
            if (!cancellation.IsCancellationRequested)
                feedback.Text="Scoring rule archived.";
        });
    }

    private async Task LoadAsync(CancellationToken cancellation)
    {
        var result=await LeadStore.ScoringDirectoryAsync(cancellation);
        if (cancellation.IsCancellationRequested)
            return;
        directory=result;
        rulesGrid.DataSource=result.Rows;
        feedback.Text=result.Rows.Rows.Count==0?"No scoring rules configured.":$"{result.Rows.Rows.Count:N0} scoring rules.";
    }

    private async Task RunAsync(Func<CancellationToken,Task> operation)
    {
        if (busy)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions(this,EventArgs.Empty);
        try { await operation(cancellation); }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is UnauthorizedAccessException or ArgumentException or InvalidOperationException
                    ?error.Message:"Could not access Lead scoring rules in PostgreSQL.";
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions(this,EventArgs.Empty);
        }
    }

    private void UpdateActions(object sender,EventArgs e)
    {
        bool browsing=!busy&&!editing;
        rulesGrid.Enabled=refreshButton.Enabled=browsing;
        newButton.Enabled=browsing&&directory?.CanCreate==true;
        editButton.Enabled=browsing&&directory?.CanEdit==true&&Selected is not null;
        confirmArchiveBox.Enabled=browsing&&directory?.CanArchive==true&&Selected is not null;
        archiveButton.Enabled=confirmArchiveBox.Enabled&&confirmArchiveBox.Checked;
        details.Enabled=editing&&!busy;
    }

    private static LeadScoringRuleKey Key(DataRowView row) => new((int)row["id"],(string)row["revision"]);

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
