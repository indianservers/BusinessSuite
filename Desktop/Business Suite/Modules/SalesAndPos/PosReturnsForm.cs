using Npgsql;

namespace Business_Suite;

public sealed partial class PosReturnsForm : Form
{
    private readonly SalesOrderRepository? repository;
    private SalesIntentJournal<PosReturnIntent>? journal;
    private FileStream? lease;
    private PosReturnIntent? pending;
    private bool loading;
    private bool recording;
    private bool canRecord;
    private int lineSequence;

    public PosReturnsForm() => InitializeComponent();
    internal PosReturnsForm(SalesOrderRepository repository) : this() => this.repository = repository;

    private async void ReturnsShown(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        conditionPicker.DataSource = new[]
        {
            new { Label = "Sellable", Code = "sellable" }, new { Label = "Damaged", Code = "damaged" },
            new { Label = "Goods not returned", Code = "not_returned" }
        };
        conditionPicker.DisplayMember = "Label";
        conditionPicker.ValueMember = "Code";
        conditionPicker.SelectedIndex = 0;
        try
        {
            canRecord = await repository.CanRecordPosReturnAsync();
            if (IsDisposed)
                return;
            if (canRecord)
            {
                journal = repository.PosReturnJournal();
                lease = journal.Acquire();
                pending = journal.Read();
                if (pending is not null)
                {
                    quantityEditor.Value = pending.Quantity;
                    conditionPicker.SelectedValue = pending.Condition;
                    methodBox.Text = pending.Method;
                    reasonBox.Text = pending.Reason;
                    restockCheck.Checked = pending.Restock;
                }
            }
            await LoadAsync();
        }
        catch (Exception error) when (error is UnauthorizedAccessException or IOException or NpgsqlException or TimeoutException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is IOException ? "The return recovery folder is unavailable or another window owns it." : error.Message;
        }
    }

    private void HistoryClicked(object sender, EventArgs e)
    {
        if (repository is null || recording)
            return;
        using var history = new PosReturnHistoryForm(repository);
        history.ShowDialog(this);
    }

    private async void RefreshClicked(object sender, EventArgs e) => await LoadAsync();

    private async Task LoadAsync(string? message = null)
    {
        if (repository is null || loading || recording)
            return;
        loading = true;
        salesGrid.DataSource = linesGrid.DataSource = null;
        ApplyState();
        statusLabel.Text = "Loading original POS sales…";
        try
        {
            var sales = await repository.ListPosReturnSalesAsync(searchBox.Text);
            if (IsDisposed)
                return;
            salesGrid.DataSource = sales;
            statusLabel.Text = message ?? (pending is not null ? "Resolve the saved return before entering another."
                : sales.Count == 0 ? "No paid POS sales match the filter." : "");
        }
        catch (Exception error) when (error is UnauthorizedAccessException or InvalidOperationException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is UnauthorizedAccessException or InvalidOperationException ? error.Message
                    : "Could not load original sales. Check PostgreSQL and refresh.";
        }
        finally
        {
            loading = false;
            if (!IsDisposed)
                ApplyState();
        }
    }

    private async void SaleSelected(object sender, EventArgs e)
    {
        int sequence = ++lineSequence;
        linesGrid.DataSource = null;
        if (repository is null || salesGrid.CurrentRow?.DataBoundItem is not PosReturnSale sale)
            return;
        try
        {
            var lines = await repository.PosReturnLinesAsync(sale.OrderId);
            if (IsDisposed || sequence != lineSequence)
                return;
            linesGrid.DataSource = lines;
            linesLabel.Text = lines.Any(line => line.Remaining > 0) ? "Original sale lines" : "No lines have remaining quantity";
            ApplyState();
        }
        catch (Exception error) when (error is UnauthorizedAccessException or InvalidOperationException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed && sequence == lineSequence)
                statusLabel.Text = error is UnauthorizedAccessException or InvalidOperationException ? error.Message
                    : "Could not load original sale lines.";
        }
    }

    private void LineSelected(object sender, EventArgs e)
    {
        if (pending is null && linesGrid.CurrentRow?.DataBoundItem is PosReturnSourceLine line)
            quantityEditor.Value = Math.Min(1m, line.Remaining);
        ApplyState();
    }

    private void ConditionChanged(object sender, EventArgs e)
    {
        if (conditionPicker.SelectedValue is string selected && selected != "sellable")
            restockCheck.Checked = false;
        ApplyState();
    }

    private async void RecordClicked(object sender, EventArgs e)
    {
        if (repository is null || journal is null || !recordButton.Enabled || recording)
            return;
        recording = true;
        ApplyState();
        string? complete = null;
        try
        {
            if (pending is null)
            {
                if (salesGrid.CurrentRow?.DataBoundItem is not PosReturnSale sale ||
                    linesGrid.CurrentRow?.DataBoundItem is not PosReturnSourceLine line || quantityEditor.Value > line.Remaining)
                    throw new ArgumentException("Choose a returnable line and quantity.");
                var intent = new PosReturnIntent(Guid.NewGuid(), sale.OrderId, line.Id, quantityEditor.Value,
                    conditionPicker.SelectedValue as string ?? "", restockCheck.Checked, methodBox.Text.Trim(), reasonBox.Text.Trim());
                journal.Save(intent);
                pending = intent;
            }
            statusLabel.Text = "Recording return…";
            var result = await repository.RecordPosReturnAsync(pending);
            journal.Clear();
            pending = null;
            complete = $"Return {result.Number} · {result.Currency} {result.Amount:N2} recorded.";
        }
        catch (PosReturnRejectedException error)
        {
            try
            {
                journal.Clear();
                pending = null;
                statusLabel.Text = error.Message;
            }
            catch (Exception storage) when (storage is IOException or UnauthorizedAccessException)
            {
                statusLabel.Text = "Return was rejected. Recovery storage could not be cleared.";
            }
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or ArgumentException
            or NpgsqlException or TimeoutException or IOException)
        {
            statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException or ArgumentException ? error.Message
                : pending is null ? "Could not save return recovery information. No request was sent."
                : "Return outcome is uncertain. Retry the same saved request.";
        }
        finally
        {
            recording = false;
            ApplyState();
        }
        if (complete is not null)
            await LoadAsync(complete);
    }

    private void ApplyState()
    {
        bool editable = !loading && !recording && canRecord && lease is not null && pending is null;
        quantityEditor.Enabled = conditionPicker.Enabled = methodBox.Enabled = reasonBox.Enabled = editable;
        restockCheck.Enabled = editable && conditionPicker.SelectedValue is string selected && selected == "sellable";
        salesGrid.Enabled = linesGrid.Enabled = !recording && pending is null;
        recordButton.Text = pending is null ? "Record return" : "Retry same return";
        recordButton.Enabled = !loading && !recording && canRecord && lease is not null &&
            (pending is not null || editable && linesGrid.CurrentRow?.DataBoundItem is PosReturnSourceLine { Remaining: > 0 });
        refreshButton.Enabled = !loading && !recording;
        closeButton.Enabled = !recording;
    }

    private void ReturnsClosing(object sender, FormClosingEventArgs e) => e.Cancel = recording;
    private void ReturnsClosed(object sender, FormClosedEventArgs e) => lease?.Dispose();
}
