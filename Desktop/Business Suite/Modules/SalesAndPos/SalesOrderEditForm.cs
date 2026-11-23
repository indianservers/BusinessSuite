using System.ComponentModel;
using Npgsql;

namespace Business_Suite;

internal sealed class SalesOrderEditableLine(SalesOrderEditLine original)
{
    public string ItemCode => original.ItemCode;
    public string Description { get; set; } = original.Description;
    public decimal Quantity { get; set; } = original.Quantity;
    public decimal UnitPrice { get; set; } = original.UnitPrice;
    public decimal Discount { get; set; } = original.Discount;
    public decimal Tax { get; set; } = original.Tax;

    internal SalesOrderEditLine Snapshot() =>
        original with { Description = Description, Quantity = Quantity, UnitPrice = UnitPrice, Discount = Discount, Tax = Tax };
}

public sealed partial class SalesOrderEditForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly SalesOrderEdit? original;
    private readonly Guid request = Guid.NewGuid();
    private BindingList<SalesOrderEditableLine>? lines;
    private bool saving;

    public SalesOrderEditForm()
    {
        InitializeComponent();
    }

    internal SalesOrderEditForm(SalesOrderRepository repository, SalesOrderEdit original) : this()
    {
        this.repository = repository;
        this.original = original;
        Text = $"Edit sales order {original.Number}";
        titleBox.Text = original.Title;
        termsBox.Text = original.Terms;
        SetDate(startBox, original.Schedule.Start);
        SetDate(endBox, original.Schedule.End);
        lines = new BindingList<SalesOrderEditableLine>(original.Lines.Select(line => new SalesOrderEditableLine(line)).ToList());
        linesGrid.DataSource = lines;
        linesGrid.ReadOnly = original.HasInvoice || original.Lines.Count > 200;
        if (original.HasInvoice)
            linesLabel.Text = "Order items · An invoice is linked to this order";
        else if (original.Lines.Count > 200)
            linesLabel.Text = "Order items · This document exceeds the editable item limit";
    }

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (saving || repository is null || original is null)
            return;
        if (linesGrid.IsInEditMode && !linesGrid.EndEdit())
        {
            statusLabel.Text = "Correct the current order item before saving.";
            return;
        }
        var requested = lines?.Select(line => line.Snapshot()).ToArray();
        var changes = requested is not null && !requested.SequenceEqual(original.Lines) ? requested : null;
        saving = true;
        saveButton.Enabled = false;
        cancelButton.Enabled = false;
        linesGrid.Enabled = false;
        statusLabel.Text = "Saving…";
        try
        {
            var schedule = new SalesOrderSchedule(startBox.Checked ? startBox.Value.Date : null,
                endBox.Checked ? endBox.Value.Date : null);
            await repository.EditSalesOrderScheduleAsync(original, titleBox.Text, termsBox.Text,
                reasonBox.Text, request, changes, schedule);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is InvalidOperationException or ArgumentException or
            UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            statusLabel.Text = error is NpgsqlException or TimeoutException
                ? "Could not confirm the save. Retry with the same values or refresh the order."
                : error.Message;
        }
        finally
        {
            saving = false;
            if (!IsDisposed)
            {
                saveButton.Enabled = true;
                cancelButton.Enabled = true;
                linesGrid.Enabled = true;
            }
        }
    }

    private static void SetDate(DateTimePicker picker, DateTime? date)
    {
        if (date.HasValue)
            picker.Value = date.Value;
        picker.Checked = date.HasValue;
    }

    private void EditorClosing(object sender, FormClosingEventArgs e)
    {
        if (saving && DialogResult != DialogResult.OK)
            e.Cancel = true;
    }
}
