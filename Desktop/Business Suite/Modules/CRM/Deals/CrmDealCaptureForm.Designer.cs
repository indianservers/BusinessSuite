namespace Business_Suite;

public sealed partial class CrmDealCaptureForm
{
    private Label nameBoxLabel;
    private Telerik.WinControls.UI.RadTextBox nameBox;
    private Label companyBoxLabel;
    private Telerik.WinControls.UI.RadDropDownList companyBox;
    private Label contactBoxLabel;
    private Telerik.WinControls.UI.RadDropDownList contactBox;
    private Label stageBoxLabel;
    private Telerik.WinControls.UI.RadDropDownList stageBox;
    private Label currencyBoxLabel;
    private Telerik.WinControls.UI.RadTextBox currencyBox;
    private Label amountBoxLabel;
    private Telerik.WinControls.UI.RadSpinEditor amountBox;
    private Label closeBoxLabel;
    private DateTimePicker closeBox;
    private Label sourceBoxLabel;
    private Telerik.WinControls.UI.RadTextBox sourceBox;
    private Label descriptionBoxLabel;
    private Telerik.WinControls.UI.RadTextBox descriptionBox;
    private Label duplicateBoxLabel;
    private Telerik.WinControls.UI.RadTextBox duplicateBox;
    private Label feedback;
    private Button saveButton;
    private Button cancelButton;

