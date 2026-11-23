using System.ComponentModel;
using Npgsql;

namespace Business_Suite;

public sealed partial class LeadResponseWorkflowForm : Form
{
    public sealed class RuleRow
    {
        public string Name {get;set;}="";
        public string Trigger {get;set;}="responded";
        public string Stage {get;set;}="";
        public string Action {get;set;}="task";
        public string Title {get;set;}="";
        public int Delay {get;set;}
        public int? Owner {get;set;}
        public bool Enabled {get;set;}=true;
    }

    private readonly CancellationTokenSource lifetime=new();
    private BindingList<RuleRow> rules=new();
    private string revision="";
    private bool canWrite;
    private bool busy;

    public LeadResponseWorkflowForm() => InitializeComponent();

    private async void FormShown(object sender,EventArgs e) => await RunAsync(async cancellation =>
    {
        var result=await LeadStore.ResponseWorkflowDirectoryAsync(cancellation);
        if (cancellation.IsCancellationRequested)
            return;
        revision=result.Revision;
        canWrite=result.CanWrite;
        stageColumn.DataSource=new[]{""}.Concat(result.Stages).ToArray();
        ownerColumn.DataSource=result.Owners;
        rules=new BindingList<RuleRow>(result.Rules.Select(rule=>new RuleRow {
            Name=rule.Name,Trigger=rule.Trigger,Stage=rule.Stage,Action=rule.Action,Title=rule.Title,
            Delay=rule.Delay,Owner=rule.Owner,Enabled=rule.Enabled
        }).ToList());
        ruleGrid.DataSource=rules;
        feedback.Text=canWrite?"Leave stage blank for any stage. Rules run in the saved order.":
            "Company-wide CRM administration is required to save rules.";
    });

    private void AddClicked(object sender,EventArgs e)
    {
        if (!addButton.Enabled)
            return;
        rules.Add(new());
        ruleGrid.CurrentRow=ruleGrid.Rows.Last();
        UpdateActions(this,EventArgs.Empty);
    }

    private void RemoveClicked(object sender,EventArgs e)
    {
        if (removeButton.Enabled&&ruleGrid.CurrentRow?.DataBoundItem is RuleRow rule)
            rules.Remove(rule);
        UpdateActions(this,EventArgs.Empty);
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (!saveButton.Enabled)
            return;
        ruleGrid.EndEdit();
        var draft=rules.Select(rule=>new LeadResponseDraft(rule.Name??"",rule.Stage??"",rule.Action??"",
            rule.Title??"",rule.Delay,rule.Owner,rule.Enabled,rule.Trigger??"")).ToList();
        await RunAsync(async cancellation =>
        {
            await LeadStore.SaveResponseWorkflowDirectoryAsync(revision,draft,cancellation);
            if (!cancellation.IsCancellationRequested)
                DialogResult=DialogResult.OK;
        });
    }

    private async Task RunAsync(Func<CancellationToken,Task> action)
    {
        if (busy)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions(this,EventArgs.Empty);
        try { await action(cancellation); }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is UnauthorizedAccessException or InvalidOperationException or ArgumentException
                    ?error.Message:"Could not access Lead workflows in PostgreSQL.";
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
        bool editable=canWrite&&!busy;
        ruleGrid.ReadOnly=!editable;
        addButton.Enabled=editable&&rules.Count<100;
        removeButton.Enabled=editable&&ruleGrid.CurrentRow?.DataBoundItem is RuleRow;
        saveButton.Enabled=editable;
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
