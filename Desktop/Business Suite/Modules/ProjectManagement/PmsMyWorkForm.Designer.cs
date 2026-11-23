#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsMyWorkForm
    {
        private void InitializeComponent()
        {
            this.toolbar = new Panel();
            this.searchTextBox = new RadTextBox();
            this.workspaceList = new RadDropDownList();
            this.viewList = new RadDropDownList();
            this.overdueCheckBox = new CheckBox();
            this.refreshButton = new RadButton();
            this.exportButton = new RadButton();
            this.editButton = new RadButton();
            this.assignButton = new RadButton();
            this.trashButton = new RadButton();
            this.checklistButton = new RadButton();
            this.subtasksButton = new RadButton();
            this.dependenciesButton = new RadButton();
            this.deletedColumn = new GridViewTextBoxColumn();
            this.taskGrid = new RadGridView();
            this.descriptionLabel = new Label();
            this.descriptionTextBox = new RadTextBox();
            this.statusLabel = new Label();
            this.exportDialog = new SaveFileDialog();
            this.keyColumn = new GridViewTextBoxColumn();
            this.titleColumn = new GridViewTextBoxColumn();
            this.projectColumn = new GridViewTextBoxColumn();
            this.workspaceColumn = new GridViewTextBoxColumn();
            this.typeColumn = new GridViewTextBoxColumn();
            this.statusColumn = new GridViewTextBoxColumn();
            this.priorityColumn = new GridViewTextBoxColumn();
            this.startColumn = new GridViewTextBoxColumn();
            this.dueColumn = new GridViewTextBoxColumn();
            this.hoursColumn = new GridViewTextBoxColumn();
            ((System.ComponentModel.ISupportInitialize)this.taskGrid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.taskGrid.MasterTemplate).BeginInit();
            this.toolbar.SuspendLayout();
            this.SuspendLayout();

            this.searchTextBox.Name = "searchTextBox";
            this.searchTextBox.NullText = "Search tasks";
            this.searchTextBox.Location = new Point(10, 12);
            this.searchTextBox.Size = new Size(194, 25);
            this.searchTextBox.KeyDown += this.SearchKeyDown;

            this.workspaceList.Name = "workspaceList";
            this.workspaceList.Location = new Point(212, 12);
            this.workspaceList.Size = new Size(160, 25);
            this.workspaceList.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.workspaceList.SelectedIndexChanged += this.ViewChanged;

            this.viewList.Name = "viewList";
            this.viewList.Location = new Point(381, 12);
            this.viewList.Size = new Size(145, 25);
            this.viewList.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.viewList.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("My work") { Value = "mine" },
                new RadListDataItem("All tasks") { Value = "all" },
                new RadListDataItem("Teams") { Value = "teams" },
                new RadListDataItem("Batches") { Value = "batches" },
                new RadListDataItem("Unassigned") { Value = "unassigned" },
                new RadListDataItem("Completed") { Value = "completed" },
                new RadListDataItem("Pending approvals") { Value = "approvals" },
                new RadListDataItem("Trash") { Value = "trash" }
            });
            this.viewList.SelectedIndex = 0;
            this.viewList.SelectedIndexChanged += this.ViewChanged;

            this.overdueCheckBox.Name = "overdueCheckBox";
            this.overdueCheckBox.Location = new Point(537, 12);
            this.overdueCheckBox.Size = new Size(124, 25);
            this.overdueCheckBox.Text = "Overdue only";
            this.overdueCheckBox.CheckedChanged += this.ViewChanged;

            this.refreshButton.Name = "refreshButton";
            this.refreshButton.Text = "Apply filters";
            this.refreshButton.Location = new Point(669, 10);
            this.refreshButton.Size = new Size(96, 28);
            this.refreshButton.Click += this.RefreshClicked;

            this.exportButton.Name = "exportButton";
            this.exportButton.Text = "Export CSV";
            this.exportButton.Location = new Point(774, 10);
            this.exportButton.Size = new Size(92, 28);
            this.exportButton.Click += this.ExportClicked;

            this.editButton.Name = "editButton";
            this.editButton.Text = "Edit task";
            this.editButton.Location = new Point(875, 10);
            this.editButton.Size = new Size(81, 28);
            this.editButton.Click += this.EditTaskClicked;

            this.assignButton.Name = "assignButton";
            this.assignButton.Text = "Assign task";
            this.assignButton.Location = new Point(965, 10);
            this.assignButton.Size = new Size(89, 28);
            this.assignButton.Enabled = false;
            this.assignButton.Click += this.AssignTaskClicked;

            this.trashButton.Name = "trashButton";
            this.trashButton.Text = "Move to Trash";
            this.trashButton.Location = new Point(1062, 10);
            this.trashButton.Size = new Size(105, 28);
            this.trashButton.Enabled = false;
            this.trashButton.Click += this.TrashTaskClicked;

            this.checklistButton.Name = "checklistButton";
            this.checklistButton.Text = "Checklist";
            this.checklistButton.Location = new Point(10, 44);
            this.checklistButton.Size = new Size(91, 28);
            this.checklistButton.Enabled = false;
            this.checklistButton.Click += this.OpenChecklistClicked;
            this.subtasksButton.Name = "subtasksButton";
            this.subtasksButton.Text = "Subtasks";
            this.subtasksButton.Location = new Point(111, 44);
            this.subtasksButton.Size = new Size(91, 28);
            this.subtasksButton.Enabled = false;
            this.subtasksButton.Click += this.OpenSubtasksClicked;
            this.dependenciesButton.Name = "dependenciesButton";
            this.dependenciesButton.Text = "Dependencies";
            this.dependenciesButton.Location = new Point(211, 44);
            this.dependenciesButton.Size = new Size(113, 28);
            this.dependenciesButton.Enabled = false;
            this.dependenciesButton.Click += this.OpenDependenciesClicked;

            this.toolbar.Name = "toolbar";
            this.toolbar.Dock = DockStyle.Top;
            this.toolbar.Height = 80;
            this.toolbar.Controls.AddRange(new Control[] {
                this.searchTextBox, this.workspaceList, this.viewList, this.overdueCheckBox, this.refreshButton,
                this.exportButton, this.editButton, this.assignButton, this.trashButton, this.checklistButton, this.subtasksButton, this.dependenciesButton });

            this.keyColumn.Name = "keyColumn";
            this.keyColumn.FieldName = "task_key";
            this.keyColumn.HeaderText = "Key";
            this.keyColumn.Width = 110;

            this.titleColumn.Name = "titleColumn";
            this.titleColumn.FieldName = "title";
            this.titleColumn.HeaderText = "Task";
            this.titleColumn.Width = 240;

            this.projectColumn.Name = "projectColumn";
            this.projectColumn.FieldName = "project";
            this.projectColumn.HeaderText = "Project";
            this.projectColumn.Width = 180;

            this.workspaceColumn.Name = "workspaceColumn";
            this.workspaceColumn.FieldName = "workspace";
            this.workspaceColumn.HeaderText = "Workspace";
            this.workspaceColumn.Width = 170;

            this.typeColumn.Name = "typeColumn";
            this.typeColumn.FieldName = "work_type";
            this.typeColumn.HeaderText = "Type";
            this.typeColumn.Width = 95;

            this.statusColumn.Name = "statusColumn";
            this.statusColumn.FieldName = "status";
            this.statusColumn.HeaderText = "Status";
            this.statusColumn.Width = 100;

            this.priorityColumn.Name = "priorityColumn";
            this.priorityColumn.FieldName = "priority";
            this.priorityColumn.HeaderText = "Priority";
            this.priorityColumn.Width = 86;

            this.startColumn.Name = "startColumn";
            this.startColumn.FieldName = "start_date";
            this.startColumn.HeaderText = "Start date";
            this.startColumn.Width = 104;
            this.startColumn.FormatString = "{0:d}";

            this.dueColumn.Name = "dueColumn";
            this.dueColumn.FieldName = "due_date";
            this.dueColumn.HeaderText = "Due date";
            this.dueColumn.Width = 104;
            this.dueColumn.FormatString = "{0:d}";

            this.hoursColumn.Name = "hoursColumn";
            this.hoursColumn.FieldName = "estimated_hours";
            this.hoursColumn.HeaderText = "Est. hours";
            this.hoursColumn.Width = 89;

            this.taskGrid.Name = "taskGrid";
            this.deletedColumn.Name = "deletedColumn";
            this.deletedColumn.FieldName = "deleted_at";
            this.deletedColumn.HeaderText = "Deleted";
            this.deletedColumn.FormatString = "{0:g}";
            this.deletedColumn.Width = 155;
            this.deletedColumn.IsVisible = false;
            this.taskGrid.Dock = DockStyle.Fill;
            this.taskGrid.AutoGenerateColumns = false;
            this.taskGrid.ReadOnly = true;
            this.taskGrid.MasterTemplate.AllowAddNewRow = false;
            this.taskGrid.MasterTemplate.AllowDeleteRow = false;
            this.taskGrid.MasterTemplate.AllowEditRow = false;
            this.taskGrid.MasterTemplate.EnableFiltering = true;
            this.taskGrid.MasterTemplate.ShowFilteringRow = true;
            this.taskGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.keyColumn, this.titleColumn, this.projectColumn, this.workspaceColumn, this.typeColumn,
                this.statusColumn, this.priorityColumn, this.startColumn, this.dueColumn, this.hoursColumn, this.deletedColumn });
            this.taskGrid.CurrentRowChanged += this.TaskSelectionChanged;
            this.taskGrid.CellDoubleClick += this.TaskDoubleClicked;

            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Description";
            this.descriptionLabel.Dock = DockStyle.Bottom;
            this.descriptionLabel.Padding = new Padding(10, 4, 10, 0);
            this.descriptionLabel.Height = 26;

            this.descriptionTextBox.Name = "descriptionTextBox";
            this.descriptionTextBox.Multiline = true;
            this.descriptionTextBox.ReadOnly = true;
            this.descriptionTextBox.ScrollBars = ScrollBars.Vertical;
            this.descriptionTextBox.Dock = DockStyle.Bottom;
            this.descriptionTextBox.Height = 74;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Dock = DockStyle.Bottom;
            this.statusLabel.Padding = new Padding(10, 4, 10, 0);
            this.statusLabel.Height = 28;

            this.exportDialog.DefaultExt = "csv";
            this.exportDialog.Filter = "CSV files (*.csv)|*.csv";
            this.exportDialog.FileName = "my-work.csv";

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(1195, 665);
            this.MinimumSize = new Size(1195, 420);
            this.Controls.Add(this.taskGrid);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.descriptionTextBox);
            this.Controls.Add(this.statusLabel);
            this.Controls.Add(this.toolbar);
            this.Font = new Font("Segoe UI", 10F);
            this.Name = "PmsMyWorkForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Business Suite | My Work";
            this.Load += this.MyWorkLoaded;
            ((System.ComponentModel.ISupportInitialize)this.taskGrid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.taskGrid).EndInit();
            this.toolbar.ResumeLayout(false);
            this.toolbar.PerformLayout();
            this.ResumeLayout(false);
        }

        private Panel toolbar;
        private RadTextBox searchTextBox;
        private RadDropDownList workspaceList;
        private RadDropDownList viewList;
        private CheckBox overdueCheckBox;
        private RadButton refreshButton;
        private RadButton exportButton;
        private RadButton editButton;
        private RadButton assignButton;
        private RadButton trashButton;
        private RadButton checklistButton;
        private RadButton subtasksButton;
        private RadButton dependenciesButton;
        private GridViewTextBoxColumn deletedColumn;
        private RadGridView taskGrid;
        private GridViewTextBoxColumn keyColumn;
        private GridViewTextBoxColumn titleColumn;
        private GridViewTextBoxColumn projectColumn;
        private GridViewTextBoxColumn workspaceColumn;
        private GridViewTextBoxColumn typeColumn;
        private GridViewTextBoxColumn statusColumn;
        private GridViewTextBoxColumn priorityColumn;
        private GridViewTextBoxColumn startColumn;
        private GridViewTextBoxColumn dueColumn;
        private GridViewTextBoxColumn hoursColumn;
        private Label descriptionLabel;
        private RadTextBox descriptionTextBox;
        private Label statusLabel;
        private SaveFileDialog exportDialog;
    }
}
