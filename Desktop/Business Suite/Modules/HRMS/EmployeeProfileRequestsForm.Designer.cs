using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeProfileRequestsForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.status = new Label();
            this.hint = new Label();
            this.comparisonLabel = new Label();
            this.remarksLabel = new Label();
            this.grid = new RadGridView();
            this.filter = new RadDropDownList();
            this.comparison = new RadTextBox();
            this.remarks = new RadTextBox();
            this.refresh = new RadButton();
            this.newRequest = new RadButton();
            this.close = new RadButton();
            this.approve = new RadButton();
            this.reject = new RadButton();
            this.typeColumn = new GridViewTextBoxColumn();
            this.stateColumn = new GridViewTextBoxColumn();
            this.fieldsColumn = new GridViewTextBoxColumn();
            this.effectiveColumn = new GridViewTextBoxColumn();
            this.submittedColumn = new GridViewTextBoxColumn();
            this.reviewedColumn = new GridViewTextBoxColumn();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            this.heading.Name = "heading";
            this.heading.Location = new Point(13, 12);
            this.heading.Size = new Size(391, 25);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);
            this.filter.Name = "filter";
            this.filter.Location = new Point(569, 10);
            this.filter.Size = new Size(140, 26);
            this.filter.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.filter.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Pending") { Value = "Pending" },
                new RadListDataItem("Approved") { Value = "Approved" },
                new RadListDataItem("Rejected") { Value = "Rejected" },
                new RadListDataItem("All statuses") { Value = "" } });
            this.filter.SelectedIndex = 0;
            this.filter.TextChanged += this.FilterChanged;
            this.grid.Name = "grid";
            this.grid.Location = new Point(13, 49);
            this.grid.Size = new Size(854, 254);
            this.grid.ReadOnly = true;
            this.grid.AutoGenerateColumns = false;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.ShowRowHeaderColumn = false;
            this.grid.CurrentRowChanged += this.SelectionChanged;
            this.comparisonLabel.Text = "Previous and requested values";
            this.comparisonLabel.Location = new Point(13, 315);
            this.comparisonLabel.Size = new Size(420, 24);
            this.comparison.Name = "comparison";
            this.comparison.Location = new Point(13, 341);
            this.comparison.Size = new Size(854, 64);
            this.comparison.Multiline = true;
            this.comparison.ReadOnly = true;
            this.comparison.ScrollBars = ScrollBars.Vertical;
            this.hint.Location = new Point(13, 410);
            this.hint.Size = new Size(854, 23);
            this.remarksLabel.Text = "Review remarks";
            this.remarksLabel.Location = new Point(13, 439);
            this.remarksLabel.Size = new Size(402, 24);
            this.remarks.Name = "remarks";
            this.remarks.Location = new Point(13, 464);
            this.remarks.Size = new Size(854, 25);
            this.remarks.MaxLength = 1000;
            this.remarks.Enabled = false;
            this.status.Location = new Point(13, 507);
            this.status.Size = new Size(527, 47);
            this.newRequest.Name = "newRequest";
            this.newRequest.Text = "New request";
            this.newRequest.Location = new Point(411, 9);
            this.newRequest.Size = new Size(146, 29);
            this.newRequest.Click += this.NewRequestClicked;
            this.refresh.Name = "refresh";
            this.refresh.Text = "Refresh";
            this.refresh.Location = new Point(720, 9);
            this.refresh.Size = new Size(147, 29);
            this.refresh.Click += this.RefreshClicked;
            this.approve.Name = "approve";
            this.approve.Text = "Approve";
            this.approve.Location = new Point(546, 505);
            this.approve.Size = new Size(101, 29);
            this.approve.Enabled = false;
            this.approve.Click += this.ApproveClicked;
            this.reject.Name = "reject";
            this.reject.Text = "Reject";
            this.reject.Location = new Point(656, 505);
            this.reject.Size = new Size(101, 29);
            this.reject.Enabled = false;
            this.reject.Click += this.RejectClicked;
            this.close.Name = "close";
            this.close.Text = "Close";
            this.close.Location = new Point(766, 505);
            this.close.Size = new Size(101, 29);
            this.close.DialogResult = DialogResult.Cancel;
            this.typeColumn.Name = "typeColumn";
            this.typeColumn.FieldName = "request_type";
            this.typeColumn.HeaderText = "Type";
            this.typeColumn.Width = 116;
            this.stateColumn.Name = "stateColumn";
            this.stateColumn.FieldName = "status";
            this.stateColumn.HeaderText = "Status";
            this.stateColumn.Width = 91;
            this.fieldsColumn.Name = "fieldsColumn";
            this.fieldsColumn.FieldName = "fields";
            this.fieldsColumn.HeaderText = "Requested fields";
            this.fieldsColumn.Width = 277;
            this.effectiveColumn.Name = "effectiveColumn";
            this.effectiveColumn.FieldName = "effective_date";
            this.effectiveColumn.HeaderText = "Effective date";
            this.effectiveColumn.Width = 118;
            this.submittedColumn.Name = "submittedColumn";
            this.submittedColumn.FieldName = "created_at";
            this.submittedColumn.HeaderText = "Submitted";
            this.submittedColumn.Width = 126;
            this.reviewedColumn.Name = "reviewedColumn";
            this.reviewedColumn.FieldName = "reviewed_at";
            this.reviewedColumn.HeaderText = "Reviewed";
            this.reviewedColumn.Width = 122;
            this.effectiveColumn.FormatString = "{0:d}";
            this.submittedColumn.FormatString = "{0:g}";
            this.reviewedColumn.FormatString = "{0:g}";
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.typeColumn, this.stateColumn, this.fieldsColumn, this.effectiveColumn,
                this.submittedColumn, this.reviewedColumn });
            this.Controls.AddRange(new Control[] {
                this.heading, this.grid, this.filter, this.refresh, this.newRequest, this.comparisonLabel, this.comparison,
                this.hint, this.remarksLabel, this.remarks, this.status, this.approve, this.reject, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(881, 561);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.Text = "Employee Profile Change Requests";
            this.Load += this.RequestsLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
        }

        private Label heading, status, hint, comparisonLabel, remarksLabel;
        private RadGridView grid;
        private GridViewTextBoxColumn typeColumn, stateColumn, fieldsColumn, effectiveColumn, submittedColumn, reviewedColumn;
        private RadDropDownList filter;
        private RadTextBox comparison, remarks;
        private RadButton approve, reject, close, refresh, newRequest;
    }
}
