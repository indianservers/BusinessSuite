using System.ComponentModel;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class SalesPipelineConfigurationForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly BindingList<EditableStage> stages = new();
    private bool busy;
    private bool ready;
    private Guid request = Guid.NewGuid();
    private PendingSave? pending;

    public SalesPipelineConfigurationForm() => InitializeComponent();

    internal SalesPipelineConfigurationForm(SalesOrderRepository repository) : this()
    {
        this.repository = repository;
        stageGrid.DataSource = stages;
    }

    private async void FormShown(object sender, EventArgs e) => await LoadDefinitionsAsync(null);
    private async void ReloadClicked(object sender, EventArgs e) => await LoadDefinitionsAsync(Current?.Id);
    private SalesOperationPipeline? Current => (pipelineBox.SelectedItem?.DataBoundItem as PipelineChoice)?.Pipeline;

    private async Task LoadDefinitionsAsync(int? selected)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        try
        {
            var result = await repository.ListSalesPipelineDefinitionsAsync();
            var options = new[] { new PipelineChoice("New Sales pipeline", null) }
                .Concat(result.Select(pipeline => new PipelineChoice(pipeline.Name, pipeline))).ToList();
            pipelineBox.DisplayMember = nameof(PipelineChoice.Label);
            pipelineBox.DataSource = options;
            pipelineBox.SelectedIndex = selected.HasValue ? Math.Max(0, options.FindIndex(item => item.Pipeline?.Id == selected)) : 0;
            ApplyCurrent();
            ready = true;
            statusLabel.Text = "";
        }
        catch (Exception error) when (IsExpected(error))
        {
            ready = false;
            statusLabel.Text = Describe(error);
        }
        finally
        {
            busy = false;
            UpdateActions();
        }
    }

    private void PipelineChanged(object sender, EventArgs e)
    {
        if (!busy && repository is not null)
            ApplyCurrent();
    }

    private void ApplyCurrent()
    {
        request = Guid.NewGuid();
        pending = null;
        var current = Current;
        nameBox.Text = current?.Name ?? "";
        stages.Clear();
        foreach (var item in current?.Stages ?? new List<SalesOperationStage>())
            stages.Add(new EditableStage(item));
        UpdateActions();
    }

    private void AddStage(object sender, EventArgs e)
    {
        if (!busy && pending is null && stages.Count < 30)
            stages.Add(new EditableStage(new SalesOperationStage($"new:{Guid.NewGuid():N}", "", Array.Empty<string>(), Array.Empty<string>(), null)));
        if (stageGrid.Rows.Count > 0)
            stageGrid.CurrentRow = stageGrid.Rows[stageGrid.Rows.Count - 1];
        UpdateActions();
    }

    private void RemoveStage(object sender, EventArgs e)
    {
        if (!busy && pending is null && stageGrid.CurrentRow?.DataBoundItem is EditableStage { IsNew: true } selected)
            stages.Remove(selected);
        UpdateActions();
    }

    private void MoveUp(object sender, EventArgs e) => ReorderStage(-1);
    private void MoveDown(object sender, EventArgs e) => ReorderStage(1);
    private void SelectionChanged(object sender, EventArgs e) => UpdateActions();

    private void ReorderStage(int delta)
    {
        if (busy || pending is not null || stageGrid.CurrentRow?.DataBoundItem is not EditableStage selected)
            return;
        if (stageGrid.IsInEditMode && !stageGrid.EndEdit())
            return;
        int index = stages.IndexOf(selected), next = index + delta;
        if (next < 0 || next >= stages.Count)
            return;
        stages.RemoveAt(index);
        stages.Insert(next, selected);
        stageGrid.CurrentRow = stageGrid.Rows[next];
        UpdateActions();
    }

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || !ready || stageGrid.IsInEditMode && !stageGrid.EndEdit())
            return;
        busy = true;
        UpdateActions();
        int? saved = null;
        try
        {
            pending ??= new PendingSave(Current?.Id, Current?.Version ?? 0, nameBox.Text, stages.Select(row => row.Snapshot()).ToArray());
            saved = await repository.SaveSalesPipelineDefinitionAsync(pending.Id, pending.Version, pending.Name, pending.Stages, request);
            pending = null;
        }
        catch (Exception error) when (IsExpected(error))
        {
            if (error is not (NpgsqlException or TimeoutException) || error is PostgresException)
                pending = null;
            statusLabel.Text = pending is null ? Describe(error) : "Could not confirm the save. Retry the same settings.";
        }
        finally
        {
            busy = false;
            UpdateActions();
        }
        if (saved.HasValue)
        {
            await LoadDefinitionsAsync(saved);
            if (ready)
                statusLabel.Text = "Sales pipeline saved.";
        }
    }

    private void UpdateActions()
    {
        if (saveButton is null || stageGrid is null)
            return;
        bool editing = ready && !busy && pending is null;
        pipelineBox.Enabled = nameBox.Enabled = stageGrid.Enabled = editing;
        reloadButton.Enabled = !busy && pending is null;
        addButton.Enabled = editing && stages.Count < 30;
        var row = stageGrid.CurrentRow?.DataBoundItem as EditableStage;
        int index = row is null ? -1 : stages.IndexOf(row);
        removeButton.Enabled = editing && row?.IsNew == true;
        upButton.Enabled = editing && index > 0;
        downButton.Enabled = editing && index >= 0 && index < stages.Count - 1;
        saveButton.Enabled = ready && !busy && stages.Count > 0;
        saveButton.Text = pending is null ? "Save pipeline" : "Retry save";
    }

    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = busy;
    private static bool IsExpected(Exception error) => error is NpgsqlException or TimeoutException or InvalidOperationException
        or UnauthorizedAccessException or ArgumentException or JsonException;
    private static string Describe(Exception error) => error is NpgsqlException or TimeoutException
        ? "Could not load or save Sales pipeline configuration." : error.Message;

    private sealed record PipelineChoice(string Label, SalesOperationPipeline? Pipeline);
    private sealed record PendingSave(int? Id, int Version, string Name, SalesOperationStage[] Stages);

    private sealed class EditableStage(SalesOperationStage stage)
    {
        public string Name { get; set; } = stage.Name;
        public int? Capacity { get; set; } = stage.Capacity;
        public int AgingDays { get; set; } = stage.AgingDays;
        public bool Terminal { get; set; } = stage.Terminal;
        public string Required { get; set; } = string.Join(", ", stage.Required);
        public string Statuses { get; set; } = string.Join(", ", stage.Statuses);
        internal bool IsNew => stage.Id.StartsWith("new:", StringComparison.Ordinal);
        internal SalesOperationStage Snapshot() => stage with
        {
            Name = Name, Capacity = Capacity, AgingDays = AgingDays, Terminal = Terminal,
            Required = Split(Required), Statuses = Split(Statuses)
        };
        private static string[] Split(string value) => (value ?? "").Split(',').Select(item => item.Trim())
            .Where(item => item.Length > 0).ToArray();
    }
}
