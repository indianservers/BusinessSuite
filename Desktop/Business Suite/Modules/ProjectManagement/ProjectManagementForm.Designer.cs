#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class ProjectManagementForm
    {
        private void InitializeComponent()
        {
            this.toolbar = new Panel();
            this.searchTextBox = new RadTextBox();
            this.workspaceList = new RadDropDownList();
            this.scopeList = new RadDropDownList();
            this.projectGrid = new RadGridView();
            this.statusLabel = new Label();
            this.exportDialog = new SaveFileDialog();
            this.newButton = new RadButton();
            this.editButton = new RadButton();
            this.archiveButton = new RadButton();
            this.trashButton = new RadButton();
            this.refreshButton = new RadButton();
            this.exportButton = new RadButton();
            this.newTaskButton = new RadButton();
            this.cloneButton = new RadButton();
            this.bulkButton = new RadButton();
            this.milestonesButton = new RadButton();
            this.risksButton = new RadButton();
            this.scheduleButton = new RadButton();
            this.workHoursButton = new RadButton();
            this.keyColumn = new GridViewTextBoxColumn();
            this.titleColumn = new GridViewTextBoxColumn();
            this.workspaceColumn = new GridViewTextBoxColumn();
            this.statusColumn = new GridViewTextBoxColumn();
            this.priorityColumn = new GridViewTextBoxColumn();
            this.startColumn = new GridViewTextBoxColumn();
            this.dueColumn = new GridViewTextBoxColumn();
            this.tasksColumn = new GridViewTextBoxColumn();
            this.progressColumn = new GridViewTextBoxColumn();
            ((System.ComponentModel.ISupportInitialize)this.projectGrid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.projectGrid.MasterTemplate).BeginInit();
            this.toolbar.SuspendLayout();
            this.SuspendLayout();

            this.searchTextBox.Name = "searchTextBox";
            this.searchTextBox.Location = new Point(10, 12);
            this.searchTextBox.Size = new Size(145, 25);
            this.searchTextBox.NullText = "Search projects";
            this.searchTextBox.TextChanged += this.FilterChanged;

            this.workspaceList.Name = "workspaceList";
            this.workspaceList.Location = new Point(160, 12);
            this.workspaceList.Size = new Size(130, 25);
            this.workspaceList.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.workspaceList.SelectedIndexChanged += this.FilterChanged;

            this.scopeList.Name = "scopeList";
            this.scopeList.Location = new Point(295, 12);
            this.scopeList.Size = new Size(102, 25);
            this.scopeList.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.scopeList.Items.AddRange(new Telerik.WinControls.UI.RadListDataItem[] {
                new Telerik.WinControls.UI.RadListDataItem("Active"),
                new Telerik.WinControls.UI.RadListDataItem("Archived"),
                new Telerik.WinControls.UI.RadListDataItem("Trash") });
            this.scopeList.SelectedIndex = 0;
            this.scopeList.SelectedIndexChanged += this.FilterChanged;

            this.newButton.Name = "newButton";
            this.newButton.Text = "New project";
            this.newButton.Location = new Point(405, 10);
            this.newButton.Size = new Size(95, 28);
            this.newButton.Click += this.newButton_Click;

            this.editButton.Name = "editButton";
            this.editButton.Text = "Edit";
            this.editButton.Location = new Point(505, 10);
            this.editButton.Size = new Size(61, 28);
            this.editButton.Click += this.editButton_Click;

            this.archiveButton.Name = "archiveButton";
            this.archiveButton.Text = "Archive";
            this.archiveButton.Location = new Point(571, 10);
            this.archiveButton.Size = new Size(90, 28);
            this.archiveButton.Click += this.archiveButton_Click;

            this.trashButton.Name = "trashButton";
            this.trashButton.Text = "Move to Trash";
            this.trashButton.Location = new Point(666, 10);
            this.trashButton.Size = new Size(105, 28);
            this.trashButton.Click += this.trashButton_Click;

            this.refreshButton.Name = "refreshButton";
            this.refreshButton.Text = "Refresh";
            this.refreshButton.Location = new Point(776, 10);
            this.refreshButton.Size = new Size(75, 28);
            this.refreshButton.Click += this.refreshButton_Click;

            this.exportButton.Name = "exportButton";
            this.exportButton.Text = "Export CSV";
            this.exportButton.Location = new Point(856, 10);
            this.exportButton.Size = new Size(94, 28);
            this.exportButton.Click += this.exportButton_Click;

            this.newTaskButton.Name = "newTaskButton";
            this.newTaskButton.Text = "New task";
            this.newTaskButton.Location = new Point(955, 10);
            this.newTaskButton.Size = new Size(85, 28);
            this.newTaskButton.Click += this.NewTaskClicked;

            this.cloneButton.Name = "cloneButton";
            this.cloneButton.Text = "Duplicate";
            this.cloneButton.Location = new Point(1048, 10);
            this.cloneButton.Size = new Size(95, 28);
            this.cloneButton.Enabled = false;
            this.cloneButton.Click += this.CloneClicked;

            this.milestonesButton.Name = "milestonesButton";
            this.milestonesButton.Text = "Milestones";
            this.milestonesButton.Location = new Point(10, 44);
            this.milestonesButton.Size = new Size(102, 28);
            this.milestonesButton.Enabled = false;
            this.milestonesButton.Click += this.MilestonesClicked;

            this.risksButton.Name = "risksButton";
            this.risksButton.Text = "Risk register";
            this.risksButton.Location = new Point(120, 44);
            this.risksButton.Size = new Size(105, 28);
            this.risksButton.Enabled = false;
            this.risksButton.Click += this.RisksClicked;
            this.scheduleButton.Name = "scheduleButton";
            this.scheduleButton.Text = "Schedule";
            this.scheduleButton.Location = new Point(235, 44);
            this.scheduleButton.Size = new Size(106, 28);
            this.scheduleButton.Enabled = false;
            this.scheduleButton.Click += this.ScheduleClicked;
            this.workHoursButton.Name = "workHoursButton";
            this.workHoursButton.Text = "My working hours";
            this.workHoursButton.Location = new Point(351, 44);
            this.workHoursButton.Size = new Size(145, 28);
            this.workHoursButton.Enabled = false;
            this.workHoursButton.Click += this.WorkHoursClicked;
            this.bulkButton.Name = "bulkButton";
            this.bulkButton.Text = "Bulk changes";
            this.bulkButton.Location = new Point(506,44);
            this.bulkButton.Size = new Size(118,28);
            this.bulkButton.Enabled = false;
            this.bulkButton.Click += this.BulkClicked;

            this.toolbar.Name = "toolbar";
            this.toolbar.Height = 80;
            this.toolbar.Dock = DockStyle.Top;
            this.toolbar.Controls.AddRange(new Control[] {
                this.searchTextBox, this.workspaceList, this.scopeList,
                this.newButton, this.editButton, this.archiveButton, this.trashButton, this.refreshButton,
                this.exportButton, this.newTaskButton, this.cloneButton, this.milestonesButton, this.risksButton, this.scheduleButton, this.workHoursButton, this.bulkButton });

            this.keyColumn.Name = "keyColumn";
            this.keyColumn.FieldName = "project_key";
            this.keyColumn.HeaderText = "Key";
            this.keyColumn.Width = 105;
            this.titleColumn.Name = "titleColumn";
            this.titleColumn.FieldName = "name";
            this.titleColumn.HeaderText = "Project name";
            this.titleColumn.Width = 250;
            this.workspaceColumn.Name = "workspaceColumn";
            this.workspaceColumn.FieldName = "workspace";
            this.workspaceColumn.HeaderText = "Workspace";
            this.workspaceColumn.Width = 175;
            this.statusColumn.Name = "statusColumn";
            this.statusColumn.FieldName = "status";
            this.statusColumn.HeaderText = "Status";
            this.statusColumn.Width = 120;
            this.priorityColumn.Name = "priorityColumn";
            this.priorityColumn.FieldName = "priority";
            this.priorityColumn.HeaderText = "Priority";
            this.priorityColumn.Width = 95;
            this.startColumn.Name = "startColumn";
            this.startColumn.FieldName = "start_date";
            this.startColumn.HeaderText = "Start date";
            this.startColumn.Width = 115;
            this.startColumn.FormatString = "{0:d}";
            this.dueColumn.Name = "dueColumn";
            this.dueColumn.FieldName = "due_date";
            this.dueColumn.HeaderText = "Due date";
            this.dueColumn.Width = 115;
            this.dueColumn.FormatString = "{0:d}";
            this.tasksColumn.Name = "tasksColumn";
            this.tasksColumn.FieldName = "task_count";
            this.tasksColumn.HeaderText = "Tasks";
            this.tasksColumn.Width = 68;
            this.progressColumn.Name = "progressColumn";
            this.progressColumn.FieldName = "progress";
            this.progressColumn.HeaderText = "Progress (%)";
            this.progressColumn.Width = 110;
            this.projectGrid.Name = "projectGrid";
            this.projectGrid.Dock = DockStyle.Fill;
            this.projectGrid.AutoGenerateColumns = false;
            this.projectGrid.ReadOnly = true;
            this.projectGrid.MasterTemplate.AllowAddNewRow = false;
            this.projectGrid.MasterTemplate.AllowDeleteRow = false;
            this.projectGrid.MasterTemplate.AllowEditRow = false;
            this.projectGrid.MasterTemplate.EnableFiltering = true;
            this.projectGrid.MasterTemplate.ShowFilteringRow = true;
            this.projectGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.keyColumn, this.titleColumn, this.workspaceColumn, this.statusColumn, this.priorityColumn, this.startColumn, this.dueColumn, this.tasksColumn, this.progressColumn });
            this.projectGrid.CurrentRowChanged += this.ProjectSelectionChanged;
            this.projectGrid.CellDoubleClick += this.ProjectDoubleClicked;

            this.exportDialog.DefaultExt = "csv";
            this.exportDialog.Filter = "CSV files (*.csv)|*.csv";
            this.exportDialog.FileName = "projects.csv";

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Dock = DockStyle.Bottom;
            this.statusLabel.Padding = new Padding(10, 4, 10, 0);
            this.statusLabel.Height = 28;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(1180, 680);
            this.MinimumSize = new Size(1175, 460);
            this.Controls.Add(this.projectGrid);
            this.Controls.Add(this.statusLabel);
            this.Controls.Add(this.toolbar);
            this.Font = new Font("Segoe UI", 10F);
            this.Name = "ProjectManagementForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Business Suite | Project Management";
            this.Load += this.ProjectManagementForm_Load;
            ((System.ComponentModel.ISupportInitialize)this.projectGrid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.projectGrid).EndInit();
            this.toolbar.ResumeLayout(false);
            this.toolbar.PerformLayout();
            this.ResumeLayout(false);
        }

        private Panel toolbar;
        private RadTextBox searchTextBox;
        private RadDropDownList workspaceList;
        private RadDropDownList scopeList;
        private RadButton newButton;
        private RadButton editButton;
        private RadButton archiveButton;
        private RadButton trashButton;
        private RadButton refreshButton;
        private RadButton exportButton;
        private RadButton newTaskButton;
        private RadButton cloneButton;
        private RadButton bulkButton;
        private RadButton milestonesButton;
        private RadButton risksButton;
        private RadButton scheduleButton;
        private RadButton workHoursButton;
        private RadGridView projectGrid;
        private GridViewTextBoxColumn keyColumn;
        private GridViewTextBoxColumn titleColumn;
        private GridViewTextBoxColumn workspaceColumn;
        private GridViewTextBoxColumn statusColumn;
        private GridViewTextBoxColumn priorityColumn;
        private GridViewTextBoxColumn startColumn;
        private GridViewTextBoxColumn dueColumn;
        private GridViewTextBoxColumn tasksColumn;
        private GridViewTextBoxColumn progressColumn;
        private Label statusLabel;
        private SaveFileDialog exportDialog;
    }
}
