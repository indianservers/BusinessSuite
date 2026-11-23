using System.Globalization;
using Npgsql;
using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class CrmDealFilterForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly bool archived;
    private readonly CancellationTokenSource lifetime=new();
    private ILookup<string,CrmDealFilterChoice>? options;

    public CrmDealFilterForm() => InitializeComponent();

    internal CrmDealFilterForm(CrmDealRepository repository,CrmDealFilters current,bool archived) : this()
    {
        this.repository=repository;
        this.archived=archived;
        Filters=current;
    }

    internal CrmDealFilters Filters {get;private set;}=new();

    private async void FormShown(object sender,EventArgs e)
    {
        if (repository is null)
            return;
        var cancellation=lifetime.Token;
        try
        {
            var available=await repository.FilterOptionsAsync(archived,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            Bind(pipelineBox,available["pipeline"],Code(Filters.Pipeline));
            Bind(ownerBox,available["owner"],Code(Filters.Owner));
            Bind(teamBox,available["team"],Code(Filters.Team));
            Bind(currencyBox,available["currency"],Filters.Currency);
            Bind(priorityBox,available["priority"],Filters.Priority);
            Bind(typeBox,available["type"],Filters.Type);
            Bind(industryBox,available["industry"],Filters.Industry);
            Bind(sourceBox,available["source"],Filters.Source);
            Bind(lossBox,available["loss"],Filters.LostReason);
            Bind(enteredBox,available["entered"],Code(Filters.EnteredStage));
            options=available;
            LoadStages(Code(Filters.Stage));
            SetDate(fromBox,Filters.From);
            SetDate(untilBox,Filters.Until);
            noNextBox.Checked=Filters.NoNextAction;
            applyButton.Enabled=true;
            feedback.Text="";
        }
        catch(OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch(Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException or IOException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is UnauthorizedAccessException?error.Message:"Could not load deal filter options.";
        }
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }

    private void PipelineChanged(object sender,EventArgs e)
    {
        if (options is null)
            return;
        int? pipeline=ChoiceId(pipelineBox);
        string? previous=Choice(stageBox);
        bool visible=options["stage"].Any(item=>item.Value==previous && (pipeline is null || item.Pipeline==pipeline));
        LoadStages(visible?previous:null);
    }

    private void LoadStages(string? selected)
    {
        int? pipeline=ChoiceId(pipelineBox);
        if (options is not null)
            Bind(stageBox,options["stage"].Where(item=>pipeline is null || item.Pipeline==pipeline),selected);
    }

    private void ApplyClicked(object sender,EventArgs e)
    {
        var candidate=new CrmDealFilters(ChoiceId(pipelineBox),ChoiceId(stageBox),ChoiceId(ownerBox),ChoiceId(teamBox),
            Choice(currencyBox),Choice(priorityBox),Choice(typeBox),Choice(industryBox),Choice(sourceBox),Choice(lossBox),
            ChoiceId(enteredBox),fromBox.Checked?fromBox.Value.Date:null,untilBox.Checked?untilBox.Value.Date:null,noNextBox.Checked);
        try
        {
            candidate.Validate();
            Filters=candidate;
            DialogResult=DialogResult.OK;
        }
        catch(ArgumentException error)
        {
            feedback.Text=error.Message;
        }
    }

    private void ClearClicked(object sender,EventArgs e)
    {
        Filters=new();
        DialogResult=DialogResult.OK;
    }

    private static void SetDate(DateTimePicker box,DateTime? date)
    {
        if (date.HasValue)
            box.Value=date.Value;
        box.Checked=date.HasValue;
    }

    private static void Bind(RadDropDownList box,IEnumerable<CrmDealFilterChoice> values,string? selected)
    {
        var choices=new List<CrmDealFilterChoice> {new(null,"Any")};
        choices.AddRange(values);
        int index=choices.FindIndex(item=>item.Value==selected);
        if (selected is not null && index<0)
        {
            index=choices.Count;
            choices.Add(new(selected,"Previously selected"));
        }
        box.DisplayMember=nameof(CrmDealFilterChoice.Name);
        box.DataSource=choices;
        box.SelectedIndex=index;
    }

    private static string? Choice(RadDropDownList box)=>(box.SelectedItem?.DataBoundItem as CrmDealFilterChoice)?.Value;
    private static int? ChoiceId(RadDropDownList box)=>int.TryParse(Choice(box),NumberStyles.None,CultureInfo.InvariantCulture,out int id)?id:null;
    private static string? Code(int? id)=>id?.ToString(CultureInfo.InvariantCulture);
}