    private void InitializeComponent()
    {
        this.nameBoxLabel = new Label();
        this.nameBox = new Telerik.WinControls.UI.RadTextBox();
        this.companyBoxLabel = new Label();
        this.companyBox = new Telerik.WinControls.UI.RadDropDownList();
        this.contactBoxLabel = new Label();
        this.contactBox = new Telerik.WinControls.UI.RadDropDownList();
        this.stageBoxLabel = new Label();
        this.stageBox = new Telerik.WinControls.UI.RadDropDownList();
        this.currencyBoxLabel = new Label();
        this.currencyBox = new Telerik.WinControls.UI.RadTextBox();
        this.amountBoxLabel = new Label();
        this.amountBox = new Telerik.WinControls.UI.RadSpinEditor();
        this.closeBoxLabel = new Label();
        this.closeBox = new DateTimePicker();
        this.sourceBoxLabel = new Label();
        this.sourceBox = new Telerik.WinControls.UI.RadTextBox();
        this.descriptionBoxLabel = new Label();
        this.descriptionBox = new Telerik.WinControls.UI.RadTextBox();
        this.duplicateBoxLabel = new Label();
        this.duplicateBox = new Telerik.WinControls.UI.RadTextBox();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.cancelButton = new Button();
        this.SuspendLayout();

        this.nameBoxLabel.Name = "nameBoxLabel";
        this.nameBoxLabel.Text = "Deal name";
        this.nameBoxLabel.Location = new Point(18, 23);
        this.nameBoxLabel.Size = new Size(125, 23);
        this.nameBox.Name = "nameBox";
        this.nameBox.Location = new Point(151, 18);
        this.nameBox.Size = new Size(419, 28);
        this.nameBox.MaxLength = 180;
        this.Controls.Add(this.nameBoxLabel);
        this.Controls.Add(this.nameBox);

        this.companyBoxLabel.Name = "companyBoxLabel";
        this.companyBoxLabel.Text = "Company";
        this.companyBoxLabel.Location = new Point(18, 63);
        this.companyBoxLabel.Size = new Size(125, 23);
        this.companyBox.Name = "companyBox";
        this.companyBox.Location = new Point(151, 58);
        this.companyBox.Size = new Size(419, 28);
        this.companyBox.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.Controls.Add(this.companyBoxLabel);
        this.Controls.Add(this.companyBox);

        this.contactBoxLabel.Name = "contactBoxLabel";
        this.contactBoxLabel.Text = "Primary contact";
        this.contactBoxLabel.Location = new Point(18, 103);
        this.contactBoxLabel.Size = new Size(125, 23);
        this.contactBox.Name = "contactBox";
        this.contactBox.Location = new Point(151, 98);
        this.contactBox.Size = new Size(419, 28);
        this.contactBox.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.Controls.Add(this.contactBoxLabel);
        this.Controls.Add(this.contactBox);

        this.stageBoxLabel.Name = "stageBoxLabel";
        this.stageBoxLabel.Text = "Pipeline stage";
        this.stageBoxLabel.Location = new Point(18, 143);
        this.stageBoxLabel.Size = new Size(125, 23);
        this.stageBox.Name = "stageBox";
        this.stageBox.Location = new Point(151, 138);
        this.stageBox.Size = new Size(419, 28);
        this.stageBox.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.Controls.Add(this.stageBoxLabel);
        this.Controls.Add(this.stageBox);

        this.currencyBoxLabel.Name = "currencyBoxLabel";
        this.currencyBoxLabel.Text = "Currency";
        this.currencyBoxLabel.Location = new Point(18, 183);
        this.currencyBoxLabel.Size = new Size(125, 23);
        this.currencyBox.Name = "currencyBox";
        this.currencyBox.Location = new Point(151, 178);
        this.currencyBox.Size = new Size(419, 28);
        this.currencyBox.MaxLength = 3;
        this.Controls.Add(this.currencyBoxLabel);
        this.Controls.Add(this.currencyBox);

        this.amountBoxLabel.Name = "amountBoxLabel";
        this.amountBoxLabel.Text = "Amount";
        this.amountBoxLabel.Location = new Point(18, 223);
        this.amountBoxLabel.Size = new Size(125, 23);
        this.amountBox.Name = "amountBox";
        this.amountBox.Location = new Point(151, 218);
        this.amountBox.Size = new Size(419, 28);
        this.amountBox.Maximum = 9999999999.99m;
        this.amountBox.DecimalPlaces = 2;
        this.Controls.Add(this.amountBoxLabel);
        this.Controls.Add(this.amountBox);

        this.closeBoxLabel.Name = "closeBoxLabel";
        this.closeBoxLabel.Text = "Expected close";
        this.closeBoxLabel.Location = new Point(18, 263);
        this.closeBoxLabel.Size = new Size(125, 23);
        this.closeBox.Name = "closeBox";
        this.closeBox.Location = new Point(151, 258);
        this.closeBox.Size = new Size(419, 28);
        this.closeBox.Format = DateTimePickerFormat.Short;
        this.closeBox.ShowCheckBox = true;
        this.closeBox.Checked = false;
        this.Controls.Add(this.closeBoxLabel);
        this.Controls.Add(this.closeBox);

        this.sourceBoxLabel.Name = "sourceBoxLabel";
        this.sourceBoxLabel.Text = "Lead source";
        this.sourceBoxLabel.Location = new Point(18, 303);
        this.sourceBoxLabel.Size = new Size(125, 23);
        this.sourceBox.Name = "sourceBox";
        this.sourceBox.Location = new Point(151, 298);
        this.sourceBox.Size = new Size(419, 28);
        this.sourceBox.MaxLength = 80;
        this.Controls.Add(this.sourceBoxLabel);
        this.Controls.Add(this.sourceBox);

        this.descriptionBoxLabel.Name = "descriptionBoxLabel";
        this.descriptionBoxLabel.Text = "Description";
        this.descriptionBoxLabel.Location = new Point(18, 343);
        this.descriptionBoxLabel.Size = new Size(125, 23);
        this.descriptionBox.Name = "descriptionBox";
        this.descriptionBox.Location = new Point(151, 338);
        this.descriptionBox.Size = new Size(419, 69);
        this.descriptionBox.MaxLength = 10000;
        this.descriptionBox.Multiline = true;
        this.Controls.Add(this.descriptionBoxLabel);
        this.Controls.Add(this.descriptionBox);

        this.duplicateBoxLabel.Name = "duplicateBoxLabel";
        this.duplicateBoxLabel.Text = "Duplicate reason";
        this.duplicateBoxLabel.Location = new Point(18, 428);
        this.duplicateBoxLabel.Size = new Size(125, 23);
        this.duplicateBox.Name = "duplicateBox";
        this.duplicateBox.Location = new Point(151, 423);
        this.duplicateBox.Size = new Size(419, 28);
        this.duplicateBox.MaxLength = 1000;
        this.Controls.Add(this.duplicateBoxLabel);
        this.Controls.Add(this.duplicateBox);

        this.companyBox.SelectedIndexChanged += this.CompanyChanged;
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(18, 468);
        this.feedback.Size = new Size(552, 45);
        this.feedback.Text = "Loading company, contact and pipeline options…";
        this.saveButton.Name = "saveButton";
        this.saveButton.Location = new Point(366, 526);
        this.saveButton.Size = new Size(98, 34);
        this.saveButton.Text = "Create deal";
        this.saveButton.Enabled = false;
        this.saveButton.Click += this.SaveClicked;
        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Location = new Point(472, 526);
        this.cancelButton.Size = new Size(98, 34);
        this.cancelButton.Text = "Cancel";
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.Add(this.feedback);
        this.Controls.Add(this.saveButton);
        this.Controls.Add(this.cancelButton);
        this.AcceptButton = this.saveButton;
        this.CancelButton = this.cancelButton;
        this.ClientSize = new Size(590, 580);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.StartPosition = FormStartPosition.CenterParent;
        this.Text = "Quick deal capture";
        this.Shown += this.FormShown;
        this.FormClosing += this.FormIsClosing;
        this.FormClosed += this.FormIsClosed;
        this.ResumeLayout(false);
    }
}

