using System.Globalization;

namespace Business_Suite;

internal sealed partial class AppointmentBillingForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly int appointment;
    private readonly CancellationTokenSource lifetime = new();
    private bool busy;
    private AppointmentBillingView? current;
    internal bool Changed { get; private set; }

    public AppointmentBillingForm() => InitializeComponent();

    internal AppointmentBillingForm(AppointmentRepository repository,int appointment) : this()
    {
        this.repository = repository;
        this.appointment = appointment;
        heading.Text = $"Booking #{appointment} · Charges & payments";
    }

    private async void BillingLoaded(object? sender,EventArgs e) => await ReadAsync();
    private async void RefreshClicked(object? sender,EventArgs e) => await ReadAsync();
    private void CloseClicked(object? sender,EventArgs e) => Close();

    private async void DraftClicked(object? sender,EventArgs e)
    {
        if (repository is null || busy || current?.CanDraft != true)
            return;
        var key = new AppointmentKey(appointment,current.Revision);
        await WriteAsync(() => repository.DraftAppointmentInvoiceAsync(key,lifetime.Token));
    }

    private async void ApproveClicked(object? sender,EventArgs e)
    {
        if (repository is null || busy || current?.CanApprove != true || current.InvoiceId is not int invoiceId)
            return;
        await WriteAsync(() => repository.ApproveAppointmentInvoiceAsync(appointment,invoiceId,lifetime.Token));
    }

    private async void ApplyAdvanceClicked(object? sender,EventArgs e)
    {
        if (repository is null || busy || current?.CanApplyAdvance != true)
            return;
        var key=new AppointmentKey(appointment,current.Revision);
        await WriteAsync(() => repository.ApplyAppointmentAdvancesAsync(key,lifetime.Token));
    }

    private async Task WriteAsync(Func<Task> action)
    {
        draft.Enabled = approve.Enabled = record.Enabled = applyAdvance.Enabled = refresh.Enabled = close.Enabled = false;
        busy = true;
        try
        {
            await action();
            Changed = true;
            busy = false;
            await ReadAsync();
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = AppointmentsForm.Friendly(error);
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
            {
                refresh.Enabled = close.Enabled = true;
                draft.Enabled = current?.CanDraft == true;
                approve.Enabled = current?.CanApprove == true;
                applyAdvance.Enabled = current?.CanApplyAdvance == true;
                UpdatePaymentButton();
            }
        }
    }

    private async void RecordClicked(object? sender,EventArgs e)
    {
        if (repository is null || busy || current is null || !record.Enabled)
            return;
        using var payment = new AppointmentPaymentForm(repository,appointment,current);
        if (payment.ShowDialog(this) == DialogResult.OK)
        {
            Changed = true;
            await ReadAsync();
        }
        UpdatePaymentButton();
    }

    private void UpdatePaymentButton()
    {
        bool pending = repository?.PaymentJournal(appointment).HasPending == true;
        record.Text = pending ? "Resume payment request" : "Record payment received";
        record.Enabled = !busy && current is { Grouped: false } && (current.CanCollect || pending);
    }

    private async Task ReadAsync()
    {
        if (repository is null || busy)
            return;
        busy = true;
        draft.Enabled = approve.Enabled = record.Enabled = applyAdvance.Enabled = refresh.Enabled = false;
        current = null;
        visit.Text = amounts.Text = invoice.Text = "";
        grid.DataSource = null;
        status.Text = "Loading payments…";
        try
        {
            var billing = await repository.ReadBillingAsync(appointment,lifetime.Token);
            if (lifetime.IsCancellationRequested)
                return;
            current = billing;
            visit.Text = "Visit status  " + Display(billing.Visit);
            if (billing.Grouped)
            {
                status.Text = "Billing for this appointment is managed by its linked service checkout.";
                return;
            }
            string Money(decimal value) => billing.Currency + " " + value.ToString("N2",CultureInfo.CurrentCulture);
            amounts.Text = $"Total {Money(billing.Total)}   ·   Paid {Money(billing.Paid)}   ·   Advance held {Money(billing.Advance)}   ·   Balance {Money(billing.Balance)}";
            invoice.Text = billing.Invoice is null ? "Invoice  Not created yet" : $"Invoice  {billing.Invoice} · {Display(billing.InvoiceStatus ?? "")}";
            grid.DataSource = billing.Receipts.DefaultView;
            status.Text = (billing.Visit is "cancelled" or "no_show") && billing.Advance > 0
                ? "The advance remains on the customer account."
                : billing.Receipts.Rows.Count == 0 ? "No payment receipts recorded for this appointment." : "";
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = AppointmentsForm.Friendly(error);
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
            {
                refresh.Enabled = true;
                draft.Enabled = current?.CanDraft == true;
                approve.Enabled = current?.CanApprove == true;
                applyAdvance.Enabled = current?.CanApplyAdvance == true;
                UpdatePaymentButton();
            }
        }
    }

    private static string Display(string value) =>
        CultureInfo.CurrentCulture.TextInfo.ToTitleCase(value.Replace('_',' '));

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        base.OnFormClosed(e);
    }
}
