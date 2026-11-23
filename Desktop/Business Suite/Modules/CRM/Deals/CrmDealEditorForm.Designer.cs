#nullable disable

namespace Business_Suite;

partial class CrmDealEditorForm
{
    private void InitializeComponent()
    {
        this.heading = new Label();
        this.nameLabel = new Label();
        this.nameBox = new TextBox();
        this.priorityLabel = new Label();
        this.priorityBox = new ComboBox();
        this.stageLabel = new Label();
        this.stageBox = new ComboBox();
        this.amountBoxLabel = new Label();
        this.amountBox = new Telerik.WinControls.UI.RadSpinEditor();
        this.sourceBoxLabel = new Label();
        this.sourceBox = new Telerik.WinControls.UI.RadTextBox();
        this.expectedCloseBoxLabel = new Label();
        this.expectedCloseBox = new DateTimePicker();
        this.nextActionBoxLabel = new Label();
        this.nextActionBox = new DateTimePicker();
        this.descriptionLabel = new Label();
        this.descriptionBox = new TextBox();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.cancelButton = new Button();
        this.SuspendLayout();

        this.heading.Name = "heading";
        this.heading.Location = new Point(21, 16);
        this.heading.Size = new Size(576, 49);
        this.heading.Text = "Edit deal";
        this.heading.Font = new Font("Segoe UI Semibold", 24F);
        this.Controls.Add(this.heading);

        this.nameLabel.Name = "nameLabel";
        this.nameLabel.Location = new Point(21, 76);
        this.nameLabel.Size = new Size(576, 22);
        this.nameLabel.Text = "Deal name";
        this.Controls.Add(this.nameLabel);

        this.nameBox.Name = "nameBox";
        this.nameBox.Location = new Point(21, 101);
        this.nameBox.Size = new Size(576, 28);
        this.nameBox.MaxLength = 180;
        this.Controls.Add(this.nameBox);

        this.priorityLabel.Name = "priorityLabel";
        this.priorityLabel.Location = new Point(21, 143);
        this.priorityLabel.Size = new Size(270, 22);
        this.priorityLabel.Text = "Priority";
        this.Controls.Add(this.priorityLabel);

        this.priorityBox.Name = "priorityBox";
        this.priorityBox.Location = new Point(21, 168);
        this.priorityBox.Size = new Size(270, 28);
        this.priorityBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.priorityBox.Items.AddRange(new object[] { "Low", "Medium", "High", "Critical" });
        this.Controls.Add(this.priorityBox);

        this.stageLabel.Name = "stageLabel";
        this.stageLabel.Location = new Point(310, 143);
        this.stageLabel.Size = new Size(287, 22);
        this.stageLabel.Text = "Open pipeline stage";
        this.Controls.Add(this.stageLabel);

        this.stageBox.Name = "stageBox";
        this.stageBox.Location = new Point(310, 168);
        this.stageBox.Size = new Size(287, 28);
        this.stageBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.Controls.Add(this.stageBox);


        this.amountBoxLabel.Name = "amountBoxLabel";
        this.amountBoxLabel.Location = new Point(21, 210);
        this.amountBoxLabel.Size = new Size(270, 23);
        this.amountBoxLabel.Text = "Amount";
        this.amountBox.Name = "amountBox";
        this.amountBox.Location = new Point(21, 235);
        this.amountBox.Size = new Size(270, 28);
        this.amountBox.Maximum = 9999999999.99m;
        this.amountBox.DecimalPlaces = 2;
        this.Controls.Add(this.amountBoxLabel);
        this.Controls.Add(this.amountBox);

        this.sourceBoxLabel.Name = "sourceBoxLabel";
        this.sourceBoxLabel.Location = new Point(310, 210);
        this.sourceBoxLabel.Size = new Size(287, 23);
        this.sourceBoxLabel.Text = "Lead source";
        this.sourceBox.Name = "sourceBox";
        this.sourceBox.Location = new Point(310, 235);
        this.sourceBox.Size = new Size(287, 28);
        this.sourceBox.MaxLength = 80;
        this.Controls.Add(this.sourceBoxLabel);
        this.Controls.Add(this.sourceBox);

        this.expectedCloseBoxLabel.Name = "expectedCloseBoxLabel";
        this.expectedCloseBoxLabel.Location = new Point(21, 277);
        this.expectedCloseBoxLabel.Size = new Size(270, 23);
        this.expectedCloseBoxLabel.Text = "Expected close";
        this.expectedCloseBox.Name = "expectedCloseBox";
        this.expectedCloseBox.Location = new Point(21, 302);
        this.expectedCloseBox.Size = new Size(270, 28);
        this.expectedCloseBox.Format = DateTimePickerFormat.Short;
        this.expectedCloseBox.ShowCheckBox = true;
        this.expectedCloseBox.Checked = false;
        this.Controls.Add(this.expectedCloseBoxLabel);
        this.Controls.Add(this.expectedCloseBox);

        this.nextActionBoxLabel.Name = "nextActionBoxLabel";
        this.nextActionBoxLabel.Location = new Point(310, 277);
        this.nextActionBoxLabel.Size = new Size(287, 23);
        this.nextActionBoxLabel.Text = "Next action (local time)";
        this.nextActionBox.Name = "nextActionBox";
        this.nextActionBox.Location = new Point(310, 302);
        this.nextActionBox.Size = new Size(287, 28);
        this.nextActionBox.Format = DateTimePickerFormat.Custom;
        this.nextActionBox.CustomFormat = "dd MMM yyyy HH:mm";
        this.nextActionBox.ShowCheckBox = true;
        this.nextActionBox.Checked = false;
        this.Controls.Add(this.nextActionBoxLabel);
        this.Controls.Add(this.nextActionBox);

        this.descriptionLabel.Name = "descriptionLabel";
        this.descriptionLabel.Location = new Point(21, 344);
        this.descriptionLabel.Size = new Size(576, 22);
        this.descriptionLabel.Text = "Description";
        this.Controls.Add(this.descriptionLabel);

        this.descriptionBox.Name = "descriptionBox";
        this.descriptionBox.Location = new Point(21, 369);
        this.descriptionBox.Size = new Size(576, 102);
        this.descriptionBox.Multiline = true;
        this.descriptionBox.MaxLength = 10000;
        this.descriptionBox.ScrollBars = ScrollBars.Vertical;
        this.Controls.Add(this.descriptionBox);

        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(21, 486);
        this.feedback.Size = new Size(576, 58);
        this.feedback.Text = "Loading the deal…";
        this.Controls.Add(this.feedback);

        this.saveButton.Name = "saveButton";
        this.saveButton.Location = new Point(398, 553);
        this.saveButton.Size = new Size(97, 35);
        this.saveButton.Text = "Save";
        this.saveButton.Enabled = false;
        this.saveButton.Click += this.SaveClicked;
        this.Controls.Add(this.saveButton);

        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Location = new Point(504, 553);
        this.cancelButton.Size = new Size(93, 35);
        this.cancelButton.Text = "Cancel";
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.Add(this.cancelButton);
        this.Text = "Business Suite | Edit deal";
        this.Name = "CrmDealEditorForm";
        this.ClientSize = new Size(620, 608);
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
        this.Shown += this.EditorShown;
        this.FormClosed += this.EditorClosed;
        this.FormClosing += this.EditorClosing;
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label heading;
    private Label nameLabel;
    private TextBox nameBox;
    private Label priorityLabel;
    private ComboBox priorityBox;
    private Label stageLabel;
    private ComboBox stageBox;
    private Label amountBoxLabel;
    private Telerik.WinControls.UI.RadSpinEditor amountBox;
    private Label sourceBoxLabel;
    private Telerik.WinControls.UI.RadTextBox sourceBox;
    private Label expectedCloseBoxLabel;
    private DateTimePicker expectedCloseBox;
    private Label nextActionBoxLabel;
    private DateTimePicker nextActionBox;
    private Label descriptionLabel;
    private TextBox descriptionBox;
    private Label feedback;
    private Button saveButton;
    private Button cancelButton;
}
