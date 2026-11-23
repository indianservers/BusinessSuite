using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmPipelineStructureForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly CancellationTokenSource lifetime=new();
    private bool busy;
    private bool loaded;
    private bool binding;
    private bool newPipeline;
    private bool newStage;

    public CrmPipelineStructureForm() => InitializeComponent();
    internal CrmPipelineStructureForm(CrmDealRepository repository) : this() => this.repository=repository;

    private PipelineAdminChoice? Selected=>pipelineBox.SelectedItem?.DataBoundItem as PipelineAdminChoice;
    private DataRowView? Stage=>stagesGrid.CurrentRow?.DataBoundItem as DataRowView;

    private async void FormShown(object sender,EventArgs e) => await RunAsync(c=>LoadPipelinesAsync(null,c));
    private async void ReloadClicked(object sender,EventArgs e) => await RunAsync(c=>LoadPipelinesAsync(Selected?.Id,c));

    private async void PipelineChanged(object sender,EventArgs e)
    {
        if (binding || !loaded || busy)
            return;
        newPipeline=false;
        await RunAsync(LoadSelectedAsync);
    }

    private void NewPipelineClicked(object sender,EventArgs e)
    {
        newPipeline=true;
        pipelineNameBox.Clear();
        pipelineDescriptionBox.Clear();
        feedback.Text="Enter the new pipeline name and save it before adding stages.";
        UpdateActions();
        pipelineNameBox.Focus();
    }

    private async void SavePipelineClicked(object sender,EventArgs e)
    {
        if (repository is null || !savePipelineButton.Enabled)
            return;
        await RunAsync(async cancellation =>
        {
            int id=await repository.SavePipelineAsync(newPipeline?null:Selected,pipelineNameBox.Text,
                pipelineDescriptionBox.Text,cancellation);
            await LoadPipelinesAsync(id,cancellation);
            if (!cancellation.IsCancellationRequested)
                feedback.Text="Pipeline saved.";
        });
    }

    private async void ArchivePipelineClicked(object sender,EventArgs e)
    {
        if (repository is null || !archivePipelineButton.Enabled || Selected is not PipelineAdminChoice pipeline ||
            MessageBox.Show(this,$"Archive the pipeline {pipeline.Name}?","Deal pipelines",MessageBoxButtons.YesNo,
                MessageBoxIcon.Question,MessageBoxDefaultButton.Button2)!=DialogResult.Yes)
            return;
        await RunAsync(async cancellation=>
        {
            await repository.ArchivePipelineAsync(pipeline,cancellation);
            await LoadPipelinesAsync(null,cancellation);
            if (!cancellation.IsCancellationRequested)
                feedback.Text="Pipeline archived. Its stage records were retained.";
        });
    }

    private void StageChanged(object sender,EventArgs e)
    {
        if (!binding)
        {
            newStage=false;
            BindStage();
        }
    }

    private void NewStageClicked(object sender,EventArgs e)
    {
        newStage=true;
        stageNameBox.Clear();
        probabilityBox.Value=0;
        outcomeBox.SelectedIndex=0;
        colorBox.Text="#278a48";
        feedback.Text="The new stage will be appended to the pipeline.";
        UpdateActions();
        stageNameBox.Focus();
    }

    private async void SaveStageClicked(object sender,EventArgs e)
    {
        if (repository is null || !saveStageButton.Enabled || Selected is not PipelineAdminChoice pipeline)
            return;
        var existing=newStage?null:Stage;
        await RunAsync(async cancellation =>
        {
            await repository.SavePipelineStageAsync(pipeline,existing is null?null:(int)existing["id"],
                existing?["revision"] as string,new(stageNameBox.Text,(int)probabilityBox.Value,outcomeBox.Text,colorBox.Text),cancellation);
            await LoadSelectedAsync(cancellation);
            if (!cancellation.IsCancellationRequested)
                feedback.Text="Stage saved.";
        });
    }

    private async void MoveStageUpClicked(object sender,EventArgs e) => await MoveStageAsync(-1);
    private async void MoveStageDownClicked(object sender,EventArgs e) => await MoveStageAsync(1);

    private async void ArchiveStageClicked(object sender,EventArgs e)
    {
        if (repository is null || !archiveStageButton.Enabled || Selected is not PipelineAdminChoice pipeline ||
            Stage is not DataRowView selected || stagesGrid.DataSource is not DataTable table)
            return;
        int source=(int)selected["id"];
        var alternatives=table.Rows.Cast<DataRow>().Where(row=>(int)row["id"]!=source
            && row["active"] is true && Equals(row["outcome"],selected["outcome"]))
            .Select(row=>new CrmDealStage((int)row["id"],(string)row["name"])).ToArray();
        using var form=new CrmStageArchiveForm((string)selected["name"],(long)selected["assigned"],alternatives);
        if (form.ShowDialog(this)!=DialogResult.OK)
            return;
        var snapshot=StageSnapshot(table);
        await RunAsync(async cancellation=>
        {
            int moved=await repository.ArchivePipelineStageAsync(pipeline,snapshot,source,form.Replacement,cancellation);
            await LoadSelectedAsync(cancellation);
            if (!cancellation.IsCancellationRequested)
                feedback.Text=moved switch
                {
                    0=>"Empty stage archived.",
                    1=>"Stage archived and one Deal moved.",
                    _=>$"Stage archived and {moved:N0} Deals moved."
                };
        });
    }

    private async Task MoveStageAsync(int direction)
    {
        if (repository is null || busy || newStage || Selected is not PipelineAdminChoice pipeline ||
            Stage is not DataRowView stage || stagesGrid.DataSource is not DataTable table)
            return;
        int stageId=(int)stage["id"];
        var snapshot=StageSnapshot(table);
        int index=Array.FindIndex(snapshot,item=>item.Id==stageId);
        int position=index+direction;
        if (index<0 || position<0 || position>=snapshot.Length)
            return;
        var next=snapshot.Select(item=>item.Id).ToArray();
        (next[index],next[position])=(next[position],next[index]);
        await RunAsync(async cancellation =>
        {
            await repository.ReorderPipelineStagesAsync(pipeline,snapshot,next,cancellation);
            await LoadSelectedAsync(cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            var row=stagesGrid.Rows.FirstOrDefault(item=>item.DataBoundItem is DataRowView record && (int)record["id"]==stageId);
            if (row is not null)
                stagesGrid.CurrentRow=row;
            feedback.Text="Stage order saved.";
        });
    }

    private static PipelineStageRevision[] StageSnapshot(DataTable table) =>
        table.Rows.Cast<DataRow>().Select(row=>new PipelineStageRevision((int)row["id"],(string)row["revision"])).ToArray();

    private async Task LoadPipelinesAsync(int? select,CancellationToken cancellation)
    {
        var options=await repository!.PipelineListAsync(cancellation);
        if (cancellation.IsCancellationRequested)
            return;
        binding=true;
        pipelineBox.DisplayMember=nameof(PipelineAdminChoice.Name);
        pipelineBox.DataSource=options;
        int found=select.HasValue?options.FindIndex(record=>record.Id==select.Value):-1;
        pipelineBox.SelectedIndex=options.Count==0?-1:Math.Max(0,found);
        binding=false;
        loaded=true;
        newPipeline=false;
        await LoadSelectedAsync(cancellation);
    }

    private async Task LoadSelectedAsync(CancellationToken cancellation)
    {
        var selected=Selected;
        var stages=selected is null?null:await repository!.PipelineAdminStagesAsync(selected.Id,cancellation);
        if (cancellation.IsCancellationRequested)
            return;
        pipelineNameBox.Text=selected?.Name??"";
        pipelineDescriptionBox.Text=selected?.Description??"";
        binding=true;
        stagesGrid.DataSource=stages;
        binding=false;
        newStage=false;
        BindStage();
        feedback.Text=selected is null?"Create a pipeline to get started.":stages!.Rows.Count==0?"Add the pipeline's first stage.":"";
    }

    private void BindStage()
    {
        var stage=Stage;
        stageNameBox.Text=stage is null?"":Convert.ToString(stage["name"]);
        probabilityBox.Value=stage?["probability"] is int value?Math.Min(100,Math.Max(0,value)):0;
        outcomeBox.SelectedItem=stage?["outcome"] as string??"open";
        colorBox.Text=stage?["color"] as string??"#278a48";
        UpdateActions();
    }

    private async Task RunAsync(Func<CancellationToken,Task> operation)
    {
        if (repository is null || busy)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions();
        try {await operation(cancellation);}
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or ArgumentException or InvalidOperationException
            or UnauthorizedAccessException or IOException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                    ?error.Message:"Could not complete pipeline administration. Check PostgreSQL.";
        }
        finally
        {
            busy=false;
            binding=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void UpdateActions()
    {
        reloadButton.Enabled=!busy;
        newPipelineButton.Enabled=loaded&&!busy;
        pipelineBox.Enabled=loaded&&!busy&&pipelineBox.Items.Count>0;
        savePipelineButton.Enabled=pipelineNameBox.Enabled=pipelineDescriptionBox.Enabled=loaded&&!busy&&(newPipeline||Selected is not null);
        archivePipelineButton.Enabled=loaded&&!busy&&!newPipeline&&Selected is not null;
        newStageButton.Enabled=loaded&&!busy&&!newPipeline&&Selected is not null;
        saveStageButton.Enabled=stageNameBox.Enabled=probabilityBox.Enabled=outcomeBox.Enabled=colorBox.Enabled=
            newStageButton.Enabled&&(newStage||Stage is not null);
        outcomeBox.Enabled=saveStageButton.Enabled&&(newStage||Stage?["deals"] is 0L);
        stagesGrid.Enabled=newStageButton.Enabled;
        int index=Stage is DataRowView selected?selected.Row.Table.Rows.IndexOf(selected.Row):-1;
        moveUpButton.Enabled=newStageButton.Enabled&&!newStage&&index>0;
        moveDownButton.Enabled=newStageButton.Enabled&&!newStage&&index>=0&&stagesGrid.DataSource is DataTable table
            && index<table.Rows.Count-1;
        archiveStageButton.Enabled=newStageButton.Enabled&&!newStage&&index>=0&&stagesGrid.DataSource is DataTable records
            && records.Rows.Count>1;
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
