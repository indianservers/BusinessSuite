namespace Business_Suite;

public sealed partial class CrmQuoteLifecycleForm : Form
{
    private readonly QuoteDraftRepository? repository;
    private readonly int id;
    private readonly CancellationTokenSource lifetime=new();
    private QuoteLifecycle? selection;
    private bool saving;
    internal bool WasIssued { get; private set; }
    private sealed record ActionChoice(QuoteLifecycleAction Action,string Label);

    public CrmQuoteLifecycleForm()=>InitializeComponent();
    internal CrmQuoteLifecycleForm(QuoteDraftRepository repository,int id) : this()
    {
        this.repository=repository;
        this.id=id;
    }

    private async void ReviewShown(object sender,EventArgs e)
    {
        if (repository is null) return;
        var token=lifetime.Token;
        try
        {
            var record=await repository.ReadLifecycleAsync(id,token);
            if (token.IsCancellationRequested) return;
            selection=record;
            titleLabel.Text=record.Number;
            summary.Text=$"{record.Status} · Version {record.Version} · {record.Currency} {record.Total:N2}";
            termsBox.Text=record.Terms;
            linesGrid.DataSource=record.Lines;
            actionBox.DisplayMember=nameof(ActionChoice.Label);
            actionBox.DataSource=record.Actions.Select(action=>new ActionChoice(action,action switch
            {
                QuoteLifecycleAction.Submit=>"Submit for approval",
                QuoteLifecycleAction.Revise=>"Create next draft version",
                _=>action.ToString()
            })).ToList();
            actionBox.SelectedIndex=-1;
            actionBox.Enabled=record.Actions.Count>0;
            exportPdfButton.Text=record.IsIssued?"Save issued PDF copy":"Export draft PDF";
            exportPdfButton.Enabled=true;
            issuePdfButton.Enabled=record.CanIssue;
            feedback.Text=record.IsIssued?"Use the original issued PDF. Delivery is a separate action."
                :actionBox.Enabled?"Choose an approval or revision action.":"No approval or revision action is available.";
        }
        catch(OperationCanceledException) when(token.IsCancellationRequested) { }
        catch(Exception error) when(CrmQuotationsForm.Expected(error))
        {
            if (!token.IsCancellationRequested) feedback.Text=CrmQuotationsForm.Describe(error);
        }
    }

    private void ActionChanged(object sender,EventArgs e)=>applyButton.Enabled=!saving&&actionBox.SelectedItem is ActionChoice;

    private async void ApplyClicked(object sender,EventArgs e)
    {
        if (repository is null||selection is null||saving||actionBox.SelectedItem is not ActionChoice choice)
            return;
        saving=true;
        UpdatePdfButtons();
        try
        {
            await repository.ApplyLifecycleAsync(selection,choice.Action,commentsBox.Text,lifetime.Token);
            saving=false;
            DialogResult=DialogResult.OK;
            Close();
        }
        catch(Exception error) when(CrmQuotationsForm.Expected(error)) {feedback.Text=CrmQuotationsForm.Describe(error);}
        finally
        {
            saving=false;
            if (!IsDisposed)
                UpdatePdfButtons();
        }
    }

    private async void ExportPdfClicked(object sender,EventArgs e)
    {
        if (repository is null || selection is null || saving)
            return;
        var token=lifetime.Token;
        saving=true;
        UpdatePdfButtons();
        try
        {
            QuotePdfFile file=selection.IsIssued?await repository.IssuedPdfAsync(id,token):
                await repository.DraftPdfAsync(id,token);
            if (token.IsCancellationRequested)
                return;
            pdfDialog.FileName=file.Name;
            if (pdfDialog.ShowDialog(this)==DialogResult.OK)
            {
                File.WriteAllBytes(pdfDialog.FileName,file.Bytes);
                feedback.Text=selection.IsIssued?"Saved a copy of the original issued PDF.":"Saved a draft PDF. Quotation status is unchanged.";
            }
        }
        catch(OperationCanceledException) when(token.IsCancellationRequested) { }
        catch(Exception error) when(CrmQuotationsForm.Expected(error))
        {
            if (!token.IsCancellationRequested) feedback.Text=CrmQuotationsForm.Describe(error);
        }
        finally { saving=false;if (!token.IsCancellationRequested) UpdatePdfButtons(); }
    }

    private async void IssuePdfClicked(object sender,EventArgs e)
    {
        if (repository is null || selection is null || saving)
            return;
        saving=true;
        UpdatePdfButtons();
        try
        {
            await repository.IssuePdfAsync(selection,lifetime.Token);
            WasIssued=true;
            saving=false;
            DialogResult=DialogResult.OK;
            Close();
        }
        catch(Exception error) when(CrmQuotationsForm.Expected(error)) { feedback.Text=CrmQuotationsForm.Describe(error); }
        finally { saving=false;if (!IsDisposed) UpdatePdfButtons(); }
    }

    private void UpdatePdfButtons()
    {
        exportPdfButton.Enabled=!saving && selection is not null;
        issuePdfButton.Enabled=!saving && selection?.CanIssue==true;
        actionBox.Enabled=!saving && selection?.Actions.Count>0;
        doneButton.Enabled=!saving;
        ActionChanged(this,EventArgs.Empty);
    }

    private void ReviewClosing(object sender,FormClosingEventArgs e)=>e.Cancel=saving;
    private void ReviewClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
