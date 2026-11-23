using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeProfileChecksForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.reminderLabel = new Label();
            this.reminder = new RadDropDownList();
            this.certifications = new RadButton();
            this.requests = new RadButton();
            this.grid = new RadGridView();
            this.status = new Label();
            this.refresh = new RadButton();
            this.close = new RadButton();
            this.fieldColumn = new GridViewTextBoxColumn();
            this.entityColumn = new GridViewTextBoxColumn();
            this.actionColumn = new GridViewTextBoxColumn();
            this.dateColumn = new GridViewTextBoxColumn();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            this.heading.Name = "heading";
            this.heading.Location = new Point(12, 15);
            this.heading.Size = new Size(328, 26);
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
            this.status.Size = new Size(550, 27);
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
            this.fieldColumn.FieldName = "category";
            this.fieldColumn.HeaderText = "Category";
            this.fieldColumn.Width = 200;
            this.entityColumn.Name = "entityColumn";
            this.entityColumn.FieldName = "name";
            this.entityColumn.HeaderText = "Record";
            this.entityColumn.Width = 325;
            this.actionColumn.Name = "actionColumn";
            this.actionColumn.FieldName = "status";
            this.actionColumn.HeaderText = "Status";
            this.actionColumn.Width = 209;
            this.dateColumn.Name = "dateColumn";
            this.dateColumn.FieldName = "due_date";
            this.dateColumn.HeaderText = "Date";
            this.dateColumn.Width = 134;
            this.dateColumn.FormatString = "{0:d}";
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.fieldColumn, this.entityColumn, this.actionColumn, this.dateColumn });
            this.reminderLabel.Name = "reminderLabel";
            this.reminderLabel.Text = "Reminder window";
            this.reminderLabel.Location = new Point(351, 17);
            this.reminderLabel.Size = new Size(117, 24);
            this.reminder.Name = "reminder";
            this.reminder.Location = new Point(470, 13);
            this.reminder.Size = new Size(100, 27);
            this.reminder.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.reminder.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("30 days") { Value = 30 },
                new RadListDataItem("60 days") { Value = 60 },
                new RadListDataItem("90 days") { Value = 90 }
            });
            this.reminder.SelectedIndex = 2;
            this.reminder.SelectedIndexChanged += this.ReminderChanged;
            this.certifications.Name = "certifications";
            this.certifications.Text = "Review certifications";
            this.certifications.Location = new Point(579, 12);
            this.certifications.Size = new Size(151, 29);
            this.certifications.Click += this.CertificationsClicked;
            this.requests.Name = "requests";
            this.requests.Text = "Review requests";
            this.requests.Location = new Point(632, 413);
            this.requests.Size = new Size(156, 29);
            this.requests.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.requests.Click += this.RequestsClicked;
            this.Controls.AddRange(new Control[] {
                this.heading, this.grid, this.status, this.refresh, this.close, this.reminderLabel, this.reminder, this.certifications, this.requests });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(903, 459);
            this.MinimumSize = new Size(850, 416);
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.Text = "Employee Profile Checks";
            this.Load += this.ChecksLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
        }

        private Label heading, status, reminderLabel;
        private RadDropDownList reminder;
        private RadGridView grid;
        private RadButton refresh, close, certifications, requests;
        private GridViewTextBoxColumn fieldColumn, entityColumn, actionColumn, dateColumn;
    }
}

