using Telerik.WinControls.UI;

namespace Business_Suite;

partial class EmployeeDirectoryForm
{
    private void InitializeComponent()
    {
        headingLabel = new Label();
        searchBox = new RadTextBox();
        skillBox = new RadTextBox();
        teamOnlyBox = new RadCheckBox();
        searchLabel = new Label();
        skillLabel = new Label();
        searchButton = new RadButton();
        exportButton = new RadButton();
        administrationButton = new RadButton();
        myProfileRequestButton = new RadButton();
        settlementRegisterButton = new RadButton();
        exportDialog = new SaveFileDialog();
        statusLabel = new Label();
        previousButton = new RadButton();
        nextButton = new RadButton();
        employeeGrid = new RadGridView();
        var codeColumn = new GridViewTextBoxColumn();
        var nameColumn = new GridViewTextBoxColumn();
        var departmentColumn = new GridViewTextBoxColumn();
        var designationColumn = new GridViewTextBoxColumn();
        var branchColumn = new GridViewTextBoxColumn();
        var locationColumn = new GridViewTextBoxColumn();
        var statusColumn = new GridViewTextBoxColumn();
        var emailColumn = new GridViewTextBoxColumn();
        var phoneColumn = new GridViewTextBoxColumn();
        ((System.ComponentModel.ISupportInitialize)searchBox).BeginInit();
        ((System.ComponentModel.ISupportInitialize)searchButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)exportButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)administrationButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)employeeGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)employeeGrid.MasterTemplate).BeginInit();
        SuspendLayout();

        headingLabel.AutoSize = true;
        headingLabel.Font = new Font("Segoe UI Semibold", 19F);
        headingLabel.Location = new Point(24, 21);
        headingLabel.Name = "headingLabel";
        headingLabel.Text = "Employee Directory";

        searchBox.AccessibleName = "Search employees";
        searchBox.NullText = "Search name, employee ID or email";
        searchLabel.AutoSize = true;
        searchLabel.Location = new Point(27, 79);
        searchLabel.Name = "searchLabel";
        searchLabel.Text = "Search";
        searchBox.Location = new Point(85, 76);
        searchBox.Name = "searchBox";
        searchBox.Size = new Size(240, 24);
        searchButton.Location = new Point(338, 74);
        searchButton.Name = "searchButton";
        searchButton.Size = new Size(110, 26);
        searchButton.Text = "Search";
        searchButton.Click += searchButton_Click;

        exportButton.Enabled = false;
        exportButton.Location = new Point(461, 74);
        exportButton.Name = "exportButton";
        exportButton.Size = new Size(110, 26);
        exportButton.Text = "Export CSV";
        exportButton.Click += exportButton_Click;
        exportDialog.AddExtension = true;
        exportDialog.DefaultExt = "csv";
        exportDialog.FileName = "employee_directory.csv";
        exportDialog.Filter = "CSV files (*.csv)|*.csv";

        administrationButton.Location = new Point(585, 74);
        administrationButton.Name = "administrationButton";
        administrationButton.Size = new Size(170, 26);
        administrationButton.Text = "Employee administration";
        administrationButton.Click += administrationButton_Click;

        skillBox.AccessibleName = "Filter by skill";
        skillBox.NullText = "Filter by skill";
        skillLabel.AutoSize = true;
        skillLabel.Location = new Point(27, 115);
        skillLabel.Name = "skillLabel";
        skillLabel.Text = "Skill";
        skillBox.Location = new Point(85, 112);
        skillBox.Name = "skillBox";
        skillBox.Size = new Size(240, 24);
        teamOnlyBox.Location = new Point(338, 113);
        teamOnlyBox.Name = "teamOnlyBox";
        teamOnlyBox.Size = new Size(110, 22);
        teamOnlyBox.Text = "My team";

        myProfileRequestButton.Location = new Point(585, 28);
        myProfileRequestButton.Name = "myProfileRequestButton";
        myProfileRequestButton.Size = new Size(170, 28);
        myProfileRequestButton.Text = "My Change Requests";
        myProfileRequestButton.Click += myProfileRequestButton_Click;

        settlementRegisterButton.Location = new Point(408, 28);
        settlementRegisterButton.Name = "settlementRegisterButton";
        settlementRegisterButton.Size = new Size(164, 28);
        settlementRegisterButton.Text = "Final Settlements";
        settlementRegisterButton.Click += settlementRegisterButton_Click;

        codeColumn.Name = "employee_id";
        codeColumn.FieldName = "employee_id";
        codeColumn.HeaderText = "Employee ID";
        codeColumn.Width = 110;

        nameColumn.Name = "employee_name";
        nameColumn.FieldName = "employee_name";
        nameColumn.HeaderText = "Name";
        nameColumn.Width = 200;

        departmentColumn.Name = "department";
        departmentColumn.FieldName = "department";
        departmentColumn.HeaderText = "Department";
        departmentColumn.Width = 130;

        designationColumn.Name = "designation";
        designationColumn.FieldName = "designation";
        designationColumn.HeaderText = "Designation";
        designationColumn.Width = 140;

        branchColumn.Name = "branch";
        branchColumn.FieldName = "branch";
        branchColumn.HeaderText = "Branch";
        branchColumn.Width = 120;

        locationColumn.Name = "work_location";
        locationColumn.FieldName = "work_location";
        locationColumn.HeaderText = "Work location";
        locationColumn.Width = 130;

        statusColumn.Name = "status";
        statusColumn.FieldName = "status";
        statusColumn.HeaderText = "Status";
        statusColumn.Width = 92;

        emailColumn.Name = "email";
        emailColumn.FieldName = "email";
        emailColumn.HeaderText = "Email";
        emailColumn.Width = 170;

        phoneColumn.Name = "phone";
        phoneColumn.FieldName = "phone";
        phoneColumn.HeaderText = "Phone";
        phoneColumn.Width = 145;

        employeeGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        employeeGrid.Location = new Point(27, 151);
        employeeGrid.Name = "employeeGrid";
        employeeGrid.Size = new Size(922, 405);
        employeeGrid.ReadOnly = true;
        employeeGrid.MasterTemplate.AllowAddNewRow = false;
        employeeGrid.MasterTemplate.AllowDeleteRow = false;
        employeeGrid.MasterTemplate.AutoGenerateColumns = false;
        employeeGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        employeeGrid.MasterTemplate.EnableFiltering = true;
        employeeGrid.ShowGroupPanel = false;
        employeeGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[]
        {
            codeColumn, nameColumn, departmentColumn, designationColumn, branchColumn, locationColumn, statusColumn,
            emailColumn, phoneColumn
        });

        statusLabel.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        statusLabel.Location = new Point(27, 570);
        statusLabel.Name = "statusLabel";
        statusLabel.Size = new Size(715, 27);

        previousButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        previousButton.Enabled = false;
        previousButton.Location = new Point(759, 566);
        previousButton.Name = "previousButton";
        previousButton.Size = new Size(92, 28);
        previousButton.Text = "Previous";
        previousButton.Click += previousButton_Click;
        nextButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        nextButton.Enabled = false;
        nextButton.Location = new Point(857, 566);
        nextButton.Name = "nextButton";
        nextButton.Size = new Size(92, 28);
        nextButton.Text = "Next";
        nextButton.Click += nextButton_Click;

        AcceptButton = searchButton;
        AutoScaleDimensions = new SizeF(7F, 15F);
        AutoScaleMode = AutoScaleMode.Font;
        BackColor = Color.FromArgb(242, 245, 251);
        ClientSize = new Size(976, 609);
        Controls.Add(headingLabel);
        Controls.Add(searchLabel);
        Controls.Add(searchBox);
        Controls.Add(skillLabel);
        Controls.Add(skillBox);
        Controls.Add(teamOnlyBox);
        Controls.Add(searchButton);
        Controls.Add(exportButton);
        Controls.Add(administrationButton);
        Controls.Add(myProfileRequestButton);
        Controls.Add(settlementRegisterButton);
        Controls.Add(employeeGrid);
        Controls.Add(statusLabel);
        Controls.Add(previousButton);
        Controls.Add(nextButton);
        Font = new Font("Segoe UI", 9F);
        MinimumSize = new Size(780, 480);
        Name = "EmployeeDirectoryForm";
        StartPosition = FormStartPosition.CenterParent;
        Text = "Business Suite | Employee Directory";
        Load += EmployeeDirectoryForm_Load;
        FormClosed += EmployeeDirectoryForm_FormClosed;
        ((System.ComponentModel.ISupportInitialize)employeeGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)employeeGrid).EndInit();
        ((System.ComponentModel.ISupportInitialize)searchBox).EndInit();
        ((System.ComponentModel.ISupportInitialize)searchButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)exportButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)administrationButton).EndInit();
        ResumeLayout(false);
        PerformLayout();
    }

    private Label headingLabel;
    private RadTextBox searchBox;
    private RadTextBox skillBox;
    private RadCheckBox teamOnlyBox;
    private Label searchLabel;
    private Label skillLabel;
    private RadButton searchButton;
    private RadButton exportButton;
    private RadButton administrationButton;
    private RadButton myProfileRequestButton;
    private RadButton settlementRegisterButton;
    private SaveFileDialog exportDialog;
    private RadGridView employeeGrid;
    private Label statusLabel;
    private RadButton previousButton;
    private RadButton nextButton;
}
