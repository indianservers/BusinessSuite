using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeQuickAddForm
    {
        private void InitializeComponent()
        {
            this.editor = new Panel();
            this.status = new Label();
            this.add = new RadButton();
            this.close = new RadButton();
            this.firstNameLabel = new Label();
            this.firstName = new RadTextBox();
            this.lastNameLabel = new Label();
            this.lastName = new RadTextBox();
            this.joiningLabel = new Label();
            this.joining = new RadDateTimePicker();
            this.departmentLabel = new Label();
            this.department = new RadDropDownList();
            this.employmentTypeLabel = new Label();
            this.employmentType = new RadDropDownList();
            this.emailLabel = new Label();
            this.email = new RadTextBox();
            this.SuspendLayout();
            this.firstNameLabel.Text = "First Name *";
            this.firstNameLabel.Location = new Point(10, 10);
            this.firstNameLabel.Size = new Size(248, 24);
            this.firstName.Name = "firstName";
            this.firstName.Location = new Point(10, 37);
            this.firstName.Size = new Size(248, 26);
            this.lastNameLabel.Text = "Last Name";
            this.lastNameLabel.Location = new Point(278, 10);
            this.lastNameLabel.Size = new Size(248, 24);
            this.lastName.Name = "lastName";
            this.lastName.Location = new Point(278, 37);
            this.lastName.Size = new Size(248, 26);
            this.joiningLabel.Text = "Joining Date";
            this.joiningLabel.Location = new Point(10, 72);
            this.joiningLabel.Size = new Size(248, 24);
            this.joining.Name = "joining";
            this.joining.Location = new Point(10, 99);
            this.joining.Size = new Size(248, 26);
            this.departmentLabel.Text = "Department";
            this.departmentLabel.Location = new Point(278, 72);
            this.departmentLabel.Size = new Size(248, 24);
            this.department.Name = "department";
            this.department.Location = new Point(278, 99);
            this.department.Size = new Size(248, 26);
            this.employmentTypeLabel.Text = "Employment Type";
            this.employmentTypeLabel.Location = new Point(10, 134);
            this.employmentTypeLabel.Size = new Size(248, 24);
            this.employmentType.Name = "employmentType";
            this.employmentType.Location = new Point(10, 161);
            this.employmentType.Size = new Size(248, 26);
            this.emailLabel.Text = "Personal Email";
            this.emailLabel.Location = new Point(278, 134);
            this.emailLabel.Size = new Size(248, 24);
            this.email.Name = "email";
            this.email.Location = new Point(278, 161);
            this.email.Size = new Size(248, 26);
            this.firstName.MaxLength = 80;
            this.lastName.MaxLength = 80;
            this.email.MaxLength = 150;
            this.firstName.TextChanged += this.InputChanged;
            this.joining.Format = DateTimePickerFormat.Short;
            this.department.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.employmentType.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.employmentType.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Full-time"), new RadListDataItem("Part-time"),
                new RadListDataItem("Intern"), new RadListDataItem("Contract") });
            this.employmentType.SelectedIndex = 0;
            this.editor.Name = "editor";
            this.editor.Location = new Point(12, 10);
            this.editor.Size = new Size(542, 194);
            this.editor.Enabled = false;
            this.editor.Controls.AddRange(new Control[] {
                this.firstNameLabel, this.firstName, this.lastNameLabel, this.lastName, this.joiningLabel, this.joining,
                this.departmentLabel, this.department, this.employmentTypeLabel, this.employmentType, this.emailLabel, this.email });
            this.status.Name = "status";
            this.status.Location = new Point(22, 212);
            this.status.Size = new Size(522, 44);
            this.add.Name = "add";
            this.add.Text = "Create employee";
            this.add.Location = new Point(307, 264);
            this.add.Size = new Size(142, 29);
            this.add.Enabled = false;
            this.add.Click += this.AddClicked;
            this.close.Name = "close";
            this.close.Text = "Cancel";
            this.close.Location = new Point(460, 264);
            this.close.Size = new Size(84, 29);
            this.close.DialogResult = DialogResult.Cancel;
            this.Controls.AddRange(new Control[] { this.editor, this.status, this.add, this.close });
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(565, 310);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Quick Add Employee";
            this.AcceptButton = this.add;
            this.CancelButton = this.close;
            this.Load += this.QuickAddLoaded;
            this.ResumeLayout(false);
        }

        private Panel editor;
        private Label firstNameLabel, lastNameLabel, joiningLabel, departmentLabel, employmentTypeLabel, emailLabel, status;
        private RadTextBox firstName, lastName, email;
        private RadDateTimePicker joining;
        private RadDropDownList department, employmentType;
        private RadButton add, close;
    }
}
