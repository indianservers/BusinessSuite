using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealCloseForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly int id;
    private readonly CancellationTokenSource lifetime=new();
    private CrmDealClosing? original;
    private bool saving;

    public CrmDealCloseForm() => InitializeComponent();

    internal CrmDealCloseForm(CrmDealRepository repository,int id) : this()
    {
        this.repository=repository;
        this.id=id;
    }

    internal int? SalesOrderId { get; private set; }

    private async void ClosingShown(object sender,EventArgs e)
    {
        if (repository is null)
            return;
        CancellationToken cancellation=lifetime.Token;
        try
        {
            var value=await repository.ReadClosingAsync(id,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            original=value;
            businessDate.MaxDate=value.BusinessToday;
            businessDate.Value=value.BusinessToday;
            reengagementDate.MinDate=value.BusinessToday;
            reengagementDate.Value=value.BusinessToday;
            reengagementDate.Checked=false;
            finalValue.Value=Math.Min(finalValue.Maximum,Math.Max(0,value.Amount));
            currencyLabel.Text=value.Currency;
            quoteBox.DisplayMember=nameof(CrmDealQuoteChoice.Display);
            quoteBox.DataSource=value.Quotes;
            quoteBox.SelectedIndex=value.Quotes.Count==1?0:-1;
            outcomeBox.SelectedIndex=0;
            saveButton.Enabled=true;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=Describe(error);
        }
    }

    private void OutcomeChanged(object sender,EventArgs e)
    {
        bool won=outcomeBox.Text=="Won";
        onboardingBox.Visible=won;
        onboardingBox.Enabled=original?.CanCreateTask==true;
        reengagementDate.Visible=reengagementLabel.Visible=!won;
        reengagementDate.Enabled=original?.CanCreateTask==true;
        quoteBox.Enabled=won && (original?.Quotes.Count??0)>0;
        feedback.Text=!won?"The deal will be closed and the reason recorded in its history."
            : quoteBox.SelectedItem is CrmDealQuoteChoice quote
            ? $"Sales will use quotation {quote.Number} totals and lines."
            : "Won creates draft Sales records. Choose an approved quotation if one is linked to the deal.";
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (repository is null || original is null || saving)
            return;
        saving=true;
        saveButton.Enabled=cancelButton.Enabled=false;
        try
        {
            var closure=new CrmDealClosure(outcomeBox.Text,businessDate.Value.Date,finalValue.Value,reasonBox.Text.Trim(),
                contractBox.Text.Trim(),handoverBox.Text.Trim(),competitorBox.Text.Trim(),
                outcomeBox.Text=="Won"?quoteBox.SelectedItem as CrmDealQuoteChoice:null,
                outcomeBox.Text=="Won" && onboardingBox.Checked,
                outcomeBox.Text=="Lost" && reengagementDate.Checked?reengagementDate.Value.Date:null);
            SalesOrderId=await repository.CloseAsync(original.Original,closure,lifetime.Token);
            saving=false;
            DialogResult=DialogResult.OK;
            Close();
        }
        catch (Exception error) when (Expected(error))
        {
            feedback.Text=Describe(error);
        }
        finally
        {
            saving=false;
            if (!IsDisposed)
                saveButton.Enabled=cancelButton.Enabled=true;
        }
    }

    private void ClosingForm(object sender,FormClosingEventArgs e) => e.Cancel=saving;
    private void ClosedForm(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
    private static bool Expected(Exception error) => error is NpgsqlException or InvalidOperationException
        or ArgumentException or UnauthorizedAccessException or JsonException or TimeoutException or IOException;
    private static string Describe(Exception error) => error is InvalidOperationException or ArgumentException or UnauthorizedAccessException
        ? error.Message : "Could not close the deal. Check PostgreSQL and the deal setup.";
}
