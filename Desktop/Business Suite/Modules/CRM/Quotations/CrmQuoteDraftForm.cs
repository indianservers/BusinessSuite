using System.ComponentModel;

namespace Business_Suite;

public sealed partial class CrmQuoteDraftForm : Form
{
    private readonly QuoteDraftRepository? repository;
    private readonly int? id;
    private readonly CancellationTokenSource lifetime=new();
    private readonly BindingList<QuoteDraftLine> lines=new();
    private QuoteDraft? original;
    private bool loading,saving;

    public CrmQuoteDraftForm() => InitializeComponent();
    internal CrmQuoteDraftForm(QuoteDraftRepository repository,int? id) : this()
    {
        this.repository=repository;
        this.id=id;
    }

    private async void DraftShown(object sender,EventArgs e)
    {
        if (repository is null)
            return;
        loading=true;
        var token=lifetime.Token;
        try
        {
            var options=await repository.OptionsAsync(!id.HasValue,token);
            var draft=id.HasValue?await repository.ReadAsync(id.Value,token):null;
            if (token.IsCancellationRequested) return;
            original=draft;
            customerBox.DisplayMember=nameof(QuoteChoice.Name);
            customerBox.DataSource=options.Customers;
            customerBox.SelectedIndex=draft is null?-1:options.Customers.FindIndex(item=>item.Id==draft.Customer);
            dealBox.DisplayMember=nameof(QuoteChoice.Name);
            dealBox.DataSource=options.Deals;
            dealBox.SelectedIndex=draft?.Deal is int deal?options.Deals.FindIndex(item=>item.Id==deal):0;
            numberBox.Text=draft?.Number??"";
            currencyBox.Text=draft?.Currency??options.Currency;
            issuePicker.Value=draft?.Issue??DateTime.Today;
            expiryPicker.Value=draft?.Expiry??DateTime.Today.AddDays(30);
            termsBox.Text=draft?.Terms??"";
            notesBox.Text=draft?.Notes??"";
            if (draft is not null)
                foreach(var line in draft.Lines) lines.Add(line);
            linesGrid.DataSource=lines;
            saveButton.Enabled=addLineButton.Enabled=true;
            Preview();
        }
        catch(OperationCanceledException) when(token.IsCancellationRequested) { }
        catch(Exception error) when(CrmQuotationsForm.Expected(error))
        {
            if (!token.IsCancellationRequested) feedback.Text=CrmQuotationsForm.Describe(error);
        }
        finally {loading=false;}
    }

    private void DealChanged(object sender,EventArgs e)
    {
        if (loading || dealBox.SelectedItem is not QuoteChoice {Id:>0} deal)
            return;
        if (deal.Company.HasValue && customerBox.DataSource is List<QuoteChoice> customers)
            customerBox.SelectedIndex=customers.FindIndex(item=>item.Id==deal.Company);
        if (deal.Currency.Length>0)
            currencyBox.Text=deal.Currency;
    }
    private void AddLineClicked(object sender,EventArgs e)
    {
        linesGrid.EndEdit();
        lines.Add(new());
        Preview();
    }
    private void RemoveLineClicked(object sender,EventArgs e)
    {
        linesGrid.EndEdit();
        if (linesGrid.CurrentRow?.DataBoundItem is QuoteDraftLine line)
            lines.Remove(line);
        Preview();
    }
    private void ReviewClicked(object sender,EventArgs e)
    {
        linesGrid.EndEdit();
        Preview();
    }
    private void Preview()
    {
        removeLineButton.Enabled=lines.Count>0;
        try
        {
            var amounts=lines.Select(QuoteDraftRepository.Calculate).ToArray();
            feedback.Text=$"Subtotal {amounts.Sum(v=>v.Gross):N2}  ·  Discount {amounts.Sum(v=>v.Discount):N2}  ·  Tax {amounts.Sum(v=>v.Tax):N2}  ·  Total {amounts.Sum(v=>v.Total):N2}";
        }
        catch(Exception error) when(CrmQuotationsForm.Expected(error)) { feedback.Text=CrmQuotationsForm.Describe(error); }
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (repository is null || saving || !saveButton.Enabled)
            return;
        linesGrid.EndEdit();
        if (customerBox.SelectedItem is not QuoteChoice customer || dealBox.SelectedItem is not QuoteChoice deal)
        {
            feedback.Text="Choose a customer and either an available linked deal or No linked deal.";
            return;
        }
        saving=true;
        saveButton.Enabled=cancelButton.Enabled=false;
        try
        {
            var draft=new QuoteDraft(id,original?.Revision??"",original?.LineRevision??"",numberBox.Text,customer.Id,
                deal.Id>0?deal.Id:null,issuePicker.Value,expiryPicker.Value,currencyBox.Text,termsBox.Text,notesBox.Text,lines.ToList());
            await repository.SaveAsync(draft,lifetime.Token);
            saving=false;
            DialogResult=DialogResult.OK;
            Close();
        }
        catch(Exception error) when(CrmQuotationsForm.Expected(error)) {feedback.Text=CrmQuotationsForm.Describe(error);}
        finally
        {
            saving=false;
            if (!IsDisposed) saveButton.Enabled=cancelButton.Enabled=true;
        }
    }
    private void DraftClosing(object sender,FormClosingEventArgs e)=>e.Cancel=saving;
    private void DraftClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
