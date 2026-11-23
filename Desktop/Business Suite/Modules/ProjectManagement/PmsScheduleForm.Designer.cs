using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsScheduleForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.status = new Label();
            this.startLabel = new Label();
            this.dueLabel = new Label();
            this.grid = new RadGridView();
            this.filter = new RadDropDownList();
            this.start = new RadDateTimePicker();
            this.due = new RadDateTimePicker();
            this.save = new RadButton();
            this.clear = new RadButton();
            this.refresh = new RadButton();
            this.close = new RadButton();
            this.dependenciesButton = new RadButton();
            this.baselinesButton = new RadButton();
            this.planButton = new RadButton();
            this.capacityButton = new RadButton();
            this.keyColumn = new GridViewTextBoxColumn();
            this.nameColumn = new GridViewTextBoxColumn();
            this.stateColumn = new GridViewTextBoxColumn();
            this.startColumn = new GridViewTextBoxColumn();
            this.dueColumn = new GridViewTextBoxColumn();
            this.durationColumn = new GridViewTextBoxColumn();
            this.conflictsColumn = new GridViewTextBoxColumn();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            this.heading.Name = "heading";
            this.heading.Location = new Point(13, 13);
            this.heading.Size = new Size(534, 27);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);
            this.filter.Name = "filter";
            this.filter.Location = new Point(552, 13);
            this.filter.Size = new Size(152, 27);
            this.filter.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.filter.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("All tasks") { Value = "" },
                new RadListDataItem("Scheduled") { Value = "scheduled" },
                new RadListDataItem("Unscheduled") { Value = "unscheduled" },
                new RadListDataItem("Date conflicts") { Value = "conflicts" } });
            this.filter.SelectedIndex = 0;
            this.filter.TextChanged += this.FilterChanged;
            this.grid.Name = "grid";
            this.grid.Location = new Point(13, 49);
            this.grid.Size = new Size(817, 310);
            this.grid.AutoGenerateColumns = false;
            this.grid.ReadOnly = true;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.ShowRowHeaderColumn = false;
            this.grid.CurrentRowChanged += this.SelectionChanged;
            this.startLabel.Text = "Start date";
            this.startLabel.Location = new Point(13, 373);
            this.startLabel.Size = new Size(142, 23);
            this.start.Name = "start";
            this.start.Location = new Point(13, 398);
            this.start.Size = new Size(148, 25);
            this.start.ShowCheckBox = true;
            this.start.Checked = false;
            this.start.Enabled = false;
            this.start.Format = DateTimePickerFormat.Short;
            this.dueLabel.Text = "Due date";
            this.dueLabel.Location = new Point(174, 373);
            this.dueLabel.Size = new Size(142, 23);
            this.due.Name = "due";
            this.due.Location = new Point(174, 398);
            this.due.Size = new Size(148, 25);
            this.due.ShowCheckBox = true;
            this.due.Checked = false;
            this.due.Enabled = false;
            this.due.Format = DateTimePickerFormat.Short;
            this.save.Name = "save";
            this.save.Text = "Save schedule";
            this.save.Location = new Point(444, 396);
            this.save.Size = new Size(129, 29);
            this.save.Enabled = false;
            this.save.Click += this.SaveClicked;
            this.clear.Name = "clear";
            this.clear.Text = "Clear dates";
            this.clear.Location = new Point(335, 396);
            this.clear.Size = new Size(96, 29);
            this.clear.Enabled = false;
            this.clear.Click += this.ClearClicked;
            this.dependenciesButton.Name = "dependenciesButton";
            this.dependenciesButton.Text = "Dependencies";
            this.dependenciesButton.Location = new Point(585, 396);
            this.dependenciesButton.Size = new Size(119, 29);
            this.dependenciesButton.Enabled = false;
            this.dependenciesButton.Click += this.DependenciesClicked;
            this.baselinesButton.Name = "baselinesButton";
            this.baselinesButton.Text = "Baselines";
            this.baselinesButton.Location = new Point(716, 396);
            this.baselinesButton.Size = new Size(114, 29);
            this.baselinesButton.Click += this.BaselinesClicked;
            this.planButton.Name = "planButton";
            this.planButton.Text = "Dependency plan";
            this.planButton.Location = new Point(563, 441);
            this.planButton.Size = new Size(141, 29);
            this.planButton.Click += this.PlanClicked;
            this.capacityButton.Name = "capacityButton";
            this.capacityButton.Text = "Resource capacity";
            this.capacityButton.Location = new Point(407, 441);
            this.capacityButton.Size = new Size(145, 29);
            this.capacityButton.Click += this.CapacityClicked;
            this.status.Location = new Point(13, 443);
            this.status.Size = new Size(380, 34);
            this.refresh.Name = "refresh";
            this.refresh.Text = "Refresh";
            this.refresh.Location = new Point(716, 12);
            this.refresh.Size = new Size(114, 29);
            this.refresh.Click += this.RefreshClicked;
            this.close.Name = "close";
            this.close.Text = "Close";
            this.close.Location = new Point(716, 441);
            this.close.Size = new Size(114, 29);
            this.close.DialogResult = DialogResult.Cancel;
            this.keyColumn.Name = "keyColumn";
            this.keyColumn.FieldName = "task_key";
            this.keyColumn.HeaderText = "Task";
            this.keyColumn.Width = 101;
            this.nameColumn.Name = "nameColumn";
            this.nameColumn.FieldName = "title";
            this.nameColumn.HeaderText = "Title";
            this.nameColumn.Width = 235;
            this.stateColumn.Name = "stateColumn";
            this.stateColumn.FieldName = "status";
            this.stateColumn.HeaderText = "Status";
            this.stateColumn.Width = 101;
            this.startColumn.Name = "startColumn";
            this.startColumn.FieldName = "start_date";
            this.startColumn.HeaderText = "Start date";
            this.startColumn.Width = 104;
            this.dueColumn.Name = "dueColumn";
            this.dueColumn.FieldName = "due_date";
            this.dueColumn.HeaderText = "Due date";
            this.dueColumn.Width = 104;
            this.durationColumn.Name = "durationColumn";
            this.durationColumn.FieldName = "duration_days";
            this.durationColumn.HeaderText = "Days";
            this.durationColumn.Width = 60;
            this.conflictsColumn.Name = "conflictsColumn";
            this.conflictsColumn.FieldName = "conflicts";
            this.conflictsColumn.HeaderText = "Date conflicts";
            this.conflictsColumn.Width = 95;
            this.startColumn.FormatString = "{0:d}";
            this.dueColumn.FormatString = "{0:d}";
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.keyColumn, this.nameColumn, this.stateColumn, this.startColumn, this.dueColumn,
                this.durationColumn, this.conflictsColumn });
            this.Controls.AddRange(new Control[] { this.heading, this.filter, this.grid, this.refresh, this.startLabel,
                this.start, this.dueLabel, this.due, this.save, this.clear, this.dependenciesButton, this.baselinesButton, this.planButton, this.capacityButton, this.status, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(843, 486);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.Text = "Project Schedule";
            this.Load += this.ScheduleLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
        }

        private Label heading, status, startLabel, dueLabel;
        private RadGridView grid;
        private RadDropDownList filter;
        private RadDateTimePicker start, due;
        private RadButton save, clear, refresh, close, dependenciesButton, baselinesButton, planButton, capacityButton;
        private GridViewTextBoxColumn keyColumn, nameColumn, stateColumn, startColumn, dueColumn, durationColumn, conflictsColumn;
    }
}
