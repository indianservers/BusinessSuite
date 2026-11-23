using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeProfileHistoryForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.grid = new RadGridView();
            this.status = new Label();
            this.refresh = new RadButton();
            this.close = new RadButton();
            this.fieldColumn = new GridViewTextBoxColumn();
            this.entityColumn = new GridViewTextBoxColumn();
            this.actionColumn = new GridViewTextBoxColumn();
            this.previousColumn = new GridViewTextBoxColumn();
            this.updatedColumn = new GridViewTextBoxColumn();
            this.dateColumn = new GridViewTextBoxColumn();
            this.actorColumn = new GridViewTextBoxColumn();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            this.heading.Name = "heading";
            this.heading.Location = new Point(12, 15);
            this.heading.Size = new Size(649, 26);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);
            this.grid.Name = "grid";
            this.grid.Location = new Point(12, 53);
            this.grid.Size = new Size(879, 345);
            this.grid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.grid.ReadOnly = true;
            this.grid.AutoGenerateColumns = false;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.EnableFiltering = true;
            this.grid.MasterTemplate.ShowRowHeaderColumn = false;
            this.status.Name = "status";
            this.status.Location = new Point(12, 414);
            this.status.Size = new Size(730, 27);
            this.status.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
            this.refresh.Name = "refresh";
            this.refresh.Text = "Refresh";
            this.refresh.Location = new Point(800, 12);
            this.refresh.Size = new Size(91, 29);
            this.refresh.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            this.refresh.Click += this.RefreshClicked;
            this.close.Name = "close";
            this.close.Text = "Close";
            this.close.Location = new Point(800, 413);
            this.close.Size = new Size(91, 29);
            this.close.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.close.DialogResult = DialogResult.Cancel;
            this.fieldColumn.Name = "fieldColumn";
            this.fieldColumn.FieldName = "field_name";
            this.fieldColumn.HeaderText = "Field";
            this.fieldColumn.Width = 140;
            this.entityColumn.Name = "entityColumn";
            this.entityColumn.FieldName = "entity_type";
            this.entityColumn.HeaderText = "Record";
            this.entityColumn.Width = 137;
            this.actionColumn.Name = "actionColumn";
            this.actionColumn.FieldName = "action";
            this.actionColumn.HeaderText = "Action";
            this.actionColumn.Width = 80;
            this.previousColumn.Name = "previousColumn";
            this.previousColumn.FieldName = "before_value";
            this.previousColumn.HeaderText = "Before";
            this.previousColumn.Width = 143;
            this.updatedColumn.Name = "updatedColumn";
            this.updatedColumn.FieldName = "after_value";
            this.updatedColumn.HeaderText = "After";
            this.updatedColumn.Width = 143;
            this.dateColumn.Name = "dateColumn";
            this.dateColumn.FieldName = "created_at";
            this.dateColumn.HeaderText = "Changed at";
            this.dateColumn.Width = 134;
            this.actorColumn.Name = "actorColumn";
            this.actorColumn.FieldName = "actor";
            this.actorColumn.HeaderText = "Actor";
            this.actorColumn.Width = 75;
            this.dateColumn.FormatString = "{0:g}";
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.fieldColumn, this.entityColumn, this.actionColumn, this.previousColumn,
                this.updatedColumn, this.dateColumn, this.actorColumn });
            this.Controls.AddRange(new Control[] { this.heading, this.grid, this.status, this.refresh, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(903, 459);
            this.MinimumSize = new Size(746, 416);
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.Text = "Employee Profile History";
            this.Load += this.HistoryLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
        }

        private Label heading, status;
        private RadGridView grid;
        private RadButton refresh, close;
        private GridViewTextBoxColumn fieldColumn, entityColumn, actionColumn, previousColumn, updatedColumn, dateColumn, actorColumn;
    }
}
