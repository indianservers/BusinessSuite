using Npgsql;
using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class CrmDealCaptureForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly CancellationTokenSource lifetime=new();
    private DealCaptureOptions? options;
    private bool saving;

    public CrmDealCaptureForm() => InitializeComponent();
    internal CrmDealCaptureForm(CrmDealRepository repository) : this() => this.repository=repository;

    private async void FormShown(object sender,EventArgs e)
    {
        if (repository is null)
            return;
        var cancellation=lifetime.Token;
        try
        {
            options=await repository.CaptureOptionsAsync(cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            Bind(companyBox,options.Companies);
            CompanyChanged(this,EventArgs.Empty);
            Bind(stageBox,options.Stages);
            currencyBox.Text=options.Currency;
            saveButton.Enabled=options.Stages.Count>0;
            feedback.Text=saveButton.Enabled?"":"No active open stage is available.";
        }
        catch(OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch(Exception error) when (Expected(error) && !cancellation.IsCancellationRequested)
        {
            feedback.Text=Friendly(error);
        }
    }

    private void CompanyChanged(object sender,EventArgs e)
    {
        if (options is null)
            return;
        int? company=Choose(companyBox);
        Bind(contactBox,options.Contacts.Where(item=>item.Parent is null || item.Parent==company).ToList());
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (repository is null || saving || Choose(stageBox) is not int stage)
            return;
        saving=true;
        saveButton.Enabled=cancelButton.Enabled=false;
        feedback.Text="Creating deal…";
        try
        {
            int id=await repository.CaptureAsync(new(nameBox.Text,descriptionBox.Text,Choose(companyBox),Choose(contactBox),
                stage,currencyBox.Text,amountBox.Value,closeBox.Checked?closeBox.Value.Date:null,sourceBox.Text,duplicateBox.Text),
                lifetime.Token);
            CreatedId=id;
            saving=false;
            DialogResult=DialogResult.OK;
        }
        catch(Exception error) when (Expected(error))
        {
            feedback.Text=Friendly(error);
        }
        finally
        {
            saving=false;
            if (!IsDisposed)
                saveButton.Enabled=cancelButton.Enabled=true;
        }
    }

    internal int? CreatedId {get;private set;}

    private void FormIsClosing(object sender,FormClosingEventArgs e) => e.Cancel=saving;
    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }

    private static void Bind(RadDropDownList box,List<DealCaptureChoice> choices)
    {
        box.DisplayMember=nameof(DealCaptureChoice.Name);
        box.DataSource=choices;
        box.SelectedIndex=choices.Count>0?0:-1;
    }

    private static int? Choose(RadDropDownList box) => (box.SelectedItem?.DataBoundItem as DealCaptureChoice)?.Id;
    private static bool Expected(Exception error) => error is NpgsqlException or TimeoutException or IOException
        or ArgumentException or InvalidOperationException or UnauthorizedAccessException;
    private static string Friendly(Exception error) => error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
        ? error.Message : "Could not complete deal capture. Check PostgreSQL and try again.";
}
