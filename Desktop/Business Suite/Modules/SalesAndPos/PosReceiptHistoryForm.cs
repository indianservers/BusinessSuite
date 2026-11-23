using System.Drawing.Printing;
using System.Runtime.InteropServices;
using System.Text;
using Npgsql;

namespace Business_Suite;

public sealed partial class PosReceiptHistoryForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int? invoice;
    private bool loading;
    private bool exporting;
    private bool canOutput;
    private int receiptSequence;
    private string printText = "";
    private int printOffset;

    public PosReceiptHistoryForm() => InitializeComponent();
    internal PosReceiptHistoryForm(SalesOrderRepository repository) : this() => this.repository = repository;

    internal PosReceiptHistoryForm(SalesOrderRepository repository, int invoice) : this(repository)
    {
        this.invoice = invoice;
        searchBox.Enabled = false;
    }

    private async void ReceiptsShown(object sender, EventArgs e) => await LoadAsync();
    private async void RefreshClicked(object sender, EventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        if (repository is null || loading || exporting)
            return;
        loading = true;
        refreshButton.Enabled = false;
        receiptGrid.DataSource = null;
        receiptBox.Clear();
        SetOutputButtons(false);
        statusLabel.Text = "Loading POS receipts…";
        try
        {
            var rows = invoice is int identity
                ? (await repository.FindPosReceiptForInvoiceAsync(identity) is { } exact
                    ? new List<PosReceiptIndexRow> { exact } : new List<PosReceiptIndexRow>())
                : await repository.ListPosReceiptsAsync(searchBox.Text);
            canOutput = await repository.CanExportPosReceiptsAsync();
            if (!IsDisposed)
            {
                receiptGrid.DataSource = rows;
                statusLabel.Text = rows.Count == 0 ? "No scoped POS receipts match the filter." : "";
            }
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not load POS receipts. Check PostgreSQL access and refresh.";
        }
        finally
        {
            loading = false;
            if (!IsDisposed)
                refreshButton.Enabled = true;
        }
    }

    private async void ReceiptSelected(object sender, EventArgs e)
    {
        int sequence = ++receiptSequence;
        receiptBox.Clear();
        SetOutputButtons(false);
        if (repository is null || receiptGrid.CurrentRow?.DataBoundItem is not PosReceiptIndexRow selected)
            return;
        try
        {
            var detail = await repository.LoadPosReceiptAsync(selected.CheckoutId, export: false);
            if (!IsDisposed && sequence == receiptSequence)
            {
                receiptBox.Text = detail.FormatText();
                SetOutputButtons(!exporting);
            }
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed && sequence == receiptSequence)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not reopen this receipt. Refresh and try again.";
        }
    }

    private async void ExportClicked(object sender, EventArgs e)
    {
        if (receiptGrid.CurrentRow?.DataBoundItem is not PosReceiptIndexRow selected)
            return;
        fileDialog.FileName = string.Concat(selected.Invoice.Select(ch => Path.GetInvalidFileNameChars().Contains(ch) ? '-' : ch)) + "-receipt.txt";
        if (fileDialog.ShowDialog(this) == DialogResult.OK)
            await OutputAsync(detail =>
            {
                File.WriteAllText(fileDialog.FileName, detail.FormatText(), new UTF8Encoding(false));
                return "Receipt saved.";
            });
    }

    private async void CopyClicked(object sender, EventArgs e) => await OutputAsync(detail =>
    {
        Clipboard.SetText(detail.FormatText());
        return "Receipt copied.";
    });

    private async void PrintClicked(object sender, EventArgs e)
    {
        try
        {
            if (printDialog.ShowDialog(this) != DialogResult.OK)
                return;
        }
        catch (Exception error) when (error is InvalidPrinterException or ExternalException)
        {
            statusLabel.Text = "The Windows printer chooser is unavailable.";
            return;
        }
        await OutputAsync(detail =>
        {
            receiptDocument.DocumentName = $"POS receipt {detail.Sale.Invoice}";
            printText = detail.FormatText();
            receiptDocument.Print();
            return "Receipt sent to the selected printer.";
        });
    }

    private async Task OutputAsync(Func<PosReceiptPrintData, string> output)
    {
        if (repository is null || exporting || receiptGrid.CurrentRow?.DataBoundItem is not PosReceiptIndexRow selected)
            return;
        exporting = true;
        SetOutputButtons(false);
        receiptGrid.Enabled = refreshButton.Enabled = false;
        try
        {
            var detail = await repository.LoadPosReceiptAsync(selected.CheckoutId, export: true);
            if (!IsDisposed)
                statusLabel.Text = output(detail);
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or NpgsqlException
            or TimeoutException or IOException or InvalidPrinterException or ExternalException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not output the receipt. Check the printer, clipboard or file destination.";
        }
        finally
        {
            exporting = false;
            if (!IsDisposed)
            {
                receiptGrid.Enabled = refreshButton.Enabled = true;
                SetOutputButtons(receiptBox.Text.Length > 0);
            }
        }
    }

    private void SetOutputButtons(bool enabled) => exportButton.Enabled = printButton.Enabled = copyButton.Enabled = enabled && canOutput;

    private void ReceiptBeginPrint(object sender, PrintEventArgs e) => printOffset = 0;

    private void ReceiptPrintPage(object sender, PrintPageEventArgs e)
    {
        using var font = new Font("Segoe UI", 10F);
        using var format = new StringFormat(StringFormat.GenericTypographic) { FormatFlags = StringFormatFlags.LineLimit };
        var bounds = new RectangleF(e.MarginBounds.X, e.MarginBounds.Y, e.MarginBounds.Width, e.MarginBounds.Height);
        if (bounds.Width <= 0 || bounds.Height <= 0)
            throw new InvalidOperationException("The selected paper margins do not leave room for a receipt.");
        string remaining = printText.Substring(printOffset);
        e.Graphics.MeasureString(remaining, font, bounds.Size, format, out int fit, out _);
        if (fit > 0 && fit < remaining.Length && char.IsHighSurrogate(remaining[fit - 1]))
            fit--;
        if (fit == 0 && remaining.Length > 0)
            throw new InvalidOperationException("The selected paper size cannot fit the receipt.");
        e.Graphics.DrawString(remaining.Substring(0, fit), font, Brushes.Black, bounds, format);
        printOffset += fit;
        e.HasMorePages = printOffset < printText.Length;
    }
}
