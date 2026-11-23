namespace Business_Suite
{
    partial class Settings
    {
        private void InitializeComponent()
        {
            heading = new Label();
            instructions = new Label();
            environmentPath = new TextBox();
            testButton = new Telerik.WinControls.UI.RadButton();
            companyLabel = new Label();
            branchLabel = new Label();
            companySelector = new Telerik.WinControls.UI.RadDropDownList();
            branchSelector = new Telerik.WinControls.UI.RadDropDownList();
            applyScopeButton = new Telerik.WinControls.UI.RadButton();
            status = new Label();
            ((System.ComponentModel.ISupportInitialize)testButton).BeginInit();
            ((System.ComponentModel.ISupportInitialize)companySelector).BeginInit();
            ((System.ComponentModel.ISupportInitialize)branchSelector).BeginInit();
            ((System.ComponentModel.ISupportInitialize)applyScopeButton).BeginInit();
            SuspendLayout();

            heading.AutoSize = true;
            heading.Font = new Font("Segoe UI", 20F);
            heading.Location = new Point(24, 22);
            heading.Name = "heading";
            heading.Text = "Database settings";

            instructions.Location = new Point(27, 78);
            instructions.Name = "instructions";
            instructions.Size = new Size(570, 50);
            instructions.Text = "Set the PostgreSQL connection and company scope in the desktop environment file. Test the connection after you save the file.";

            environmentPath.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            environmentPath.Location = new Point(27, 132);
            environmentPath.Name = "environmentPath";
            environmentPath.ReadOnly = true;
            environmentPath.Size = new Size(570, 23);
            environmentPath.AccessibleName = "Desktop environment file path";

            testButton.Location = new Point(27, 180);
            testButton.Name = "testButton";
            testButton.Size = new Size(150, 34);
            testButton.Text = "Test connection";
            testButton.Click += testButton_Click;

            companyLabel.AutoSize = true;
            companyLabel.Location = new Point(27, 235);
            companyLabel.Name = "companyLabel";
            companyLabel.Text = "Company";

            companySelector.Location = new Point(27, 258);
            companySelector.Enabled = false;
            companySelector.Name = "companySelector";
            companySelector.Size = new Size(268, 25);
            companySelector.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            companySelector.DisplayMember = "Company";
            companySelector.ValueMember = "CompanyId";
            companySelector.AccessibleName = "Company";
            companySelector.SelectedIndexChanged += companySelector_SelectedIndexChanged;

            branchLabel.AutoSize = true;
            branchLabel.Location = new Point(312, 235);
            branchLabel.Name = "branchLabel";
            branchLabel.Text = "Branch";

            branchSelector.Location = new Point(312, 258);
            branchSelector.Enabled = false;
            branchSelector.Name = "branchSelector";
            branchSelector.Size = new Size(285, 25);
            branchSelector.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            branchSelector.DisplayMember = "Name";
            branchSelector.ValueMember = "Id";
            branchSelector.AccessibleName = "Branch";

            applyScopeButton.Enabled = false;
            applyScopeButton.Location = new Point(27, 302);
            applyScopeButton.Name = "applyScopeButton";
            applyScopeButton.Size = new Size(150, 34);
            applyScopeButton.Text = "Apply";
            applyScopeButton.Click += applyScopeButton_Click;

            status.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            status.Location = new Point(27, 358);
            status.Name = "status";
            status.Size = new Size(570, 55);

            AutoScaleDimensions = new SizeF(7F, 15F);
            AutoScaleMode = AutoScaleMode.Font;
            ClientSize = new Size(624, 428);
            Controls.Add(heading);
            Controls.Add(instructions);
            Controls.Add(environmentPath);
            Controls.Add(testButton);
            Controls.Add(companyLabel);
            Controls.Add(companySelector);
            Controls.Add(branchLabel);
            Controls.Add(branchSelector);
            Controls.Add(applyScopeButton);
            Controls.Add(status);
            Font = new Font("Segoe UI", 9F);
            MinimumSize = new Size(640, 467);
            Name = "Settings";
            StartPosition = FormStartPosition.CenterParent;
            Text = "Database settings";
            Load += Settings_Load;
            FormClosed += Settings_FormClosed;
            ((System.ComponentModel.ISupportInitialize)testButton).EndInit();
            ((System.ComponentModel.ISupportInitialize)companySelector).EndInit();
            ((System.ComponentModel.ISupportInitialize)branchSelector).EndInit();
            ((System.ComponentModel.ISupportInitialize)applyScopeButton).EndInit();
            ResumeLayout(false);
            PerformLayout();
        }

        private Label heading;
        private Label instructions;
        private TextBox environmentPath;
        private Telerik.WinControls.UI.RadButton testButton;
        private Label companyLabel;
        private Label branchLabel;
        private Telerik.WinControls.UI.RadDropDownList companySelector;
        private Telerik.WinControls.UI.RadDropDownList branchSelector;
        private Telerik.WinControls.UI.RadButton applyScopeButton;
        private Label status;
    }
}
