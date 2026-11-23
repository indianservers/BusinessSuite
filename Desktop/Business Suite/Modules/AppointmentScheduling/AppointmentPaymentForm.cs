using System.Security.Cryptography;

namespace Business_Suite;

internal sealed partial class AppointmentPaymentForm : Form
{
    private static readonly string[] Methods = ["cash","upi","card","bank_transfer","cheque","other"];
    private readonly AppointmentRepository? repository;
    private readonly AppointmentBillingView? billing;
    private readonly int appointment;
    private readonly CancellationTokenSource lifetime = new();
    private ProtectedAppointmentJournal<AppointmentPaymentIntent>? journal;
    private FileStream? journalLock;
    private AppointmentPaymentIntent? pending;
    private bool busy;
    private bool refreshRequired;

    public AppointmentPaymentForm() => InitializeComponent();

    internal AppointmentPaymentForm(AppointmentRepository repository,int appointment,AppointmentBillingView billing) : this()
    {
        this.repository=repository;
        this.appointment=appointment;
        this.billing=billing;
    }

    private void PaymentLoaded(object? sender,EventArgs e)
    {
        if (repository is null || billing is null)
            return;
        try
        {
            journal=repository.PaymentJournal(appointment);
            journalLock=journal.Acquire();
            pending=journal.Read();
            balance.Text=$"Booking #{appointment}  ·  {billing.Currency} {billing.Balance:N2} outstanding";
            if (pending is not null)
            {
                amount.Value=pending.Amount;
                method.SelectedIndex=Array.IndexOf(Methods,pending.Method);
                reference.Text=pending.Reference;
                status.Text="Retry the saved payment request to verify its outcome.";
            }
            else if (billing.CanCollect)
            {
                amount.Maximum=billing.Balance;
                amount.Value=billing.Balance;
            }
            UpdateButtons();
        }
        catch (Exception error) when (AppointmentsForm.IsExpected(error) || error is CryptographicException)
        {
            journalLock?.Dispose();
            journalLock=null;
            status.Text=error is IOException ? "A payment window is already active or the local recovery file is unavailable." :
                AppointmentsForm.Friendly(error);
            UpdateButtons();
        }
    }

    private void CloseClicked(object? sender,EventArgs e) => Close();

    private async void SaveClicked(object? sender,EventArgs e)
    {
        if (!save.Enabled || repository is null || billing is null || journal is null)
            return;
        busy=true;
        UpdateButtons();
        try
        {
            if (pending is null)
            {
                var attempt=new AppointmentPaymentIntent(Guid.NewGuid(),billing.Revision,amount.Value,Methods[method.SelectedIndex],reference.Text.Trim());
                journal.Save(attempt);
                pending=attempt;
            }
            await repository.RecordAppointmentPaymentAsync(appointment,pending,lifetime.Token);
            journal.Clear();
            pending=null;
            DialogResult=DialogResult.OK;
        }
        catch (AppointmentPaymentRejectedException error)
        {
            try
            {
                journal.Clear();
                pending=null;
                refreshRequired=true;
                status.Text=error.Message;
            }
            catch (IOException) { status.Text="The rejected payment request could not be cleared from local recovery."; }
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error) || error is CryptographicException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text=pending is not null ? AppointmentsForm.Friendly(error)+" Retry the same saved request after reviewing this visit." :
                    error is CryptographicException ? "The payment request could not be saved securely." : AppointmentsForm.Friendly(error);
        }
        finally
        {
            busy=false;
            if (!IsDisposed)
                UpdateButtons();
        }
    }

    private void UpdateButtons()
    {
        bool canEnter = !busy && !refreshRequired && pending is null && journalLock is not null && billing?.CanCollect == true;
        amount.Enabled=method.Enabled=reference.Enabled=canEnter;
        save.Enabled=!busy && journalLock is not null && (canEnter || pending is not null);
        save.Text=pending is null ? "Record payment" : "Retry saved payment";
        close.Enabled=!busy;
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        journalLock?.Dispose();
        base.OnFormClosed(e);
    }
}
