using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeOnboardingForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.progress = new Label();
            this.status = new Label();
            this.templateLabel = new Label();
            this.reasonLabel = new Label();
            this.template = new RadDropDownList();
            this.reason = new RadTextBox();
            this.grid = new RadGridView();
            this.refresh = new RadButton();
            this.assign = new RadButton();
            this.complete = new RadButton();
            this.close = new RadButton();
            this.taskColumn = new GridViewTextBoxColumn();
            this.typeColumn = new GridViewTextBoxColumn();
            this.dueColumn = new GridViewTextBoxColumn();
            this.stateColumn = new GridViewTextBoxColumn();
            this.completedColumn = new GridViewTextBoxColumn();
            this.notesColumn = new GridViewTextBoxColumn();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            this.heading.Name = "heading";
            this.heading.Location = new Point(13, 13);
            this.heading.Size = new Size(615, 27);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);
            this.templateLabel.Text = "Onboarding template";
            this.templateLabel.Location = new Point(13, 48);
            this.templateLabel.Size = new Size(287, 23);
            this.template.Name = "template";
            this.template.Location = new Point(13, 73);
            this.template.Size = new Size(430, 27);
            this.template.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.template.TextChanged += this.InputsChanged;
            this.template.Enabled = false;
            this.assign.Name = "assign";
            this.assign.Text = "Apply template";
            this.assign.Location = new Point(455, 72);
            this.assign.Size = new Size(133, 29);
            this.assign.Enabled = false;
            this.assign.Click += this.ApplyTemplateClicked;
            this.progress.Location = new Point(604, 73);
            this.progress.Size = new Size(224, 24);
            this.grid.Name = "grid";
            this.grid.Location = new Point(13, 113);
            this.grid.Size = new Size(823, 231);
            this.grid.ReadOnly = true;
            this.grid.AutoGenerateColumns = false;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.ShowRowHeaderColumn = false;
            this.grid.CurrentRowChanged += this.SelectionChanged;
            this.reasonLabel.Text = "Completion reason";
            this.reasonLabel.Location = new Point(13, 358);
            this.reasonLabel.Size = new Size(270, 23);
            this.reason.Name = "reason";
            this.reason.Location = new Point(13, 384);
            this.reason.Size = new Size(634, 25);
            this.reason.MaxLength = 1000;
            this.reason.Enabled = false;
            this.reason.TextChanged += this.InputsChanged;
            this.complete.Name = "complete";
            this.complete.Text = "Complete selected item";
            this.complete.Location = new Point(657, 382);
            this.complete.Size = new Size(179, 29);
            this.complete.Enabled = false;
            this.complete.Click += this.CompleteClicked;
            this.status.Location = new Point(13, 424);
            this.status.Size = new Size(686, 32);
            this.refresh.Name = "refresh";
            this.refresh.Text = "Refresh";
            this.refresh.Location = new Point(712, 12);
            this.refresh.Size = new Size(124, 29);
            this.refresh.Click += this.RefreshClicked;
            this.close.Name = "close";
            this.close.Text = "Close";
            this.close.Location = new Point(712, 423);
            this.close.Size = new Size(124, 29);
            this.close.DialogResult = DialogResult.Cancel;
            this.taskColumn.Name = "taskColumn";
            this.taskColumn.FieldName = "task_name";
            this.taskColumn.HeaderText = "Task";
            this.taskColumn.Width = 217;
            this.typeColumn.Name = "typeColumn";
            this.typeColumn.FieldName = "category";
            this.typeColumn.HeaderText = "Category";
            this.typeColumn.Width = 108;
            this.dueColumn.Name = "dueColumn";
            this.dueColumn.FieldName = "due_date";
            this.dueColumn.HeaderText = "Due";
            this.dueColumn.Width = 93;
            this.stateColumn.Name = "stateColumn";
            this.stateColumn.FieldName = "status";
            this.stateColumn.HeaderText = "Status";
            this.stateColumn.Width = 105;
            this.completedColumn.Name = "completedColumn";
            this.completedColumn.FieldName = "completed_at";
            this.completedColumn.HeaderText = "Completed";
            this.completedColumn.Width = 119;
            this.notesColumn.Name = "notesColumn";
            this.notesColumn.FieldName = "notes";
            this.notesColumn.HeaderText = "Notes";
            this.notesColumn.Width = 176;
            this.dueColumn.FormatString = "{0:d}";
            this.completedColumn.FormatString = "{0:g}";
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.taskColumn, this.typeColumn, this.dueColumn, this.stateColumn, this.completedColumn, this.notesColumn });
            this.Controls.AddRange(new Control[] { this.heading, this.templateLabel, this.template, this.assign,
                this.progress, this.grid, this.reasonLabel, this.reason, this.complete, this.status, this.refresh, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(849, 467);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.Text = "Employee Onboarding";
            this.Load += this.OnboardingLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
        }

        private Label heading, progress, status, templateLabel, reasonLabel;
        private RadDropDownList template;
        private RadTextBox reason;
        private RadGridView grid;
        private GridViewTextBoxColumn taskColumn, typeColumn, dueColumn, stateColumn, completedColumn, notesColumn;
        private RadButton refresh, assign, complete, close;
    }
}
