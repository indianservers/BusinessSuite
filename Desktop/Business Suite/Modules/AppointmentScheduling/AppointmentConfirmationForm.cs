using System.Runtime.InteropServices;
using System.Drawing.Printing;

namespace Business_Suite;

public sealed partial class AppointmentConfirmationForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly int id;
    private readonly CancellationTokenSource lifetime = new();
    private bool busy;
    private bool hasSummary;
    private readonly bool canCreate;
    private string slipText = "";
    private int slipOffset;

    public AppointmentConfirmationForm() => InitializeComponent();

    internal AppointmentConfirmationForm(AppointmentRepository repository, int id) : this(repository, id, false) { }

    internal AppointmentConfirmationForm(AppointmentRepository repository, int id, bool canCreate) : this()
    {
        this.repository = repository;
        this.id = id;
        this.canCreate = canCreate;
        anotherButton.Visible = sameCustomerButton.Visible = repeatButton.Visible = canCreate;
    }

    internal AppointmentRebookSeed? NewBooking { get; private set; }

    private async void RefreshClicked(object? sender, EventArgs e) => await ReadLatestAsync();

    private void AnotherClicked(object? sender, EventArgs e)
    {
        if (canCreate && !busy)
            StartBooking(new AppointmentRebookSeed(null));
    }

    private async void SameCustomerClicked(object? sender, EventArgs e) => await RebookAsync(false);
    private async void RepeatClicked(object? sender, EventArgs e) => await RebookAsync(true);

    private async Task RebookAsync(bool repeat)
    {
        if (canCreate && hasSummary)
            await ReadLatestAsync(summary =>
            {
                StartBooking(summary.Rebook(repeat));
                return "";
            });
    }

    private void StartBooking(AppointmentRebookSeed seed)
    {
        NewBooking = seed;
        DialogResult = DialogResult.OK;
        Close();
    }

    private async void ReferenceClicked(object? sender, EventArgs e) =>
        await ReadLatestAsync(summary =>
        {
            Clipboard.SetText(summary.Reference);
            return "Copied booking reference.";
        });

    private async void CopyClicked(object? sender, EventArgs e) =>
        await ReadLatestAsync(summary =>
        {
            Clipboard.SetText(summary.Summary);
            return "Copied customer-safe booking summary.";
        });

    private void PreviewMessageClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy || !hasSummary)
            return;
        using var preview = new AppointmentMessageForm(repository, id);
        preview.ShowDialog(this);
    }

    private async void CalendarClicked(object? sender, EventArgs e)
    {
        if (busy || !hasSummary)
            return;
        calendarDialog.FileName = $"booking-{id}.ics";
        if (calendarDialog.ShowDialog(this) != DialogResult.OK)
            return;
        await ReadLatestAsync(summary =>
        {
            summary.SaveCalendar(calendarDialog.FileName);
            return "Saved calendar event.";
        });
    }

    private async void PrintClicked(object? sender, EventArgs e)
    {
        if (busy || !hasSummary)
            return;
        try
        {
            if (printDialog.ShowDialog(this) != DialogResult.OK)
                return;
        }
        catch (Exception error) when (error is InvalidPrinterException or ExternalException)
        {
            feedback.Text = "The printer chooser is unavailable.";
            return;
        }
        await ReadLatestAsync(summary =>
        {
            slipDocument.DocumentName = $"Appointment slip #{summary.Reference}";
            slipText = summary.Summary;
            try
            {
                slipDocument.Print();
                return "Appointment slip sent to the selected printer.";
            }
            catch (Exception error) when (error is InvalidPrinterException or ExternalException)
            {
                return "The appointment slip could not be sent to the selected printer.";
            }
        });
    }

    private void BeginSlip(object? sender, PrintEventArgs e) => slipOffset = 0;

    private void PrintSlipPage(object? sender, PrintPageEventArgs e)
    {
        const string footer = "Appointment confirmation only. No payment receipt is issued by this slip.";
        using var titleFont = new Font("Segoe UI", 17F, FontStyle.Bold);
        using var bodyFont = new Font("Segoe UI", 10F);
        using var format = new StringFormat(StringFormat.GenericTypographic) { FormatFlags = StringFormatFlags.LineLimit };
        Rectangle bounds = e.MarginBounds;
        var graphics = e.Graphics;
        var body = new RectangleF(bounds.X, bounds.Y + 38, bounds.Width, bounds.Height - 68);
        if (body.Width <= 0 || body.Height <= 0)
            throw new InvalidOperationException("The selected printer margins do not leave space for the appointment slip.");
        graphics.DrawString(slipDocument.DocumentName, titleFont, Brushes.Black, bounds.X, bounds.Y);
        graphics.DrawString(footer, bodyFont, Brushes.Black,
            new RectangleF(bounds.X, bounds.Bottom - 24, bounds.Width, 24));
        string remaining = slipText.Substring(slipOffset);
        graphics.MeasureString(remaining, bodyFont, body.Size, format, out int fit, out _);
        if (fit < remaining.Length && fit > 0 && char.IsHighSurrogate(remaining[fit - 1]))
            fit--;
        if (fit == 0 && remaining.Length > 0)
            throw new InvalidOperationException("The appointment slip does not fit the selected paper size.");
        graphics.DrawString(remaining.Substring(0, fit), bodyFont, Brushes.Black, body, format);
        slipOffset += fit;
        e.HasMorePages = slipOffset < slipText.Length;
    }

    private async Task ReadLatestAsync(Func<AppointmentConfirmation, string>? action = null)
    {
        if (repository is null || busy)
            return;
        busy = true;
        var cancellation = lifetime.Token;
        UpdateButtons();
        feedback.Text = "Checking latest booking details…";
        try
        {
            var summary = await repository.ConfirmationAsync(id, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            hasSummary = true;
            heading.Text = $"Booking #{summary.Reference}";
            summaryBox.Text = summary.Summary;
            string? message = action?.Invoke(summary);
            if (!cancellation.IsCancellationRequested)
                feedback.Text = message ?? "Customer-safe summary. Calendar export does not send an invitation.";
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (ExternalException error) when (error is not Npgsql.NpgsqlException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text = "The clipboard is unavailable. Select and copy the summary text.";
        }
        catch (IOException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text = "Could not save the calendar event. Check the destination folder.";
        }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                hasSummary = false;
                summaryBox.Clear();
                feedback.Text = AppointmentsForm.Friendly(error);
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                busy = false;
                UpdateButtons();
            }
        }
    }

    private void UpdateButtons()
    {
        refreshButton.Enabled = !busy;
        referenceButton.Enabled = copyButton.Enabled = calendarButton.Enabled = printButton.Enabled = !busy && hasSummary;
        messageButton.Enabled = !busy && hasSummary;
        anotherButton.Enabled = !busy && canCreate;
        sameCustomerButton.Enabled = repeatButton.Enabled = !busy && canCreate && hasSummary;
    }

    private void WindowClosed(object? sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
        calendarDialog.Dispose();
        printDialog.Dispose();
        slipDocument.Dispose();
    }
}
