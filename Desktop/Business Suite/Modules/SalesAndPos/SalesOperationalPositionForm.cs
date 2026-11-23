using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class SalesOperationalPositionForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private SalesPositionOptions? options;
    private bool busy;
    private Guid request = Guid.NewGuid();
    private PendingMove? pending;

    public SalesOperationalPositionForm() => InitializeComponent();

    internal SalesOperationalPositionForm(SalesOrderRepository repository, int order, string number) : this()
    {
        this.repository = repository;
        this.order = order;
        titleLabel.Text = $"Operational stage | {number}";
    }

    internal bool Changed { get; private set; }

    private async void ReloadClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || pending is not null)
            return;
        busy = true;
        UpdateButtons();
        try
        {
            options = await repository.SalesPositionOptionsAsync(order);
            currentLabel.Text = options.Current is { } current ? $"Current: {current.PipelineName} | {current.StageName}" : "Current: Unassigned";
            pipelineBox.DisplayMember = nameof(SalesOperationPipeline.Name);
            pipelineBox.DataSource = options.Pipelines;
            if (options.Current?.Pipeline is int pipeline)
                pipelineBox.SelectedIndex = options.Pipelines.FindIndex(item => item.Id == pipeline);
            statusLabel.Text = options.Pipelines.Count == 0 ? "There are no configured Sales pipelines."
                : options.CanMove ? "" : "This Sales order is available for review.";
        }
        catch (Exception error) when (IsExpected(error))
        {
            options = null;
            statusLabel.Text = Describe(error);
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private void PipelineChanged(object sender, EventArgs e)
    {
        if (stageBox is null)
            return;
        var selected = pipelineBox.SelectedItem?.DataBoundItem as SalesOperationPipeline;
        var stages = new List<SalesOperationStage>();
        if (selected is not null)
        {
            stages.AddRange(selected.Stages);
            stages.Add(new SalesOperationStage("unassigned", "Unassigned", Array.Empty<string>(), Array.Empty<string>(), null));
        }
        stageBox.DisplayMember = nameof(SalesOperationStage.Name);
        stageBox.DataSource = stages;
        stageBox.SelectedIndex = selected is not null && options?.Current is { } current && selected.Id == current.Pipeline
            ? stages.FindIndex(stage => stage.Id == current.Stage) : -1;
        UpdateButtons();
    }

    private void StageChanged(object sender, EventArgs e) => UpdateButtons();

    private async void MoveClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || options?.CanMove != true ||
            pipelineBox.SelectedItem?.DataBoundItem is not SalesOperationPipeline pipeline ||
            stageBox.SelectedItem?.DataBoundItem is not SalesOperationStage stage)
            return;
        busy = true;
        UpdateButtons();
        try
        {
            pending ??= new PendingMove(pipeline.Id, pipeline.Version, stage.Id, options.Current?.Event);
            var moved = await repository.MoveSalesPositionAsync(order, pending.Pipeline, pending.Version,
                pending.Stage, pending.Expected, request);
            Changed |= moved.Event != options.Current?.Event;
            statusLabel.Text = "Stage saved. Configured automation requires the workflow service.";
            pending = null;
            request = Guid.NewGuid();
            options = options with { Current = moved };
            currentLabel.Text = $"Current: {moved.PipelineName} | {moved.StageName}";
        }
        catch (Exception error) when (IsExpected(error))
        {
            if (error is not (NpgsqlException or TimeoutException) || error is PostgresException)
                pending = null;
            statusLabel.Text = pending is not null ? "Could not confirm the result. Retry the original move." : Describe(error);
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private void UpdateButtons()
    {
        if (reloadButton is null || moveButton is null || stageBox is null)
            return;
        reloadButton.Enabled = !busy && pending is null;
        pipelineBox.Enabled = stageBox.Enabled = !busy && pending is null && options?.CanMove == true;
        moveButton.Enabled = !busy && options?.CanMove == true &&
            pipelineBox.SelectedItem?.DataBoundItem is SalesOperationPipeline && stageBox.SelectedItem?.DataBoundItem is SalesOperationStage;
        moveButton.Text = pending is null ? "Move order" : "Retry move";
    }

    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = busy;

    private static bool IsExpected(Exception error) => error is NpgsqlException or TimeoutException or InvalidOperationException
        or UnauthorizedAccessException or ArgumentException or JsonException;
    private static string Describe(Exception error) => error is NpgsqlException or TimeoutException
        ? "Could not load or save the Sales stage." : error.Message;

    private sealed record PendingMove(int Pipeline, int Version, string Stage, int? Expected);
}
