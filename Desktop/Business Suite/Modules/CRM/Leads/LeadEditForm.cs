using System.Data;
using System.Globalization;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class LeadEditForm : Form
{
    private sealed record OwnerOption(int? Id,string Name);
    private readonly DataRow? original;
    private readonly bool potential;
    private readonly CancellationTokenSource lifetime = new();
    private readonly Dictionary<string, Control> fields;
    private bool saving;
    private int branchLoad;
    private bool loadedBranches;

    public LeadEditForm() : this(null) { }

    internal LeadEditForm(DataRow? row, bool potential = false)
    {
        original = row;
        this.potential = potential;
        InitializeComponent();
        fields = new Dictionary<string, Control>
        {
            ["first_name"] = first_nameBox,
            ["last_name"] = last_nameBox,
            ["company_name"] = company_nameBox,
            ["job_title"] = job_titleBox,
            ["email"] = emailBox,
            ["source"] = sourceBox,
            ["phone_country_code"] = phone_country_codeBox,
            ["phone"] = phoneBox,
            ["alternate_phone_country_code"] = alternate_phone_country_codeBox,
            ["alternate_phone"] = alternate_phoneBox,
            ["status"] = statusBox,
            ["rating"] = ratingBox,
            ["estimated_value"] = estimated_valueBox,
            ["expected_close_date"] = expected_close_dateBox,
            ["next_follow_up_at"] = next_follow_up_atBox,
            ["industry"] = industryBox,
            ["website"] = websiteBox,
            ["company_website"] = company_websiteBox,
            ["linkedin_url"] = linkedin_urlBox,
            ["address"] = addressBox,
            ["city"] = cityBox,
            ["state"] = stateBox,
            ["country"] = countryBox,
            ["tags_text"] = tags_textBox,
            ["need"] = needBox,
            ["budget"] = budgetBox,
            ["decisionMaker"] = decisionMakerBox,
            ["timeline"] = timelineBox,
            ["lossReason"] = lossReasonBox,
            ["competitor"] = competitorBox,
            ["notes"] = notesBox
        };
        string recordLabel = potential ? "potential client" : "lead";
        heading.Text = row is null ? $"New {recordLabel}" : $"Edit {recordLabel}";
        branchLabel.Visible = branchBox.Visible = row is null;
        captureOwnerLabel.Visible=captureOwnerBox.Visible=row is null && !potential;
        foreach (ComboBox combo in new[] { phone_country_codeBox, alternate_phone_country_codeBox })
            combo.Items.AddRange(CrmPhone.CallingCodes);
        ratingBox.Items.AddRange(LeadStore.Ratings);

        foreach (var field in fields.Where(pair => pair.Key != "status"))
            field.Value.Text = Value(field.Key);

        string Value(string key)
        {
            if (row is null)
                return key switch
                {
                    "source" => "Other", "rating" => "Warm", "phone_country_code" or "alternate_phone_country_code" => CrmPhone.DefaultCallingCode,
                    _ => ""
                };
            if (key is "need" or "budget" or "decisionMaker" or "timeline")
                return LeadStore.Qualification(LeadStore.ReadDetails(row), key);
            if (key is "lossReason" or "competitor")
                return LeadStore.Detail(LeadStore.ReadDetails(row), key);
            if (row[key] is DateTime date)
                return key == "next_follow_up_at" ? date.ToLocalTime().ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture)
                    : date.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
            return LeadStore.Text(row, key);
        }
    }

    private async void EditorShown(object sender, EventArgs e)
    {
        CancellationToken cancellation = lifetime.Token;
        try
        {
            LeadPolicy policy = await LeadStore.PolicyAsync(cancellation);
            var choices = await CrmDirectoryWrites.ReadEditorChoicesAsync("leads", original is null, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            string previous = original is null ? "New" : LeadStore.Text(original, "status");
            LeadStage? oldStage = policy.Stages.FirstOrDefault(stage => stage.Name == previous);
            statusBox.Items.AddRange(policy.Stages.Where(stage => original is null
                ? stage.Name != "Converted" : stage.Name == previous || stage.Name != "Converted" &&
                (oldStage?.AllowedNext.Contains(stage.Name) ?? true)).Select(stage => stage.Name).ToArray());
            statusBox.SelectedItem = previous;
            if (statusBox.SelectedIndex < 0 && statusBox.Items.Count != 0)
                statusBox.SelectedIndex = 0;
            branchBox.DisplayMember = nameof(CrmLookup.Name);
            branchBox.DataSource = choices.Branches;
            int selected = choices.Branches.FindIndex(branch => branch.Id == choices.DefaultBranch);
            branchBox.SelectedIndex = selected >= 0 ? selected : choices.Branches.Count == 1 ? 0 : -1;
            loadedBranches=true;
            saveButton.Enabled = original is not null || choices.Branches.Count > 0;
            if (!saveButton.Enabled)
                feedback.Text = "Create or restore an active branch before adding leads.";
            else
                await LoadCaptureOwnersAsync();
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (error is NpgsqlException or JsonException or ArgumentException or InvalidOperationException or IOException or UnauthorizedAccessException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text = "Could not load lead settings from local PostgreSQL.";
        }
    }

    private async void BranchChanged(object sender,EventArgs e)
    {
        if (loadedBranches)
            await LoadCaptureOwnersAsync();
    }

    private async Task LoadCaptureOwnersAsync()
    {
        if (original is not null || potential) return;
        var cancellation=lifetime.Token;
        int revision=++branchLoad;
        captureOwnerBox.DataSource=null;
        captureOwnerBox.Enabled=false;
        if ((branchBox.SelectedItem as CrmLookup)?.Id is not int branch) return;
        try
        {
            var people=await LeadStore.ReadLeadCaptureOwnersAsync(branch,cancellation);
            if (cancellation.IsCancellationRequested || revision!=branchLoad) return;
            var list=new List<OwnerOption>{new(null,"Use configured routing")};
            list.AddRange(people.Select(person=>new OwnerOption(person.Id,person.Name)));
            captureOwnerBox.DataSource=list;
            captureOwnerBox.Enabled=people.Count>0;
        }
        catch(OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch(Exception error) when (error is NpgsqlException or UnauthorizedAccessException or InvalidOperationException or IOException)
        {
            if (!cancellation.IsCancellationRequested && revision==branchLoad)
                feedback.Text="Lead owners are unavailable. Capture can still use configured routing.";
        }
    }

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (saving || !saveButton.Enabled)
            return;
        saving = true;
        saveButton.Enabled = cancelButton.Enabled = false;
        feedback.Text = "Saving lead…";
        try
        {
            int? branch = (branchBox.SelectedItem as CrmLookup)?.Id;
            if (original is null && branch is null)
                throw new ArgumentException("Choose a branch.");
            await LeadStore.SaveAsync(original is null ? null : LeadStore.Key(original, potential),
                fields.ToDictionary(field => field.Key, field => field.Value.Text), branch, lifetime.Token, potential, (captureOwnerBox.SelectedItem as OwnerOption)?.Id);
            saving = false;
            DialogResult = DialogResult.OK;
            Close();
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException)
        {
            feedback.Text = error.Message;
        }
        catch (Exception error) when (error is NpgsqlException or JsonException or IOException or UnauthorizedAccessException)
        {
            feedback.Text = "Could not save the lead. Refresh the directory and check local PostgreSQL.";
        }
        finally
        {
            saving = false;
            if (!IsDisposed)
                saveButton.Enabled = cancelButton.Enabled = true;
        }
    }

    private void EditorClosing(object sender, FormClosingEventArgs e) => e.Cancel = saving;
    private void EditorClosed(object sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
