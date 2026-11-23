using System.ComponentModel;
using Npgsql;

namespace Business_Suite;

public sealed partial class LeadSequenceTemplatesForm : Form
{
    public sealed class SequenceRow
    {
        public string Name {get;set;}="";
        public BindingList<StepRow> Steps {get;}=new();
    }

    public sealed class StepRow
    {
        public int Day {get;set;}
        public string Kind {get;set;}="task";
        public string Title {get;set;}="";
    }

    private readonly CancellationTokenSource lifetime=new();
    private BindingList<SequenceRow> templates=new();
    private string revision="";
    private bool canWrite;
    private bool busy;

    public LeadSequenceTemplatesForm() => InitializeComponent();

    private SequenceRow? Selected => templateGrid.CurrentRow?.DataBoundItem as SequenceRow;

    private async void FormShown(object sender,EventArgs e) => await RunAsync(async cancellation =>
    {
        var result=await LeadStore.SequenceDirectoryAsync(cancellation);
        if (cancellation.IsCancellationRequested)
            return;
        revision=result.Revision;
        canWrite=result.CanWrite;
        templates=new BindingList<SequenceRow>();
        foreach(var template in result.Templates)
        {
            var row=new SequenceRow {Name=template.Name};
            foreach(var step in template.Steps)
                row.Steps.Add(new() {Day=step.Day,Kind=step.Kind,Title=step.Title});
            templates.Add(row);
        }
        templateGrid.DataSource=templates;
        feedback.Text=canWrite?"Edit the sequence and step cells, then save.":"Company-wide CRM administration is required to save templates.";
    });

    private void TemplateChanged(object sender,EventArgs e)
    {
        stepsGrid.DataSource=Selected?.Steps;
        UpdateActions(this,EventArgs.Empty);
    }

    private void AddTemplateClicked(object sender,EventArgs e)
    {
        if (!addTemplateButton.Enabled)
            return;
        var template=new SequenceRow {Name="New sequence"};
        template.Steps.Add(new());
        templates.Add(template);
        templateGrid.CurrentRow=templateGrid.Rows.Last();
        UpdateActions(this,EventArgs.Empty);
    }

    private void RemoveTemplateClicked(object sender,EventArgs e)
    {
        if (removeTemplateButton.Enabled && Selected is SequenceRow selected)
            templates.Remove(selected);
        TemplateChanged(this,EventArgs.Empty);
    }

    private void AddStepClicked(object sender,EventArgs e)
    {
        if (addStepButton.Enabled && Selected is SequenceRow selected)
        {
            selected.Steps.Add(new());
            stepsGrid.CurrentRow=stepsGrid.Rows.Last();
        }
        UpdateActions(this,EventArgs.Empty);
    }

    private void RemoveStepClicked(object sender,EventArgs e)
    {
        if (removeStepButton.Enabled && Selected is SequenceRow selected && stepsGrid.CurrentRow?.DataBoundItem is StepRow step)
            selected.Steps.Remove(step);
        UpdateActions(this,EventArgs.Empty);
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (!saveButton.Enabled)
            return;
        templateGrid.EndEdit();
        stepsGrid.EndEdit();
        var draft=templates.Select(template=>new LeadSequenceTemplate(template.Name,
            template.Steps.Select(step=>new LeadSequenceStep(step.Day,step.Kind,step.Title)).ToList())).ToList();
        await RunAsync(async cancellation =>
        {
            await LeadStore.SaveSequenceDirectoryAsync(revision,draft,cancellation);
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
                    ?error.Message:"Could not access Lead sequence templates in PostgreSQL.";
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
        var selected=Selected;
        bool writable=canWrite&&!busy;
        templateGrid.ReadOnly=stepsGrid.ReadOnly=!writable;
        addTemplateButton.Enabled=writable&&templates.Count<30;
        removeTemplateButton.Enabled=writable&&selected is not null;
        addStepButton.Enabled=writable&&selected is not null&&selected.Steps.Count<30;
        removeStepButton.Enabled=writable&&stepsGrid.CurrentRow?.DataBoundItem is StepRow;
        saveButton.Enabled=writable;
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
