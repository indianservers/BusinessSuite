using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class LeadsForm : Form
{
    private readonly CancellationTokenSource lifetime = new();
    private readonly bool potential;
    private bool ready;
    private bool busy;
    private bool snapshot;
    private bool loadedArchived;
    private int page;
    private long total;

    public LeadsForm() : this(false) { }

    internal LeadsForm(bool potential)
    {
        this.potential = potential;
        InitializeComponent();
        if (potential)
        {
            heading.Text = "Potential Clients";
            Text = "Business Suite | Potential Clients";
            newButton.Text = "New client";
            convertButton.Text = "Make lead";
            nurtureConsentButton.Visible=false;
            meetingMetricsButton.Visible=false;
            meetingOutcomesButton.Visible=false;
            leadTasksButton.Visible=false;
        }
        ratingBox.Items.Add("All ratings");
        ratingBox.Items.AddRange(LeadStore.Ratings);
        ratingBox.SelectedIndex = 0;
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private async void LeadsShown(object sender, EventArgs e)
    {
        try
        {
            LeadPolicy policy = await LeadStore.PolicyAsync(lifetime.Token);
            var owners = await LeadStore.OwnersAsync(lifetime.Token);
            if (IsDisposed)
                return;
            stageBox.Items.Add("All stages");
            stageBox.Items.AddRange(policy.Stages.Select(stage => stage.Name).ToArray());
            stageBox.SelectedIndex = 0;
            ownerBox.DisplayMember = nameof(CrmLookup.Name);
            ownerBox.DataSource = owners;
            ready = true;
            await LoadAsync(0);
        }
        catch (OperationCanceledException) { }
        catch (Exception error) when (Expected(error))
        {
            if (!IsDisposed)
                statusLabel.Text = "Could not load lead settings. Check local PostgreSQL.";
        }
    }

    private void LeadsClosed(object sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
        exportDialog.Dispose();
    }

    private async void FilterChanged(object sender, EventArgs e) => await LoadAsync(0);
    private async void RefreshClicked(object sender, EventArgs e) => await LoadAsync(page);
    private async void PreviousClicked(object sender, EventArgs e) => await LoadAsync(page - 1);
    private async void NextClicked(object sender, EventArgs e) => await LoadAsync(page + 1);

    private async void ExportFilteredClicked(object sender,EventArgs e) => await ExportAsync(false);
    private async void ExportSelectedClicked(object sender,EventArgs e) => await ExportAsync(true);

    private async Task ExportAsync(bool selection)
    {
        if (busy || !snapshot)
            return;
        int[] ids=selection ? grid.SelectedRows.Select(row=>row.DataBoundItem).OfType<DataRowView>()
            .Select(row=>(int)row["id"]).Distinct().ToArray() : [];
        if (selection && ids.Length==0)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions();
        statusLabel.Text="Preparing the Excel workbook…";
        try
        {
            string search=selection?"":searchBox.Text.Trim();
            string stage=selection || stageBox.SelectedIndex<=0?"":stageBox.Text;
            string source=selection?"":sourceBox.Text.Trim();
            string rating=selection || ratingBox.SelectedIndex<=0?"":ratingBox.Text;
            int? owner=selection?null:(ownerBox.SelectedItem as CrmLookup)?.Id;
            var rows=await LeadStore.ExportRowsAsync(search,stage,source,rating,owner,potential,ids,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            if (rows.Rows.Count==0)
            {
                statusLabel.Text="No records match the export.";
                return;
            }
            exportDialog.FileName=potential?"potential-clients.xlsx":"leads.xlsx";
            if (exportDialog.ShowDialog(this)!=DialogResult.OK)
            {
                statusLabel.Text="Export canceled.";
                return;
            }
            string destination=exportDialog.FileName;
            string temporary=Path.Combine(Path.GetDirectoryName(destination),Guid.NewGuid().ToString("N")+".tmp");
            try
            {
                await Task.Run(() =>
                {
                    using (var output=new FileStream(temporary,FileMode.CreateNew,FileAccess.Write,FileShare.None))
                        LeadWorkbook.Write(output,rows,cancellation);
                    cancellation.ThrowIfCancellationRequested();
                    if (File.Exists(destination))
                        File.Replace(temporary,destination,null);
                    else
                        File.Move(temporary,destination);
                },cancellation);
            }
            finally
            {
                if (File.Exists(temporary))
                    File.Delete(temporary);
            }
            if (!cancellation.IsCancellationRequested)
                statusLabel.Text=$"Exported {rows.Rows.Count:N0} records to {Path.GetFileName(destination)}.";
        }
        catch(OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch(Exception error) when (Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                statusLabel.Text=error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not save the lead export. Check PostgreSQL and access to the destination.";
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }
    private void SelectionChanged(object sender, EventArgs e) => UpdateActions();

    private void LeadHistoryClicked(object sender,EventArgs e)
    {
        if (!leadHistoryButton.Enabled || Selected is not DataRow row)
            return;
        using var dialog=new LeadHistoryForm((int)row["id"],potential,LeadStore.Text(row,"full_name"));
        dialog.ShowDialog(this);
    }

    private void MeetingMetricsClicked(object sender,EventArgs e)
    {
        if (!meetingMetricsButton.Enabled)
            return;
        using var dialog=new LeadMeetingMetricsForm(searchBox.Text.Trim(),stageBox.SelectedIndex<=0?"":stageBox.Text,
            (ownerBox.SelectedItem as CrmLookup)?.Id);
        dialog.ShowDialog(this);
    }

    private async void MeetingOutcomesClicked(object sender,EventArgs e)
    {
        if (!meetingOutcomesButton.Enabled || Selected is not DataRow row)
            return;
        using var dialog=new LeadMeetingOutcomesForm(LeadStore.Key(row,false),LeadStore.Text(row,"full_name"));
        if (dialog.ShowDialog(this)==DialogResult.OK)
        {
            await LoadAsync(page);
            if (snapshot)
                statusLabel.Text=dialog.SuccessMessage;
        }
    }

    private async void LeadTasksClicked(object sender,EventArgs e)
    {
        if (!leadTasksButton.Enabled || Selected is not DataRow row)
            return;
        using var dialog=new LeadTasksForm(LeadStore.Key(row,false),LeadStore.Text(row,"full_name"));
        if (dialog.ShowDialog(this)==DialogResult.OK)
        {
            await LoadAsync(page);
            if (snapshot)
                statusLabel.Text=dialog.SuccessMessage;
        }
    }

    private async void NurtureConsentClicked(object sender,EventArgs e)
    {
        if (!nurtureConsentButton.Enabled || Selected is not DataRow row)
            return;
        using var dialog=new LeadNurtureConsentForm(LeadStore.Key(row,false),LeadStore.Text(row,"full_name"),
            LeadStore.ReadNurtureConsent(row));
        if (dialog.ShowDialog(this)==DialogResult.OK)
            await LoadAsync(page);
    }

    private async void NewClicked(object sender, EventArgs e) => await OpenEditorAsync(null);

    private async void EditClicked(object sender, EventArgs e)
    {
        if (Selected is DataRow row)
            await OpenEditorAsync(row);
    }

    private async Task OpenEditorAsync(DataRow? row)
    {
        if (busy || !snapshot || loadedArchived)
            return;
        using var form = new LeadEditForm(row, potential);
        if (form.ShowDialog(this) == DialogResult.OK)
            await LoadAsync(page);
    }

    private async void ConvertClicked(object sender, EventArgs e)
    {
        if (!convertButton.Enabled || Selected is not DataRow row)
            return;
        if (potential)
        {
            await PromoteAsync(row);
            return;
        }
        using var form = new LeadConversionForm(row);
        if (form.ShowDialog(this) != DialogResult.OK || form.Result is not LeadConversionResult result)
            return;
        await LoadAsync(page);
        string deal = result.Deal.HasValue ? $", deal #{result.Deal}" : "";
        statusLabel.Text = $"Lead converted to company #{result.Company}, contact #{result.Contact}{deal}.";
    }

    private async Task PromoteAsync(DataRow row)
    {
        CancellationToken cancellation = lifetime.Token;
        busy = true;
        UpdateActions();
        try
        {
            await LeadStore.PromotePotentialAsync(LeadStore.Key(row, potential), cancellation);
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { return; }
        catch (Exception error) when (Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException ? error.Message : "Could not move this client to Leads.";
            return;
        }
        finally
        {
            busy = false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }

        if (!cancellation.IsCancellationRequested)
        {
            await LoadAsync(page);
            if (snapshot)
                statusLabel.Text = "Potential client moved to Leads.";
        }
    }

    private async void ArchiveClicked(object sender, EventArgs e) => await ChangeArchiveAsync(true);
    private async void RestoreClicked(object sender, EventArgs e) => await ChangeArchiveAsync(false);

    private async Task ChangeArchiveAsync(bool archive)
    {
        if (busy || !snapshot || loadedArchived == archive || Selected is not DataRow row)
            return;
        string name = LeadStore.Text(row, "full_name");
        string? reason = null;
        if (archive)
        {
            using var form = new LeadArchiveForm(name);
            if (form.ShowDialog(this) != DialogResult.OK)
                return;
            reason = form.Reason;
        }
        else if (MessageBox.Show(this, $"Restore {name}?", "Business Suite", MessageBoxButtons.YesNo,
                     MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) != DialogResult.Yes)
            return;

        CancellationToken cancellation = lifetime.Token;
        busy = true;
        UpdateActions();
        try
        {
            await LeadStore.SetArchivedAsync(LeadStore.Key(row, potential), archive, cancellation, reason);
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { return; }
        catch (Exception error) when (Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException ? error.Message : "Could not update this lead.";
            return;
        }
        finally
        {
            busy = false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
        if (!cancellation.IsCancellationRequested)
            await LoadAsync(page);
    }

    private async Task LoadAsync(int requestedPage)
    {
        if (busy || !ready || requestedPage < 0)
            return;
        CancellationToken cancellation = lifetime.Token;
        busy = true;
        snapshot = false;
        UpdateActions();
        statusLabel.Text = "Reading leads from local PostgreSQL…";
        try
        {
            string stage = stageBox.SelectedIndex > 0 ? stageBox.Text : "";
            string rating = ratingBox.SelectedIndex > 0 ? ratingBox.Text : "";
            string search = searchBox.Text.Trim();
            string source = sourceBox.Text.Trim();
            int? owner = (ownerBox.SelectedItem as CrmLookup)?.Id;
            bool archived = archivedBox.Checked;
            LeadPage result = await LeadStore.ListAsync(search,stage,source,rating,archived,requestedPage,cancellation,owner,potential);
            if (result.Records.Rows.Count == 0 && requestedPage > 0)
            {
                requestedPage = 0;
                result = await LeadStore.ListAsync(search,stage,source,rating,archived,0,cancellation,owner,potential);
            }
            if (cancellation.IsCancellationRequested)
                return;
            grid.DataSource = result.Records;
            page = requestedPage;
            total = result.Total;
            loadedArchived = archived;
            snapshot = true;
            string recordLabel = potential ? "potential clients" : "leads";
            statusLabel.Text = total == 0 ? $"No matching {recordLabel}." :
                $"Showing {page * LeadStore.PageSize + 1:N0}–{page * LeadStore.PageSize + result.Records.Rows.Count:N0} of {total:N0} {recordLabel}";
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                statusLabel.Text = "Could not load leads. Check local PostgreSQL.";
        }
        finally
        {
            busy = false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void UpdateActions()
    {
        searchButton.Enabled = refreshButton.Enabled = stageBox.Enabled = ratingBox.Enabled =
            ownerBox.Enabled = archivedBox.Enabled = !busy;
        bool current = snapshot && !busy && loadedArchived == archivedBox.Checked;
        exportFilteredButton.Enabled=current;
        exportSelectedButton.Enabled=current && grid.SelectedRows.Count>0;
        DataRow? row = Selected;
        newButton.Enabled = current && !loadedArchived;
        editButton.Enabled = archiveButton.Enabled = current && !loadedArchived && row is not null;
        nurtureConsentButton.Enabled=!potential&&editButton.Enabled;
        meetingMetricsButton.Enabled=!potential&&current&&!loadedArchived;
        meetingOutcomesButton.Enabled=!potential&&editButton.Enabled;
        leadTasksButton.Enabled=!potential&&editButton.Enabled;
        leadHistoryButton.Enabled=editButton.Enabled;
        restoreButton.Enabled = current && loadedArchived && row is not null;
        convertButton.Enabled = editButton.Enabled && row is not null && row["is_converted"] is not true
            && (potential || LeadStore.Text(row, "status") == "Qualified");
        previousButton.Enabled = current && page > 0;
        nextButton.Enabled = current && (long)(page + 1) * LeadStore.PageSize < total;
    }

    private static bool Expected(Exception error) =>
        error is NpgsqlException or JsonException or ArgumentException or InvalidOperationException or IOException or UnauthorizedAccessException;
}
