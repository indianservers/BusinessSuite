using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CommunicationEmailConsentForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        addressLabel = new Label { Name = "addressLabel", Text = "Customer email", Location = new Point(20, 16), Size = new Size(481, 23),
            Font = new Font("Segoe UI Semibold", 11F), AutoEllipsis = true };
        statusLabel = new Label { Name = "statusLabel", Location = new Point(20, 46), Size = new Size(660, 22) };
        refreshButton = new RadButton { Name = "refreshButton", Text = "Refresh", Location = new Point(565, 15), Size = new Size(115, 27) };
        refreshButton.Click += RefreshClicked;
        grid = new RadGridView { Name = "grid", Location = new Point(20, 76), Size = new Size(660, 219),
            ReadOnly = true, AccessibleName = "Linked email consent history", ShowGroupPanel = false };
        grid.MasterTemplate.AutoGenerateColumns = false;
        grid.MasterTemplate.AllowAddNewRow = false;
        grid.MasterTemplate.AllowDeleteRow = false;
        grid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewDateTimeColumn { Name = "recordedColumn", FieldName = "Recorded", HeaderText = "Recorded",
                Width = 152, FormatString = "{0:g}" },
            new GridViewTextBoxColumn { Name = "choiceColumn", FieldName = "Choice", HeaderText = "Customer choice", Width = 134 },
            new GridViewTextBoxColumn { Name = "evidenceColumn", FieldName = "Source", HeaderText = "Source or evidence", Width = 355 }
        });
        choiceLabel = new Label { Name = "choiceLabel", Text = "Customer choice", Location = new Point(20, 311), Size = new Size(140, 24) };
        choiceBox = new RadDropDownList { Name = "choiceBox", Location = new Point(164, 307), Size = new Size(174, 27),
            Enabled = false, DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList, AccessibleName = "Customer choice" };
        choiceBox.Items.Add(new RadListDataItem("Opted in"));
        choiceBox.Items.Add(new RadListDataItem("Opted out"));
        choiceBox.Items.Add(new RadListDataItem("Unsubscribed"));
        choiceBox.Items.Add(new RadListDataItem("Block email to address"));
        choiceBox.SelectedIndexChanged += InputChanged;
        evidenceLabel = new Label { Name = "evidenceLabel", Text = "Source or evidence", Location = new Point(20, 354), Size = new Size(140, 24) };
        evidenceBox = new RadTextBox { Name = "evidenceBox", Location = new Point(164, 350), Size = new Size(516, 27),
            MaxLength = 120, AccessibleName = "Source or consent evidence", Enabled = false };
        evidenceBox.TextChanged += InputChanged;
        feedback = new Label { Name = "feedback", Location = new Point(20, 391), Size = new Size(660, 56) };
        confirmButton = new RadButton { Name = "confirmButton", Text = "Review customer choice", Location = new Point(377, 451),
            Size = new Size(181, 29), Enabled = false };
        confirmButton.Click += ConfirmClicked;
        closeButton = new RadButton { Name = "closeButton", Text = "Close", Location = new Point(569, 451),
            Size = new Size(111, 29), DialogResult = DialogResult.Cancel };
        Controls.AddRange(new Control[] { addressLabel, statusLabel, refreshButton, grid, choiceLabel, choiceBox,
            evidenceLabel, evidenceBox, feedback, confirmButton, closeButton });
        CancelButton = closeButton;
        AutoScaleMode = AutoScaleMode.Font;
        AutoScaleDimensions = new SizeF(7F, 15F);
        Font = new Font("Segoe UI", 9F);
        ClientSize = new Size(700, 495);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition = FormStartPosition.CenterParent;
        ShowInTaskbar = MaximizeBox = MinimizeBox = false;
        Name = "CommunicationEmailConsentForm";
        Text = "Email consent history";
        Shown += RefreshClicked;
        FormClosing += ConsentClosing;
        ResumeLayout(false);
        PerformLayout();
    }

    private Label addressLabel, statusLabel, choiceLabel, evidenceLabel, feedback;
    private RadGridView grid;
    private RadDropDownList choiceBox;
    private RadTextBox evidenceBox;
    private RadButton refreshButton, confirmButton, closeButton;
}
