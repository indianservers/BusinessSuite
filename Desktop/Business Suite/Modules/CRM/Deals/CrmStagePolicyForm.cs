using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmStagePolicyForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly CancellationTokenSource lifetime=new();
    private List<PipelinePolicyStage> stages=[];
    private bool busy;
    private bool binding;
    private bool valid;

    public CrmStagePolicyForm() => InitializeComponent();
    internal CrmStagePolicyForm(CrmDealRepository repository) : this() => this.repository=repository;

    private async void FormShown(object sender,EventArgs e) => await LoadAsync(null);
    private async void RefreshClicked(object sender,EventArgs e) => await LoadAsync(Selected?.Id);
    private PipelinePolicyStage? Selected=>stageBox.SelectedItem?.DataBoundItem as PipelinePolicyStage;

    private async Task LoadAsync(int? restore)
    {
        if (repository is null || busy)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions();
        feedback.Text="Loading pipeline stages…";
        try
        {
            var loaded=await repository.PipelinePolicyStagesAsync(cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            stages=loaded;
            binding=true;
            stageBox.DisplayMember=nameof(PipelinePolicyStage.Label);
            stageBox.DataSource=stages;
            int index=restore.HasValue?stages.FindIndex(stage=>stage.Id==restore.Value):-1;
            stageBox.SelectedIndex=index<0 && stages.Count>0?0:index;
            binding=false;
            BindStage();
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                valid=false;
                feedback.Text=Friendly(error);
            }
        }
        finally
        {
            busy=false;
            binding=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void StageChanged(object sender,EventArgs e)
    {
        if (!binding)
            BindStage();
    }

    private void BindStage()
    {
        valid=false;
        destinations.Items.Clear();
        if (Selected is not PipelinePolicyStage source)
            feedback.Text="No stages are available.";
        else
        {
            try
            {
                var policy=JsonSerializer.Deserialize<DealStagePolicy>(source.Json)??new();
                for (int index=0;index<requiredFields.Items.Count;index++)
                    requiredFields.SetItemChecked(index,policy.Required.Contains(CrmDealRepository.StageRequiredFields[index].Key));
                destinations.DisplayMember=nameof(PipelinePolicyStage.Label);
                foreach (var target in stages.Where(stage=>stage.Pipeline==source.Pipeline && stage.Id!=source.Id))
                    destinations.Items.Add(target,policy.AllowedNext.Contains(target.Id));
                approvalBox.Checked=policy.Approval;
                notifyBox.Checked=policy.NotifyOwner;
                daysBox.Value=policy.StagnationDays;
                capacityBox.Value=policy.Capacity ?? 1;
                limitBox.Checked=policy.Capacity.HasValue;
                valid=true;
                feedback.Text=policy.AllowedNext.Any(id=>!stages.Any(stage=>stage.Id==id && stage.Pipeline==source.Pipeline))
                    ?"Some stored destinations are unavailable. Saving uses the destinations shown here."
                    :"Clear all destinations to allow any stage permitted by the pipeline.";
            }
            catch(Exception error) when(error is JsonException or ArgumentOutOfRangeException or ArgumentNullException)
            {
                feedback.Text="This stage has an invalid stored policy.";
            }
        }
        UpdateActions();
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (repository is null || !saveButton.Enabled || Selected is not PipelinePolicyStage source)
            return;
        var draft=new DealStagePolicy
        {
            AllowedNext=destinations.CheckedItems.Cast<PipelinePolicyStage>().Select(stage=>stage.Id).ToArray(),
            Required=requiredFields.CheckedIndices.Cast<int>().Select(index=>CrmDealRepository.StageRequiredFields[index].Key).ToArray(),
            Approval=approvalBox.Checked,NotifyOwner=notifyBox.Checked,StagnationDays=(int)daysBox.Value,
            Capacity=limitBox.Checked?(int)capacityBox.Value:null
        };
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions();
        bool saved=false;
        try
        {
            await repository.SaveStagePolicyAsync(source,draft,cancellation);
            saved=true;
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=Friendly(error);
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
        if (saved && !cancellation.IsCancellationRequested)
        {
            await LoadAsync(source.Id);
            if (!cancellation.IsCancellationRequested && valid)
                feedback.Text="Stage policy saved.";
        }
    }

    private void LimitChanged(object sender,EventArgs e) => UpdateActions();
    private void UpdateActions()
    {
        stageBox.Enabled=!busy&&stages.Count>0;
        refreshButton.Enabled=!busy;
        requiredFields.Enabled=destinations.Enabled=approvalBox.Enabled=notifyBox.Enabled=daysBox.Enabled=limitBox.Enabled=
            saveButton.Enabled=!busy&&valid;
        capacityBox.Enabled=saveButton.Enabled&&limitBox.Checked;
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }

    private static bool Expected(Exception error)=>error is ArgumentException or InvalidOperationException
        or UnauthorizedAccessException or NpgsqlException or IOException or TimeoutException;
    private static string Friendly(Exception error)=>error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
        ?error.Message:"Could not complete the pipeline policy operation.";
}
