using Telerik.WinControls.UI;

namespace Business_Suite;

partial class PmsProjectBulkForm
{
    private void InitializeComponent()
    {
        this.hint=new Label();
        this.action=new RadDropDownList();
        this.value=new RadDropDownList();
        this.deadline=new RadDateTimePicker();
        this.projects=new RadGridView();
        this.preview=new RadTextBox();
        this.feedback=new Label();
        this.apply=new RadButton();
        this.back=new RadButton();
        this.close=new RadButton();
        this.export=new RadButton();
        this.exportDialog=new SaveFileDialog();
        this.keyColumn=new GridViewTextBoxColumn();
        this.nameColumn=new GridViewTextBoxColumn();
        this.statusColumn=new GridViewTextBoxColumn();
        this.priorityColumn=new GridViewTextBoxColumn();
        this.deadlineColumn=new GridViewDateTimeColumn();
        ((System.ComponentModel.ISupportInitialize)this.projects).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.projects.MasterTemplate).BeginInit();
        this.SuspendLayout();
        this.hint.Name="hint";
        this.hint.Location=new Point(14,12);
        this.hint.Size=new Size(705,25);
        this.hint.Text="Use Ctrl or Shift to select projects, then choose the change to review.";
        this.action.Name="action";
        this.action.Location=new Point(14,44);
        this.action.Size=new Size(169,28);
        this.action.AccessibleName="Project field to change";
        this.action.DropDownStyle=Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.action.Items.AddRange(new RadListDataItem[]{
            new RadListDataItem("Status"){Value=PmsBulkField.Status},
            new RadListDataItem("Priority"){Value=PmsBulkField.Priority},
            new RadListDataItem("Deadline"){Value=PmsBulkField.Deadline},
            new RadListDataItem("Archive"){Value=PmsBulkField.Archive},
            new RadListDataItem("Restore archived projects"){Value=PmsBulkField.RestoreArchive},
            new RadListDataItem("Move to Trash"){Value=PmsBulkField.Trash},
            new RadListDataItem("Restore from Trash"){Value=PmsBulkField.RestoreTrash}});
        this.action.SelectedIndexChanged+=this.ActionChanged;
        this.value.Name="value";
        this.value.Location=new Point(194,44);
        this.value.Size=new Size(242,28);
        this.value.AccessibleName="New status or priority";
        this.value.DropDownStyle=Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.deadline.Name="deadline";
        this.deadline.Location=new Point(194,44);
        this.deadline.Size=new Size(242,28);
        this.deadline.AccessibleName="New deadline";
        this.deadline.Format=DateTimePickerFormat.Short;
        this.deadline.Visible=false;
        this.projects.Name="projects";
        this.projects.Location=new Point(14,85);
        this.projects.Size=new Size(705,325);
        this.projects.AutoGenerateColumns=false;
        this.projects.MultiSelect=true;
        this.projects.ReadOnly=true;
        this.projects.SelectionMode=GridViewSelectionMode.FullRowSelect;
        this.projects.AllowAddNewRow=false;
        this.projects.AllowDeleteRow=false;
        this.keyColumn.Name="keyColumn";
        this.keyColumn.FieldName="project_key";
        this.keyColumn.HeaderText="Key";
        this.keyColumn.Width=102;
        this.nameColumn.Name="nameColumn";
        this.nameColumn.FieldName="name";
        this.nameColumn.HeaderText="Project";
        this.nameColumn.Width=240;
        this.statusColumn.Name="statusColumn";
        this.statusColumn.FieldName="status";
        this.statusColumn.HeaderText="Status";
        this.statusColumn.Width=115;
        this.priorityColumn.Name="priorityColumn";
        this.priorityColumn.FieldName="priority";
        this.priorityColumn.HeaderText="Priority";
        this.priorityColumn.Width=100;
        this.deadlineColumn.Name="deadlineColumn";
        this.deadlineColumn.FieldName="due_date";
        this.deadlineColumn.HeaderText="Deadline";
        this.deadlineColumn.Width=115;
        this.deadlineColumn.FormatString="{0:d}";
        this.projects.Columns.AddRange(new GridViewDataColumn[]{this.keyColumn,this.nameColumn,this.statusColumn,this.priorityColumn,this.deadlineColumn});
        this.preview.Name="preview";
        this.preview.Location=new Point(14,85);
        this.preview.Size=new Size(705,325);
        this.preview.AutoSize=false;
        this.preview.Multiline=true;
        this.preview.ReadOnly=true;
        this.preview.ScrollBars=ScrollBars.Vertical;
        this.preview.Visible=false;
        this.preview.AccessibleName="Review changes and results";
        this.feedback.Name="feedback";
        this.feedback.Location=new Point(14,417);
        this.feedback.Size=new Size(705,25);
        this.apply.Name="apply";
        this.apply.Location=new Point(408,448);
        this.apply.Size=new Size(132,30);
        this.apply.Text="Review changes";
        this.apply.Click+=this.ReviewOrApply;
        this.back.Name="back";
        this.back.Location=new Point(549,448);
        this.back.Size=new Size(80,30);
        this.back.Text="Back";
        this.back.Enabled=false;
        this.back.Click+=this.BackClicked;
        this.close.Name="close";
        this.close.Location=new Point(639,448);
        this.close.Size=new Size(80,30);
        this.close.Text="Close";
        this.close.Click+=this.CloseClicked;
        this.export.Name="export";
        this.export.Location=new Point(14,448);
        this.export.Size=new Size(140,30);
        this.export.Text="Export selected";
        this.export.Click+=this.ExportClicked;
        this.exportDialog.DefaultExt="csv";
        this.exportDialog.Filter="CSV files (*.csv)|*.csv";
        this.exportDialog.FileName="projects.csv";
        this.ClientSize=new Size(733,492);
        this.Controls.AddRange(new Control[]{this.hint,this.action,this.value,this.deadline,this.projects,this.preview,this.feedback,this.apply,this.back,this.close,this.export});
        this.StartPosition=FormStartPosition.CenterParent;
        this.Text="Bulk project changes";
        ((System.ComponentModel.ISupportInitialize)this.projects.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.projects).EndInit();
        this.ResumeLayout(false);
    }
    private Label hint=null!,feedback=null!;
    private RadDropDownList action=null!,value=null!;
    private RadDateTimePicker deadline=null!;
    private RadGridView projects=null!;
    private RadTextBox preview=null!;
    private RadButton apply=null!,back=null!,close=null!;
    private RadButton export=null!;
    private SaveFileDialog exportDialog=null!;
    private GridViewTextBoxColumn keyColumn=null!,nameColumn=null!,statusColumn=null!,priorityColumn=null!;
    private GridViewDateTimeColumn deadlineColumn=null!;
}
