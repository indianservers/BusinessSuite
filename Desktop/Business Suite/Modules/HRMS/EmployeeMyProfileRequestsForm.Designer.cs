using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeMyProfileRequestsForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.status = new Label();
            this.reasonLabel = new Label();
            this.reviewerNoteLabel = new Label();
            this.grid = new RadGridView();
            this.filter = new RadDropDownList();
            this.reason = new RadTextBox();
            this.reviewerNote = new RadTextBox();
            this.refresh = new RadButton();
            this.newRequest = new RadButton();
            this.close = new RadButton();
            this.typeColumn = new GridViewTextBoxColumn();
            this.stateColumn = new GridViewTextBoxColumn();
            this.fieldsColumn = new GridViewTextBoxColumn();
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
            this.filter.SelectedIndex = 3;
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
            this.reasonLabel.Text = "Request Reason";
            this.reasonLabel.Location = new Point(13, 315);
            this.reasonLabel.Size = new Size(420, 24);
            this.reason.Name = "reason";
            this.reason.Location = new Point(13, 341);
            this.reason.Size = new Size(854, 64);
            this.reason.Multiline = true;
            this.reason.ReadOnly = true;
            this.reason.ScrollBars = ScrollBars.Vertical;
            this.reviewerNoteLabel.Text = "Reviewer Note";
            this.reviewerNoteLabel.Location = new Point(13, 414);
            this.reviewerNoteLabel.Size = new Size(402, 24);
            this.reviewerNote.Name = "reviewerNote";
            this.reviewerNote.Location = new Point(13, 440);
            this.reviewerNote.Size = new Size(854, 36);
            this.reviewerNote.ReadOnly = true;
            this.reviewerNote.Multiline = true;
            this.reviewerNote.ScrollBars = ScrollBars.Vertical;
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
            this.fieldsColumn.Width = 370;
            this.submittedColumn.Name = "submittedColumn";
            this.submittedColumn.FieldName = "created_at";
            this.submittedColumn.HeaderText = "Submitted";
            this.submittedColumn.Width = 126;
            this.reviewedColumn.Name = "reviewedColumn";
            this.reviewedColumn.FieldName = "reviewed_at";
            this.reviewedColumn.HeaderText = "Reviewed";
            this.reviewedColumn.Width = 122;
            this.submittedColumn.FormatString = "{0:g}";
            this.reviewedColumn.FormatString = "{0:g}";
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.typeColumn, this.stateColumn, this.fieldsColumn,
                this.submittedColumn, this.reviewedColumn });
            this.Controls.AddRange(new Control[] {
                this.heading, this.grid, this.filter, this.refresh, this.newRequest, this.reasonLabel, this.reason,
                this.reviewerNoteLabel, this.reviewerNote, this.status, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(881, 561);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.Text = "My Change Requests";
            this.Load += this.RequestsLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
        }

        private Label heading, status, reasonLabel, reviewerNoteLabel;
        private RadGridView grid;
        private GridViewTextBoxColumn typeColumn, stateColumn, fieldsColumn, submittedColumn, reviewedColumn;
        private RadDropDownList filter;
        private RadTextBox reason, reviewerNote;
        private RadButton close, refresh, newRequest;
    }
}

