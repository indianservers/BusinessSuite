using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealEditorForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly int id;
    private readonly CancellationTokenSource lifetime = new();
    private CrmDealEdit? original;
    private bool saving;

    public CrmDealEditorForm() => InitializeComponent();
    internal CrmDealEditorForm(CrmDealRepository repository,int id) : this()
    {
        this.repository=repository;
        this.id=id;
    }

    private async void EditorShown(object sender,EventArgs e)
    {
        if (repository is null)
            return;
        CancellationToken cancellation=lifetime.Token;
        try
        {
            var draft=await repository.EditAsync(id,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            original=draft;
            nameBox.Text=draft.Name;
            descriptionBox.Text=draft.Description;
            if (!priorityBox.Items.Contains(draft.Priority))
                priorityBox.Items.Add(draft.Priority);
            priorityBox.SelectedItem=draft.Priority;
            stageBox.DisplayMember=nameof(CrmDealStage.Name);
            stageBox.DataSource=draft.Stages;
            stageBox.SelectedIndex=draft.Stages.FindIndex(stage=>stage.Id==draft.Stage);
            amountBox.Value=Math.Max(0,draft.BusinessFields.Amount ?? 0);
            amountBox.Enabled=draft.CanEditAmount;
            if (!string.IsNullOrEmpty(draft.Currency))
                amountBoxLabel.Text=$"Amount ({draft.Currency})";
            sourceBox.Text=draft.BusinessFields.LeadSource;
            SetDate(expectedCloseBox,draft.BusinessFields.ExpectedClose);
            SetDate(nextActionBox,draft.BusinessFields.NextAction?.ToLocalTime());
            feedback.Text=draft.CanEditAmount?"Change the deal details or move it to another open stage."
                :"Product or service lines determine this deal's amount.";
            saveButton.Enabled=true;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=Describe(error);
        }
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (repository is null || original is null || saving || stageBox.SelectedItem is not CrmDealStage stage)
            return;
        saving=true;
        saveButton.Enabled=cancelButton.Enabled=false;
        try
        {
            var previous=original.BusinessFields;
            decimal? amount=!original.CanEditAmount || amountBox.Value==Math.Max(0,previous.Amount ?? 0)
                ?previous.Amount:amountBox.Value;
            var fields=new CrmDealBusinessFields(amount,LocalSelection(expectedCloseBox,previous.ExpectedClose)?.Date,
                NextAction(previous.NextAction),sourceBox.Text);
            await repository.SaveEditAsync(original,nameBox.Text.Trim(),descriptionBox.Text.Trim(),priorityBox.Text,
                stage.Id,lifetime.Token,fields);
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

    private DateTime? NextAction(DateTime? previousUtc)
    {
        DateTime? previous=previousUtc?.ToLocalTime();
        var local=LocalSelection(nextActionBox,previous);
        if (!local.HasValue || local==previous)
            return local.HasValue?previousUtc:null;
        var wallClock=DateTime.SpecifyKind(local.Value,DateTimeKind.Unspecified);
        if (TimeZoneInfo.Local.IsInvalidTime(wallClock))
            throw new ArgumentException("This local time does not exist on the selected date. Choose another time.");
        return TimeZoneInfo.ConvertTimeToUtc(wallClock,TimeZoneInfo.Local);
    }

    private static void SetDate(DateTimePicker box,DateTime? date)
    {
        box.Enabled=!date.HasValue || (date>=box.MinDate && date<=box.MaxDate);
        if (date.HasValue && box.Enabled)
            box.Value=date.Value;
        box.Checked=date.HasValue && box.Enabled;
    }

    private static DateTime? LocalSelection(DateTimePicker box,DateTime? previous) =>
        !box.Enabled?previous:box.Checked?box.Value:null;

    private void EditorClosing(object sender,FormClosingEventArgs e) => e.Cancel=saving;
    private void EditorClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
    private static bool Expected(Exception error) => error is NpgsqlException or InvalidOperationException
        or ArgumentException or UnauthorizedAccessException or JsonException or TimeoutException or IOException;
    private static string Describe(Exception error) => error is InvalidOperationException or ArgumentException or UnauthorizedAccessException
        ? error.Message : "Could not save the deal. Check the stage policy and PostgreSQL connection.";
}
