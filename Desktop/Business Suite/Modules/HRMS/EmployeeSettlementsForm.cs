using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeSettlementsForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly int employee;
    private readonly int? record;
    private int? preferredSettlement;
    private readonly bool own;
    private readonly CancellationTokenSource lifetime = new();
    private EmployeeSettlementsView? view;
    private bool busy;
    private DataTable? adjustmentDraft;
    internal bool Changed { get; private set; }

    public EmployeeSettlementsForm() => InitializeComponent();

    internal EmployeeSettlementsForm(EmployeeAdministrationRepository repository, int employee, int? record, string employeeLabel, int? selectedSettlement = null, bool own = false) : this()
    {
        this.repository = repository;
        this.employee = employee;
        this.record = record;
        preferredSettlement = selectedSettlement;
        this.own = own;
        heading.Text = "Full & final settlement · " + employeeLabel;
    }

    private DataRow? Selected => (rows.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private async void SettleLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private void CloseClicked(object? sender, EventArgs e) => Close();
    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private async void SubmitClicked(object? sender, EventArgs e) => await DecideAsync("Submit");
    private async void ApproveClicked(object? sender, EventArgs e) => await DecideAsync("Approve");
    private async void RejectClicked(object? sender, EventArgs e) => await DecideAsync("Reject");
    private async void GenerateClicked(object? sender, EventArgs e) => await RunAsync(async () =>
    {
        if (record is not int exit)
            return;
        await repository!.GenerateSettlementAsync(employee, exit, notes.Text, lifetime.Token);
        Changed = true;
        notes.Clear();
        await ReadAsync();
        status.Text = "Draft generated from the exit last working date and payroll records.";
    });
    private async void PaidClicked(object? sender, EventArgs e) => await DecideAsync("Mark paid");

    private async void ExportClicked(object? sender,EventArgs e)
    {
        if (!export.Enabled || Selected is not DataRow row)
            return;
        int id = row.Field<int>("id");
        exportDialog.FileName = $"fnf-settlement-{id}.pdf";
        if (exportDialog.ShowDialog(this) != DialogResult.OK)
            return;
        await RunAsync(async () =>
        {
            var fresh = await repository!.ReadSettlementsAsync(employee, record, lifetime.Token, own);
            var printable = fresh.Settlements.Rows.Cast<DataRow>().FirstOrDefault(item => item.Field<int>("id") == id);
            if (printable?.Field<string>("status") is not ("approved" or "paid"))
                throw new InvalidOperationException("The settlement statement is available after approval.");
            var lines = fresh.Components.Rows.Cast<DataRow>().Where(item => item.Field<int>("settlement_id") == id);
            var presentation = await repository.ReadSettlementPresentationAsync(lifetime.Token);
            var logo = repository.ReadSettlementBrandAsset(presentation.Logo,"logo");
            var signature = repository.ReadSettlementBrandAsset(presentation.Signature,"signature");
            File.WriteAllBytes(exportDialog.FileName, EmployeeSettlementPdf.Render(printable!,lines,presentation.Template,logo,signature));
            status.Text = !presentation.Available ? "Settlement statement saved. The payroll presentation profile is unavailable." :
                (presentation.Logo is not null && logo is null) || (presentation.Signature is not null && signature is null)
                    ? "Settlement statement saved. A configured branding image is unavailable in local storage."
                    : "Settlement statement saved.";
        });
    }

    private void AdjustClicked(object? sender,EventArgs e)
    {
        if (!adjust.Enabled || Selected is not DataRow row)
            return;
        adjustmentDraft = view!.Components.DefaultView.ToTable();
        notes.Text = row.Field<string>("remarks") ?? string.Empty;
        components.DataSource = adjustmentDraft.DefaultView;
        status.Text = "Edit earning or deduction rows and save. Rows with blank names are omitted.";
        UpdateActions();
    }

    private void AddComponentClicked(object? sender,EventArgs e)
    {
        if (!addComponent.Enabled || adjustmentDraft is null || Selected is not DataRow row || (components.IsInEditMode && !components.EndEdit()))
            return;
        adjustmentDraft.Rows.Add(row.Field<int>("id"), "earning", "", 0m, "manual", "", true);
        components.CurrentRow = components.Rows[components.Rows.Count - 1];
        components.CurrentColumn = components_component_name;
        components.BeginEdit();
    }

    private async void SaveAdjustmentsClicked(object? sender,EventArgs e)
    {
        if (!saveAdjustments.Enabled || adjustmentDraft is null || Selected is not DataRow row || (components.IsInEditMode && !components.EndEdit()))
            return;
        await RunAsync(async () =>
        {
            var items = adjustmentDraft.Rows.Cast<DataRow>().Select(item => new EmployeeSettlementComponent(
                (item.Field<string>("line_type") ?? "").Trim().ToLowerInvariant(),
                item.Field<string>("component_name") ?? "", item.Field<decimal?>("amount") ?? 0,
                item.Field<string>("source") ?? "", item.Field<bool>("is_manual_adjustment"), item.Field<string>("remarks") ?? ""));
            await repository!.SaveSettlementAdjustmentsAsync(employee, record, row.Field<int>("id"), row.Field<string>("revision")!,
                items, notes.Text, lifetime.Token);
            adjustmentDraft = null;
            Changed = true;
            notes.Clear();
            await ReadAsync();
            status.Text = "Settlement adjustments saved.";
        });
    }

    private void CancelAdjustmentsClicked(object? sender,EventArgs e)
    {
        components.CancelEdit();
        adjustmentDraft = null;
        components.DataSource = view!.Components.DefaultView;
        notes.Clear();
        status.Text = "Settlement adjustments discarded.";
        UpdateActions();
    }

    private async Task ReadAsync()
    {
        view = await repository!.ReadSettlementsAsync(employee, record, lifetime.Token, own);
        var progress = view.Clearance;
        clearance.Text = record is null ? "Clearance  ·  No linked exit" : !progress.Available ? "Clearance unavailable" :
            progress.Total == 0 ? "Clearance  ·  Not started" :
            $"Clearance  {progress.Completed}/{progress.Total}  ·  {(progress.Completed == progress.Total ? "Cleared" : "Pending")}";
        rows.DataSource = view.Settlements.DefaultView;
        if (preferredSettlement is int requested)
        {
            var match = rows.Rows.FirstOrDefault(item => (item.DataBoundItem as DataRowView)?.Row.Field<int>("id") == requested);
            if (match is not null)
                rows.CurrentRow = match;
            preferredSettlement = null;
        }
        components.DataSource = view.Components.DefaultView;
        status.Text = view.Settlements.Rows.Count == 0 ? "No settlement is available." :
            own ? "Approved and paid settlement statements." : record is null ? "These settlements have no linked exit case." :
            "Mark paid records a completed payment in payroll and updates the exit case.";
    }

    private async Task DecideAsync(string action)
    {
        if (Selected is not DataRow row)
            return;
        await RunAsync(async () =>
        {
            await repository!.DecideSettlementAsync(employee, record, row.Field<int>("id"), row.Field<string>("revision")!,
                action, action == "Submit" ? string.Empty : notes.Text, lifetime.Token);
            Changed = true;
            notes.Clear();
            await ReadAsync();
            status.Text = "Settlement updated.";
        });
    }

    private void UpdateActions()
    {
        var selected = Selected;
        if (view is not null)
            view.Components.DefaultView.RowFilter = "settlement_id = " + (selected?.Field<int>("id") ?? 0);
        string? state = selected?.Field<string>("status");
        bool editing = adjustmentDraft is not null;
        submit.Enabled = !busy && !editing && view?.CanRun == true && state is "draft" or "rejected";
        approve.Enabled = reject.Enabled = !busy && !editing && view?.CanApprove == true && state == "pending_approval";
        paid.Enabled = !busy && !editing && (view?.CanApprove == true || view?.CanRun == true) && state == "approved";
        generate.Enabled = !busy && !editing && view?.CanGenerate == true;
        adjust.Enabled = submit.Enabled;
        export.Enabled = !busy && !editing && state is "approved" or "paid";
        rows.Enabled = !editing && !busy;
        components.ReadOnly = !editing || busy;
        components.MasterTemplate.AllowEditRow = editing && !busy;
        addComponent.Visible = saveAdjustments.Visible = cancelAdjustments.Visible = editing;
        addComponent.Enabled = saveAdjustments.Enabled = cancelAdjustments.Enabled = editing && !busy;
        notes.Enabled = (editing && !busy) || approve.Enabled || reject.Enabled || paid.Enabled || generate.Enabled;
        refresh.Enabled = !busy && !editing;
        close.Enabled = !busy && !editing;
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (UnauthorizedAccessException ex) { status.Text = ex.Message; }
        catch (InvalidOperationException ex) { status.Text = ex.Message; }
        catch (IOException) { status.Text = "The settlement statement could not be written to the selected file."; }
        catch (Npgsql.NpgsqlException) { status.Text = "PostgreSQL could not complete the settlement operation."; }
        finally
        {
            busy = false;
            if (!IsDisposed)
                UpdateActions();
        }
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        exportDialog.Dispose();
        base.OnFormClosed(e);
    }
}
