using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsProjectBulkForm : Form
{
    private static readonly string[] Statuses=["Draft","Planned","Active","On Hold","Completed","Cancelled"];
    private static readonly string[] Priorities=["Low","Medium","High","Critical"];
    private readonly PmsProjectRepository? repository;
    private readonly PmsProjectScope scope;
    private readonly int workspaceId;
    private PmsBulkProject[]? plan;
    private PmsBulkPatch? patch;
    private bool saving;
    internal bool Changed { get; private set; }

    public PmsProjectBulkForm()=>InitializeComponent();

    internal PmsProjectBulkForm(PmsProjectRepository repository,PmsProjectScope scope,DataTable candidates,int workspaceId):this()
    {
        this.repository=repository;
        this.scope=scope;
        this.workspaceId=workspaceId;
        projects.DataSource=candidates;
        foreach(var item in action.Items.Cast<RadListDataItem>().ToArray())
            if(item.Value is not PmsBulkField field || !candidates.Rows.Cast<DataRow>().Any(row=>CanApply(row,scope,field)))
                action.Items.Remove(item);
        bool canChange=action.Items.Count>0;
        action.Visible=apply.Visible=back.Visible=canChange;
        action.SelectedIndex=canChange ? 0 : -1;
        ActionChanged(this,EventArgs.Empty);
        if(!canChange)
            hint.Text="Use Ctrl or Shift to select projects, then choose Export selected.";
        export.Visible=repository.CanExport && scope!=PmsProjectScope.Trash;
    }

    private DataRow[] SelectedProjects()=>projects.SelectedRows.OfType<GridViewDataRowInfo>()
        .Select(row=>row.DataBoundItem).OfType<DataRowView>().Select(view=>view.Row).ToArray();

    private async void ExportClicked(object? sender,EventArgs e)
    {
        if(repository is null || saving) return;
        int[] selected=SelectedProjects().Select(row=>row.Field<int>("id")).ToArray();
        if(selected.Length==0)
        {
            feedback.Text="Select at least one project to export.";
            return;
        }
        saving=true;
        export.Enabled=apply.Enabled=close.Enabled=false;
        try
        {
            var scoped=await repository.ReadSelectedExportAsync(workspaceId,scope,selected,CancellationToken.None);
            if(scoped.Count==0)
                feedback.Text="The selected projects are no longer available. Refresh Projects.";
            else if(exportDialog.ShowDialog(this)==DialogResult.OK)
            {
                PmsGridExport.WriteSelectedProjects(scoped,exportDialog.FileName);
                feedback.Text=$"{scoped.Count} of {selected.Length} selected projects exported.";
            }
        }
        catch(UnauthorizedAccessException error) { feedback.Text=error.Message; }
        catch(IOException) { feedback.Text="The CSV could not be saved. Choose an available file."; }
        catch(Npgsql.NpgsqlException) { feedback.Text="Could not read selected projects. Check the PostgreSQL connection."; }
        finally
        {
            saving=false;
            export.Enabled=apply.Enabled=close.Enabled=true;
        }
    }

    private void ActionChanged(object? sender,EventArgs e)
    {
        var field=action.SelectedItem?.Value as PmsBulkField?;
        value.Visible=field is PmsBulkField.Status or PmsBulkField.Priority;
        deadline.Visible=field==PmsBulkField.Deadline;
        value.DataSource=field==PmsBulkField.Status ? Statuses : field==PmsBulkField.Priority ? Priorities : null;
        value.SelectedIndex=-1;
    }

    private async void ReviewOrApply(object? sender,EventArgs e)
    {
        if(repository is null || saving) return;
        if(plan is null || patch is null)
        {
            var selected=SelectedProjects();
            if(selected.Length==0 || action.SelectedItem?.Value is not PmsBulkField field ||
                (field is PmsBulkField.Status or PmsBulkField.Priority && value.SelectedIndex<0))
            {
                feedback.Text="Select projects and choose a change first.";
                return;
            }
            patch=new(field,value.SelectedItem?.Text,field==PmsBulkField.Deadline ? deadline.Value.Date : null);
            plan=selected.Select(row=>new PmsBulkProject(row.Field<int>("id"),row.Field<string>("name")!,
                row.Field<string>("revision")!)).ToArray();
            string after=field switch
            {
                PmsBulkField.Archive=>"Archived",
                PmsBulkField.RestoreArchive=>"Active",
                PmsBulkField.Trash=>"Trash",
                PmsBulkField.RestoreTrash=>"Restored from Trash",
                _=>patch.Deadline?.ToString("d") ?? patch.Value!
            };
            string rows=string.Join(Environment.NewLine,selected.Select(row=>
                $"{row.Field<string>("name")} · {Previous(row,field)} → {after}"+
                (CanApply(row,scope,field) ? "" : " · permission required")));
            preview.Text=field is PmsBulkField.Archive or PmsBulkField.Trash
                ? "Related tasks and files are kept."+Environment.NewLine+Environment.NewLine+rows : rows;
            preview.Visible=true;
            projects.Visible=false;
            action.Enabled=value.Enabled=deadline.Enabled=false;
            back.Enabled=true;
            export.Enabled=false;
            apply.Text="Apply changes";
            feedback.Text=$"Review {plan.Length} selected projects.";
            return;
        }
        saving=true;
        apply.Enabled=back.Enabled=close.Enabled=false;
        try
        {
            var result=await repository.BulkUpdateAsync(plan,patch,scope,CancellationToken.None);
            Changed=result.Saved>0;
            preview.Text=result.Failures.Count==0 ? "All selected projects were updated." :
                string.Join(Environment.NewLine,result.Failures);
            feedback.Text=$"{result.Saved} updated · {result.Failures.Count} skipped";
        }
        catch(Exception error) when(error is InvalidOperationException or UnauthorizedAccessException or Npgsql.NpgsqlException)
        {
            preview.Text="The update could not finish. Refresh Projects to check the current records before retrying.";
            Changed=true;
        }
        finally
        {
            saving=false;
            close.Enabled=true;
        }
    }

    private static string Previous(DataRow row,PmsBulkField field)=>field switch
    {
        PmsBulkField.Status=>row.Field<string>("status") ?? "Unset",
        PmsBulkField.Priority=>row.Field<string>("priority") ?? "Unset",
        PmsBulkField.Deadline=>row.Field<DateTime?>("due_date")?.ToString("d") ?? "Unset",
        PmsBulkField.RestoreTrash=>"Trash",
        PmsBulkField.RestoreArchive=>"Archived",
        _=>row.Field<string>("status") ?? "Unset"
    };

    internal static bool CanApplyAny(DataRow row,PmsProjectScope scope)=>
        scope==PmsProjectScope.Trash ? CanApply(row,scope,PmsBulkField.RestoreTrash) : CanApply(row,scope,PmsBulkField.Status);

    private static bool CanApply(DataRow row,PmsProjectScope scope,PmsBulkField field)=>field switch
    {
        PmsBulkField.Archive=>scope==PmsProjectScope.Active && row.Field<bool>("can_edit") && row.Field<bool>("can_archive"),
        PmsBulkField.RestoreArchive=>scope==PmsProjectScope.Archived && row.Field<bool>("can_edit") && row.Field<bool>("can_archive"),
        PmsBulkField.Trash=>scope!=PmsProjectScope.Trash && row.Field<bool>("can_edit") && row.Field<bool>("can_trash"),
        PmsBulkField.RestoreTrash=>scope==PmsProjectScope.Trash && row.Field<bool>("can_restore"),
        _=>scope!=PmsProjectScope.Trash && row.Field<bool>("can_edit")
    };

    private void BackClicked(object? sender,EventArgs e)
    {
        plan=null;
        patch=null;
        preview.Visible=false;
        projects.Visible=true;
        action.Enabled=value.Enabled=deadline.Enabled=true;
        back.Enabled=false;
        export.Enabled=true;
        apply.Text="Review changes";
        feedback.Text="";
    }

    private void CloseClicked(object? sender,EventArgs e)=>Close();

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if(saving) e.Cancel=true;
    }
}
