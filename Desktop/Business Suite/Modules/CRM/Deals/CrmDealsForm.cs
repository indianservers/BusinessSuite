using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealsForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private bool ready;
    private bool busy;
    private bool canArchive;
    private bool canCapture;
    private int page;
    private long total;
    private CrmDealFilters dealFilters=new();

    public CrmDealsForm()
    {
        InitializeComponent();
        statusBox.SelectedIndex=0;
    }

    internal CrmDealsForm(DesktopDatabaseSettings settings) : this() => repository=new(settings);

    private async void FormShown(object sender,EventArgs e)
    {
        ready=true;
        await LoadAsync(0);
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
        dealExportDialog.Dispose();
    }

    private async void RefreshClicked(object sender,EventArgs e) => await LoadAsync(page);
    private async void FiltersChanged(object sender,EventArgs e) => await LoadAsync(0);
    private async void PreviousClicked(object sender,EventArgs e) => await LoadAsync(page-1);
    private async void NextClicked(object sender,EventArgs e) => await LoadAsync(page+1);
    private void SelectionChanged(object sender,EventArgs e) => UpdateActions();

    private void PipelineRulesClicked(object sender,EventArgs e)
    {
        if (busy || repository is null)
            return;
        using var form=new CrmStagePolicyForm(repository);
        form.ShowDialog(this);
    }

    private void PipelineStructureClicked(object sender,EventArgs e)
    {
        if (busy || repository is null)
            return;
        using var form=new CrmPipelineStructureForm(repository);
        form.ShowDialog(this);
    }

    private async void ForecastClicked(object sender,EventArgs e)
    {
        if (busy || repository is null)
            return;
        string status=statusBox.SelectedIndex>0?statusBox.Text:"";
        using var form=new CrmDealForecastForm(repository,searchBox.Text.Trim(),status,archiveBox.Checked,dealFilters);
        if (form.ShowDialog(this)!=DialogResult.OK || form.DrillFilters is not CrmDealFilters drill)
            return;
        dealFilters=drill;
        advancedFiltersButton.Text="Deal filters •";
        if (statusBox.SelectedIndex==1)
            await LoadAsync(0);
        else
            statusBox.SelectedIndex=1;
    }

    private async void ExportFilteredClicked(object sender,EventArgs e) => await ExportAsync(false);
    private async void SalesOutcomesClicked(object sender,EventArgs e)
    {
        if (busy || repository is null || archiveBox.Checked)
            return;
        string status=statusBox.SelectedIndex>0?statusBox.Text:"";
        using var form=new CrmDealOutcomesForm(repository,searchBox.Text.Trim(),status,dealFilters);
        if (form.ShowDialog(this)!=DialogResult.OK || form.DrillFilters is not CrmDealFilters drill)
            return;
        dealFilters=drill;
        advancedFiltersButton.Text="Deal filters •";
        if (form.DrillLost && statusBox.SelectedIndex!=3)
            statusBox.SelectedIndex=3;
        else
            await LoadAsync(0);
    }
    private async void ExportSelectedClicked(object sender,EventArgs e) => await ExportAsync(true);

    private async Task ExportAsync(bool selection)
    {
        if (busy || repository is null)
            return;
        int[] ids=selection?dealGrid.SelectedRows.Select(row=>row.DataBoundItem).OfType<DataRowView>()
            .Select(row=>(int)row["id"]).Distinct().ToArray():[];
        if (selection && ids.Length==0)
            return;
        dealExportDialog.FileName=archiveBox.Checked?"archived-deals.csv":"deals.csv";
        if (dealExportDialog.ShowDialog(this)!=DialogResult.OK)
            return;
        string destination=dealExportDialog.FileName;
        string temporary=Path.Combine(Path.GetDirectoryName(destination),Guid.NewGuid().ToString("N")+".tmp");
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions();
        feedback.Text="Preparing the Deal export…";
        try
        {
            string status=!selection && statusBox.SelectedIndex>0?statusBox.Text:"";
            string search=selection?"":searchBox.Text.Trim();
            var records=await repository.ExportRowsAsync(search,status,archiveBox.Checked,selection?new():dealFilters,ids,cancellation);
            if (records.Rows.Count==0)
            {
                feedback.Text="No deals matched the export.";
                return;
            }
            try
            {
                await Task.Run(() =>
                {
                    using (var output=new FileStream(temporary,FileMode.CreateNew,FileAccess.Write,FileShare.None))
                        CrmDealRepository.WriteCsv(output,records,cancellation);
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
                feedback.Text=$"Exported {records.Rows.Count:N0} deals to {Path.GetFileName(destination)}.";
        }
        catch(OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch(Exception error) when (IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is UnauthorizedAccessException or ArgumentException or InvalidOperationException
                    ?error.Message:"Could not export deals. Check PostgreSQL and access to the destination.";
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested) UpdateActions();
        }
    }

    private async void AdvancedFiltersClicked(object sender,EventArgs e)
    {
        if (busy || repository is null)
            return;
        using var dialog=new CrmDealFilterForm(repository,dealFilters,archiveBox.Checked);
        if (dialog.ShowDialog(this)!=DialogResult.OK)
            return;
        dealFilters=dialog.Filters;
        advancedFiltersButton.Text=dealFilters==new CrmDealFilters()?"Deal filters":"Deal filters •";
        await LoadAsync(0);
    }

    private async void DetailsClicked(object sender,EventArgs e)
    {
        if (busy||repository is null||Selected is not DataRowView row)
            return;
        CancellationToken cancellation=lifetime.Token;
        bool edited=false;
        int? order=null;
        busy=true;
        UpdateActions();
        try
        {
            var details=await repository.DetailAsync((int)row["id"],archiveBox.Checked,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            using var form=new CrmDealDetailForm(details,repository);
            edited=form.ShowDialog(this)==DialogResult.OK || form.RelatedChanged;
            order=form.HandoffOrderId;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=Friendly(error);
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
        if (edited && !cancellation.IsCancellationRequested)
        {
            await LoadAsync(page);
            if (order.HasValue && !cancellation.IsCancellationRequested)
                feedback.Text=$"Deal closed Won. Draft Sales order #{order.Value} created.";
        }
    }

    private async void CaptureClicked(object sender,EventArgs e)
    {
        if (repository is null || !newDealButton.Enabled)
            return;
        using var form=new CrmDealCaptureForm(repository);
        if (form.ShowDialog(this)!=DialogResult.OK)
            return;
        await LoadAsync(0);
        if (!IsDisposed)
            feedback.Text=$"Deal #{form.CreatedId} created.";
    }

    private async void ArchiveClicked(object sender,EventArgs e)
    {
        if (repository is null || !archiveButton.Enabled || Selected is not DataRowView selected)
            return;
        bool archive=!archiveBox.Checked;
        string action=archive?"Archive":"Restore";
        if (MessageBox.Show(this,$"{action} {selected["name"]}?","Business Suite",
            MessageBoxButtons.YesNo,MessageBoxIcon.Question,MessageBoxDefaultButton.Button2)!=DialogResult.Yes)
            return;
        CancellationToken cancellation=lifetime.Token;
        busy=true;
        bool changed=false;
        UpdateActions();
        try
        {
            await repository.ChangeArchiveAsync((int)selected["id"],(string)selected["revision"],archive,cancellation);
            changed=true;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch(Exception error) when (IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested) feedback.Text=Friendly(error);
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested) UpdateActions();
        }
        if (changed && !cancellation.IsCancellationRequested)
            await LoadAsync(page);
    }

    private async Task LoadAsync(int requestedPage)
    {
        if (busy||!ready||repository is null||requestedPage<0)
            return;
        CancellationToken cancellation=lifetime.Token;
        busy=true;
        UpdateActions();
        feedback.Text="Loading deals…";
        try
        {
            string status=statusBox.SelectedIndex>0?statusBox.Text:"";
            string search=searchBox.Text.Trim();
            bool archived=archiveBox.Checked;
            var result=await repository.ListAsync(search,status,archived,requestedPage,cancellation,dealFilters);
            if (requestedPage>0&&result.Rows.Rows.Count==0)
            {
                requestedPage=0;
                result=await repository.ListAsync(search,status,archived,requestedPage,cancellation,dealFilters);
            }
            if (cancellation.IsCancellationRequested)
                return;
            dealGrid.DataSource=result.Rows;
            page=requestedPage;
            total=result.Total;
            canArchive=result.CanArchive;
            canCapture=result.CanCapture;
            int first=page*CrmDealRepository.PageSize;
            feedback.Text=total==0?"No matching deals.":$"Showing {first+1:N0}–{first+result.Rows.Rows.Count:N0} of {total:N0} deals.";
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                dealGrid.DataSource=null;
                page=0;
                total=0;
                canArchive=canCapture=false;
                feedback.Text=Friendly(error);
            }
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    private DataRowView? Selected => dealGrid.CurrentRow?.DataBoundItem as DataRowView;

    private void UpdateActions()
    {
        searchBox.Enabled=applyButton.Enabled=statusBox.Enabled=archiveBox.Enabled=refreshButton.Enabled=!busy;
        advancedFiltersButton.Enabled=!busy;
        forecastButton.Enabled=!busy;
        salesOutcomesButton.Enabled=!busy&&!archiveBox.Checked;
        pipelineRulesButton.Enabled=!busy;
        pipelineStructureButton.Enabled=!busy;
        exportFilteredButton.Enabled=!busy&&total>0;
        exportSelectedButton.Enabled=exportFilteredButton.Enabled&&dealGrid.SelectedRows.Count>0;
        detailsButton.Enabled=!busy&&Selected is not null;
        newDealButton.Enabled=!busy&&canCapture&&!archiveBox.Checked;
        archiveButton.Enabled=detailsButton.Enabled&&canArchive;
        archiveButton.Text=archiveBox.Checked?"Restore deal":"Archive deal";
        previousButton.Enabled=!busy&&page>0;
        nextButton.Enabled=!busy&&(long)(page+1)*CrmDealRepository.PageSize<total;
    }

    private static bool IsExpected(Exception error) => error is NpgsqlException or TimeoutException or IOException
        or ArgumentException or InvalidOperationException or UnauthorizedAccessException;

    private static string Friendly(Exception error) => error is UnauthorizedAccessException or InvalidOperationException or ArgumentException
        ? error.Message : "Could not load the deal. Check PostgreSQL and try again.";
}
