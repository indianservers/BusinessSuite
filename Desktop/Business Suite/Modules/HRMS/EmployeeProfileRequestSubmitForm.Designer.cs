using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeProfileRequestSubmitForm
    {
        private void InitializeComponent()
        {
            this.editor = new Panel();
            this.heading = new Label();
            this.status = new Label();
            this.submit = new RadButton();
            this.refresh = new RadButton();
            this.close = new RadButton();
            this.fieldLabel = new Label();
            this.field = new RadDropDownList();
            this.currentLabel = new Label();
            this.current = new RadTextBox();
            this.proposedLabel = new Label();
            this.proposed = new RadTextBox();
            this.reasonLabel = new Label();
            this.reason = new RadTextBox();
            this.SuspendLayout();
            this.fieldLabel.Text = "Field";
            this.fieldLabel.Location = new Point(10, 10);
            this.fieldLabel.Size = new Size(248, 24);
            this.field.Name = "field";
            this.field.Location = new Point(10, 37);
            this.field.Size = new Size(248, 26);
            this.currentLabel.Text = "Current Value";
            this.currentLabel.Location = new Point(278, 10);
            this.currentLabel.Size = new Size(248, 24);
            this.current.Name = "current";
            this.current.Location = new Point(278, 37);
            this.current.Size = new Size(248, 26);
            this.proposedLabel.Text = "Requested Value";
            this.proposedLabel.Location = new Point(10, 72);
            this.proposedLabel.Size = new Size(248, 24);
            this.proposed.Name = "proposed";
            this.proposed.Location = new Point(10, 99);
            this.proposed.Size = new Size(248, 26);
            this.reasonLabel.Text = "Reason";
            this.reasonLabel.Location = new Point(278, 72);
            this.reasonLabel.Size = new Size(248, 24);
            this.reason.Name = "reason";
            this.reason.Location = new Point(278, 99);
            this.reason.Size = new Size(248, 26);
            this.heading.Name = "heading";
            this.heading.Location = new Point(22, 13);
            this.heading.Size = new Size(478, 26);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);
            this.current.ReadOnly = true;
            this.proposed.MaxLength = 200;
            this.reason.MaxLength = 1000;
            this.field.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.field.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Present city") { Value = "present_city" },
                new RadListDataItem("Present state") { Value = "present_state" },
                new RadListDataItem("Present postal code") { Value = "present_pincode" },
                new RadListDataItem("Permanent city") { Value = "permanent_city" },
                new RadListDataItem("Permanent state") { Value = "permanent_state" },
                new RadListDataItem("Permanent postal code") { Value = "permanent_pincode" },
                new RadListDataItem("Emergency contact relationship") { Value = "emergency_contact_relation" } });
            this.field.TextChanged += this.FieldChanged;
            this.editor.Name = "editor";
            this.editor.Location = new Point(12, 43);
            this.editor.Size = new Size(542, 139);
            this.editor.Enabled = false;
            this.editor.Controls.AddRange(new Control[] {
                this.fieldLabel, this.field, this.currentLabel, this.current,
                this.proposedLabel, this.proposed, this.reasonLabel, this.reason });
            this.status.Name = "status";
            this.status.Location = new Point(22, 193);
            this.status.Size = new Size(522, 44);
            this.refresh.Name = "refresh";
            this.refresh.Text = "Reload profile";
            this.refresh.Location = new Point(22, 246);
            this.refresh.Size = new Size(115, 29);
            this.refresh.Click += this.RefreshClicked;
            this.submit.Name = "submit";
            this.submit.Text = "Submit request";
            this.submit.Location = new Point(307, 246);
            this.submit.Size = new Size(142, 29);
            this.submit.Enabled = false;
            this.submit.Click += this.SubmitClicked;
            this.close.Name = "close";
            this.close.Text = "Cancel";
            this.close.Location = new Point(460, 246);
            this.close.Size = new Size(84, 29);
            this.close.DialogResult = DialogResult.Cancel;
            this.Controls.AddRange(new Control[] { this.heading, this.editor, this.status, this.refresh, this.submit, this.close });
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(565, 292);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Request Profile Change";
            this.AcceptButton = this.submit;
            this.CancelButton = this.close;
            this.Load += this.SubmitLoaded;
            this.ResumeLayout(false);
        }

        private Panel editor;
        private Label heading, fieldLabel, currentLabel, proposedLabel, reasonLabel, status;
        private RadTextBox current, proposed, reason;
        private RadDropDownList field;
        private RadButton refresh, submit, close;
    }
}
