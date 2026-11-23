using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsResourceAllocationsForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.taskLabel = new Label();
            this.personLabel = new Label();
            this.status = new Label();
            this.taskFilter = new RadDropDownList();
            this.personFilter = new RadDropDownList();
            this.grid = new RadGridView();
            this.dateColumn = new GridViewTextBoxColumn();
            this.keyColumn = new GridViewTextBoxColumn();
            this.titleColumn = new GridViewTextBoxColumn();
            this.personColumn = new GridViewTextBoxColumn();
            this.hoursColumn = new GridViewTextBoxColumn();
            this.close = new RadButton();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            this.heading.Name = "heading";
            this.heading.Location = new Point(13, 13);
            this.heading.Size = new Size(793, 28);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);
            this.taskLabel.Text = "Task";
            this.taskLabel.Location = new Point(13, 45);
            this.taskLabel.Size = new Size(367, 23);
            this.taskFilter.Name = "taskFilter";
            this.taskFilter.Location = new Point(13, 70);
            this.taskFilter.Size = new Size(367, 26);
            this.taskFilter.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.taskFilter.SelectedIndexChanged += this.FiltersChanged;
            this.personLabel.Text = "Assignee";
            this.personLabel.Location = new Point(396, 45);
            this.personLabel.Size = new Size(396, 23);
            this.personFilter.Name = "personFilter";
            this.personFilter.Location = new Point(396, 70);
            this.personFilter.Size = new Size(410, 26);
            this.personFilter.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.personFilter.SelectedIndexChanged += this.FiltersChanged;
            this.grid.Name = "grid";
            this.grid.Location = new Point(13, 112);
            this.grid.Size = new Size(793, 300);
            this.grid.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
            this.grid.ReadOnly = true;
            this.grid.AutoGenerateColumns = false;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.ShowRowHeaderColumn = false;
            this.dateColumn.Name = "dateColumn";
            this.dateColumn.FieldName = "date";
            this.dateColumn.HeaderText = "Date";
            this.dateColumn.Width = 112;
            this.dateColumn.FormatString = "{0:d}";
            this.keyColumn.Name = "keyColumn";
            this.keyColumn.FieldName = "task_key";
            this.keyColumn.HeaderText = "Task";
            this.keyColumn.Width = 112;
            this.titleColumn.Name = "titleColumn";
            this.titleColumn.FieldName = "title";
            this.titleColumn.HeaderText = "Title";
            this.titleColumn.Width = 257;
            this.personColumn.Name = "personColumn";
            this.personColumn.FieldName = "person";
            this.personColumn.HeaderText = "Assignee";
            this.personColumn.Width = 211;
            this.hoursColumn.Name = "hoursColumn";
            this.hoursColumn.FieldName = "hours";
            this.hoursColumn.HeaderText = "Hours";
            this.hoursColumn.Width = 94;
            this.hoursColumn.FormatString = "{0:N4}";
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.dateColumn, this.keyColumn, this.titleColumn, this.personColumn, this.hoursColumn });
            this.status.Name = "status";
            this.status.Location = new Point(13, 426);
            this.status.Size = new Size(640, 32);
            this.status.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
            this.close.Name = "close";
            this.close.Text = "Close";
            this.close.Location = new Point(704, 426);
            this.close.Size = new Size(102, 29);
            this.close.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.close.DialogResult = DialogResult.Cancel;
            this.Controls.AddRange(new Control[] { this.heading, this.taskLabel, this.taskFilter, this.personLabel,
                this.personFilter, this.grid, this.status, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(819, 471);
            this.MinimumSize = new Size(838, 441);
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.Text = "Daily Resource Allocations";
            this.Load += this.AllocationsLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
        }

        private Label heading, taskLabel, personLabel, status;
        private RadDropDownList taskFilter, personFilter;
        private RadGridView grid;
        private GridViewTextBoxColumn dateColumn, keyColumn, titleColumn, personColumn, hoursColumn;
        private RadButton close;
    }
}
