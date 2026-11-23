namespace Business_Suite;

public sealed partial class LeadSalesSetupForm
{
    private Label description = null!;
    private Label managerLabel = null!;
    private Label ownerLabel = null!;
    private ComboBox managerBox = null!;
    private CheckedListBox ownerList = null!;
    private Label feedback = null!;
    private Button saveButton = null!;
    private Button closeButton = null!;

    private void InitializeComponent()
    {
        this.description = new Label();
        this.managerLabel = new Label();
        this.ownerLabel = new Label();
        this.managerBox = new ComboBox();
        this.ownerList = new CheckedListBox();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.closeButton = new Button();
        this.SuspendLayout();
        this.description.Location = new Point(17, 16);
        this.description.Size = new Size(515, 63);
        this.description.Text = "Assign new Leads in rotation. The process sets a 24-hour first-response threshold and a seven-day inactivity threshold.";
        this.managerLabel.Location = new Point(17, 82);
        this.managerLabel.Size = new Size(300, 23);
        this.managerLabel.Text = "Sales manager";
        this.managerBox.Name = "managerBox";
        this.managerBox.Location = new Point(17, 107);
        this.managerBox.Size = new Size(515, 28);
        this.managerBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.managerBox.DisplayMember = "Name";
        this.managerBox.Enabled = false;
        this.ownerLabel.Location = new Point(17, 148);
        this.ownerLabel.Size = new Size(300, 23);
        this.ownerLabel.Text = "Assignment pool";
        this.ownerList.Name = "ownerList";
        this.ownerList.Location = new Point(17, 176);
        this.ownerList.Size = new Size(515, 150);
        this.ownerList.DisplayMember = "Name";
        this.ownerList.CheckOnClick = true;
        this.ownerList.Enabled = false;
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(17, 341);
        this.feedback.Size = new Size(515, 48);
        this.feedback.Text = "Loading sales process settings…";
        this.saveButton.Name = "saveButton";
        this.saveButton.Location = new Point(310, 400);
        this.saveButton.Size = new Size(129, 33);
        this.saveButton.Text = "Save sales process";
        this.saveButton.Enabled = false;
        this.saveButton.Click += this.SaveClicked;
        this.closeButton.Location = new Point(447, 400);
        this.closeButton.Size = new Size(85, 33);
        this.closeButton.Text = "Close";
        this.closeButton.DialogResult = DialogResult.Cancel;
        this.Controls.AddRange(new Control[] {this.description,this.managerLabel,this.managerBox,this.ownerLabel,
            this.ownerList,this.feedback,this.saveButton,this.closeButton});
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(549, 450);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.StartPosition = FormStartPosition.CenterParent;
        this.Name = "LeadSalesSetupForm";
        this.Text = "Lead sales process";
        this.CancelButton = this.closeButton;
        this.Shown += this.FormShownHandler;
        this.FormClosing += this.ClosingHandler;
        this.FormClosed += this.ClosedHandler;
        this.ResumeLayout(false);
    }
}
