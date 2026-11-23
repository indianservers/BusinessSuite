#nullable disable

namespace Business_Suite;

partial class CrmDealCloseForm
{
    private void InitializeComponent()
    {
        this.heading = new Label();
        this.outcomeLabel = new Label();
        this.outcomeBox = new ComboBox();
        this.dateLabel = new Label();
        this.businessDate = new DateTimePicker();
        this.valueLabel = new Label();
        this.finalValue = new NumericUpDown();
        this.currencyLabel = new Label();
        this.reasonLabel = new Label();
        this.quoteLabel = new Label();
        this.quoteBox = new ComboBox();
        this.reasonBox = new TextBox();
        this.contractLabel = new Label();
        this.contractBox = new TextBox();
        this.competitorLabel = new Label();
        this.competitorBox = new TextBox();
        this.handoverLabel = new Label();
        this.handoverBox = new TextBox();
        this.onboardingBox = new CheckBox();
        this.reengagementDate = new DateTimePicker();
        this.reengagementLabel = new Label();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.cancelButton = new Button();
        this.SuspendLayout();

        this.heading.Name = "heading";
        this.heading.Location = new Point(21, 16);
        this.heading.Size = new Size(578, 49);
        this.heading.Text = "Close deal";
        this.heading.Font = new Font("Segoe UI Semibold", 24F);
        this.Controls.Add(this.heading);

        this.outcomeLabel.Name = "outcomeLabel";
        this.outcomeLabel.Location = new Point(21, 72);
        this.outcomeLabel.Size = new Size(155, 22);
        this.outcomeLabel.Text = "Outcome";
        this.Controls.Add(this.outcomeLabel);

        this.outcomeBox.Name = "outcomeBox";
        this.outcomeBox.Location = new Point(21, 97);
        this.outcomeBox.Size = new Size(156, 28);
        this.outcomeBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.outcomeBox.Items.AddRange(new object[] { "Won", "Lost" });
        this.outcomeBox.SelectedIndexChanged += this.OutcomeChanged;
        this.Controls.Add(this.outcomeBox);

        this.dateLabel.Name = "dateLabel";
        this.dateLabel.Location = new Point(191, 72);
        this.dateLabel.Size = new Size(170, 22);
        this.dateLabel.Text = "Actual closing date";
        this.Controls.Add(this.dateLabel);

        this.businessDate.Name = "businessDate";
        this.businessDate.Location = new Point(191, 97);
        this.businessDate.Size = new Size(170, 28);
        this.businessDate.Format = DateTimePickerFormat.Short;
        this.Controls.Add(this.businessDate);

        this.valueLabel.Name = "valueLabel";
        this.valueLabel.Location = new Point(375, 72);
        this.valueLabel.Size = new Size(226, 22);
        this.valueLabel.Text = "Final deal value";
        this.Controls.Add(this.valueLabel);

        this.finalValue.Name = "finalValue";
        this.finalValue.Location = new Point(375, 97);
        this.finalValue.Size = new Size(156, 28);
        this.finalValue.Maximum = 9999999999m;
        this.finalValue.DecimalPlaces = 2;
        this.finalValue.ThousandsSeparator = true;
        this.Controls.Add(this.finalValue);

        this.currencyLabel.Name = "currencyLabel";
        this.currencyLabel.Location = new Point(540, 101);
        this.currencyLabel.Size = new Size(62, 20);
        this.Controls.Add(this.currencyLabel);

        this.quoteLabel.Name = "quoteLabel";
        this.quoteLabel.Location = new Point(21, 141);
        this.quoteLabel.Size = new Size(576, 22);
        this.quoteLabel.Text = "Approved quotation";
        this.Controls.Add(this.quoteLabel);

        this.quoteBox.Name = "quoteBox";
        this.quoteBox.Location = new Point(21, 165);
        this.quoteBox.Size = new Size(576, 28);
        this.quoteBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.quoteBox.Enabled = false;
        this.quoteBox.SelectedIndexChanged += this.OutcomeChanged;
        this.Controls.Add(this.quoteBox);

        this.reasonLabel.Name = "reasonLabel";
        this.reasonLabel.Location = new Point(21, 207);
        this.reasonLabel.Size = new Size(576, 22);
        this.reasonLabel.Text = "Closing reason";
        this.Controls.Add(this.reasonLabel);

        this.reasonBox.Name = "reasonBox";
        this.reasonBox.Location = new Point(21, 231);
        this.reasonBox.Size = new Size(576, 76);
        this.reasonBox.MaxLength = 2000;
        this.reasonBox.Multiline = true;
        this.reasonBox.ScrollBars = ScrollBars.Vertical;
        this.Controls.Add(this.reasonBox);

        this.contractLabel.Name = "contractLabel";
        this.contractLabel.Location = new Point(21, 321);
        this.contractLabel.Size = new Size(274, 22);
        this.contractLabel.Text = "Contract reference";
        this.Controls.Add(this.contractLabel);

        this.contractBox.Name = "contractBox";
        this.contractBox.Location = new Point(21, 344);
        this.contractBox.Size = new Size(274, 28);
        this.contractBox.MaxLength = 180;
        this.Controls.Add(this.contractBox);

        this.competitorLabel.Name = "competitorLabel";
        this.competitorLabel.Location = new Point(312, 321);
        this.competitorLabel.Size = new Size(285, 22);
        this.competitorLabel.Text = "Competitor";
        this.Controls.Add(this.competitorLabel);

        this.competitorBox.Name = "competitorBox";
        this.competitorBox.Location = new Point(312, 344);
        this.competitorBox.Size = new Size(285, 28);
        this.competitorBox.MaxLength = 180;
        this.Controls.Add(this.competitorBox);

        this.handoverLabel.Name = "handoverLabel";
        this.handoverLabel.Location = new Point(21, 386);
        this.handoverLabel.Size = new Size(576, 22);
        this.handoverLabel.Text = "Handover notes";
        this.Controls.Add(this.handoverLabel);

        this.handoverBox.Name = "handoverBox";
        this.handoverBox.Location = new Point(21, 410);
        this.handoverBox.Size = new Size(576, 92);
        this.handoverBox.MaxLength = 4000;
        this.handoverBox.Multiline = true;
        this.handoverBox.ScrollBars = ScrollBars.Vertical;
        this.Controls.Add(this.handoverBox);

        this.onboardingBox.Name = "onboardingBox";
        this.onboardingBox.Location = new Point(21, 507);
        this.onboardingBox.Size = new Size(300, 29);
        this.onboardingBox.Text = "Create customer onboarding task";
        this.onboardingBox.Enabled = false;
        this.Controls.Add(this.onboardingBox);

        this.reengagementLabel.Name = "reengagementLabel";
        this.reengagementLabel.Location = new Point(21, 513);
        this.reengagementLabel.Size = new Size(165, 22);
        this.reengagementLabel.Text = "Re-engagement date";
        this.reengagementLabel.Visible = false;
        this.Controls.Add(this.reengagementLabel);

        this.reengagementDate.Name = "reengagementDate";
        this.reengagementDate.Location = new Point(191, 507);
        this.reengagementDate.Size = new Size(175, 28);
        this.reengagementDate.Format = DateTimePickerFormat.Short;
        this.reengagementDate.ShowCheckBox = true;
        this.reengagementDate.Checked = false;
        this.reengagementDate.AccessibleName = "Re-engagement date";
        this.reengagementDate.Visible = false;
        this.Controls.Add(this.reengagementDate);

        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(21, 549);
        this.feedback.Size = new Size(576, 50);
        this.feedback.Text = "Loading the deal…";
        this.Controls.Add(this.feedback);

        this.saveButton.Name = "saveButton";
        this.saveButton.Location = new Point(374, 610);
        this.saveButton.Size = new Size(121, 35);
        this.saveButton.Text = "Close deal";
        this.saveButton.Enabled = false;
        this.saveButton.Click += this.SaveClicked;
        this.Controls.Add(this.saveButton);

        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Location = new Point(505, 610);
        this.cancelButton.Size = new Size(92, 35);
        this.cancelButton.Text = "Cancel";
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.Add(this.cancelButton);
        this.Text = "Business Suite | Close deal";
        this.Name = "CrmDealCloseForm";
        this.ClientSize = new Size(620, 666);
        this.StartPosition = FormStartPosition.CenterParent;
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.Font = new Font("Segoe UI", 10F);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.AcceptButton = this.saveButton;
        this.CancelButton = this.cancelButton;
        this.Shown += this.ClosingShown;
        this.FormClosed += this.ClosedForm;
        this.FormClosing += this.ClosingForm;
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label heading;
    private Label outcomeLabel;
    private ComboBox outcomeBox;
    private Label dateLabel;
    private DateTimePicker businessDate;
    private Label valueLabel;
    private NumericUpDown finalValue;
    private Label currencyLabel;
    private Label reasonLabel;
    private Label quoteLabel;
    private ComboBox quoteBox;
    private TextBox reasonBox;
    private Label contractLabel;
    private TextBox contractBox;
    private Label competitorLabel;
    private TextBox competitorBox;
    private Label handoverLabel;
    private TextBox handoverBox;
    private CheckBox onboardingBox;
    private DateTimePicker reengagementDate;
    private Label reengagementLabel;
    private Label feedback;
    private Button saveButton;
    private Button cancelButton;
}
