using Npgsql;

namespace Business_Suite;

public sealed partial class LeadStageSettingsForm : Form
{
    private sealed record FieldChoice(string Key,string Caption);

    private static readonly FieldChoice[] RequiredFields=[
        new("email","Email"),new("phone","Phone"),new("company_name","Company"),new("need","Need"),
        new("budget","Budget"),new("decisionMaker","Decision maker"),new("timeline","Timeline"),
        new("lossReason","Loss reason"),new("competitor","Competitor"),new("next_follow_up_at","Next follow-up")
    ];

    private readonly CancellationTokenSource lifetime=new();
    private List<LeadStage> stages=new();
    private string revision="";
    private bool loading;
    private bool busy;
    private bool canWrite;

    public LeadStageSettingsForm() => InitializeComponent();

    private async void FormShown(object sender,EventArgs e) => await RunAsync(async cancellation =>
    {
        var result=await LeadStore.StageDirectoryAsync(cancellation);
        if (cancellation.IsCancellationRequested)
            return;
        revision=result.Revision;
        canWrite=result.CanWrite;
        stages=result.Policy.Stages.ToList();
        duplicateBox.Checked=result.Policy.PreventDuplicates;
        responseHoursBox.Value=result.Policy.SlaHours;
        inactivityDaysBox.Value=result.Policy.StaleDays;
        BindStages(0);
        feedback.Text=canWrite?"Choose a stage to set its allowed transitions and required fields.":
            "Company-wide CRM administration is required to save stage settings.";
    });

    private void BindStages(int selected)
    {
        stageBox.DataSource=stages.Select(stage=>stage.Name).ToArray();
        if (selected>=0&&selected<stages.Count)
            stageBox.SelectedIndex=selected;
        StageChanged(this,EventArgs.Empty);
    }

    private void StageChanged(object sender,EventArgs e)
    {
        int index=stageBox.SelectedIndex;
        if (index<0||index>=stages.Count)
            return;
        var stage=stages[index];
        loading=true;
        try
        {
            transitionBox.Items.Clear();
            foreach(var destination in stages.Where(item=>item.Name!=stage.Name&&item.Name!="Converted"))
                transitionBox.Items.Add(destination.Name,stage.AllowedNext.Contains(destination.Name));
            requiredBox.Items.Clear();
            requiredBox.DisplayMember="Caption";
            var fields=RequiredFields.Concat(stage.Required.Where(key=>!RequiredFields.Any(field=>field.Key==key))
                .Select(key=>new FieldChoice(key,key)));
            foreach(var field in fields)
                requiredBox.Items.Add(field,stage.Required.Contains(field.Key));
        }
        finally { loading=false; }
        UpdateActions();
    }

    private void TransitionChanged(object sender,ItemCheckEventArgs e)
    {
        if (loading||!canWrite||stageBox.SelectedIndex<0)
            return;
        int index=stageBox.SelectedIndex;
        var stage=stages[index];
        string name=(string)transitionBox.Items[e.Index];
        string[] allowed=e.NewValue==CheckState.Checked?stage.AllowedNext.Append(name).Distinct().ToArray():
            stage.AllowedNext.Where(item=>item!=name).ToArray();
        stages[index]=stage with {AllowedNext=allowed};
    }

    private void RequiredChanged(object sender,ItemCheckEventArgs e)
    {
        if (loading||!canWrite||stageBox.SelectedIndex<0)
            return;
        int index=stageBox.SelectedIndex;
        var stage=stages[index];
        string key=((FieldChoice)requiredBox.Items[e.Index]).Key;
        string[] required=e.NewValue==CheckState.Checked?stage.Required.Append(key).Distinct().ToArray():
            stage.Required.Where(item=>item!=key).ToArray();
        stages[index]=stage with {Required=required};
    }

    private void AddStageClicked(object sender,EventArgs e)
    {
        if (!addStageButton.Enabled)
            return;
        string name=stageNameBox.Text.Trim();
        if (name.Length==0||stages.Any(stage=>stage.Name==name))
        {
            feedback.Text="Enter a unique stage name.";
            return;
        }
        stages.Add(new(name,["Qualified","Lost"],[]));
        stageNameBox.Clear();
        BindStages(stages.Count-1);
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (!saveButton.Enabled)
            return;
        await RunAsync(async cancellation =>
        {
            await LeadStore.SaveLeadStageDirectoryAsync(revision,stages.ToArray(),duplicateBox.Checked,cancellation,
                (int)responseHoursBox.Value,(int)inactivityDaysBox.Value);
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
        UpdateActions();
        try { await action(cancellation); }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is UnauthorizedAccessException or InvalidOperationException or ArgumentException
                    ?error.Message:"Could not access Lead stage settings in PostgreSQL.";
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void UpdateActions()
    {
        bool editable=canWrite&&!busy;
        stageBox.Enabled=!busy&&stages.Count>0;
        string current=stageBox.Text;
        transitionBox.Enabled=editable&&current.Length>0&&current!="Converted";
        requiredBox.Enabled=editable&&current.Length>0;
        duplicateBox.Enabled=saveButton.Enabled=editable;
        responseHoursBox.Enabled=inactivityDaysBox.Enabled=editable;
        stageNameBox.Enabled=addStageButton.Enabled=editable&&stages.Count<25;
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
