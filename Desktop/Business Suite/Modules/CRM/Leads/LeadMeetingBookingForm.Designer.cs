using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class LeadMeetingBookingForm
{
    private void InitializeComponent()
    {
        this.purposeLabel = new Label();
        this.purposeBox = new ComboBox();
        this.timeLabel = new Label();
        this.timePicker = new RadDateTimePicker();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.cancelButton = new Button();
        this.SuspendLayout();
        this.purposeLabel.Location = new Point(18, 16);
        this.purposeLabel.Size = new Size(411, 24);
        this.purposeLabel.Text = "Meeting type";
        this.purposeBox.Name = "purposeBox";
        this.purposeBox.Location = new Point(18, 43);
        this.purposeBox.Size = new Size(411, 28);
        this.purposeBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.purposeBox.Items.AddRange(new object[] { "Consultation", "Product demo" });
        this.timeLabel.Location = new Point(18, 83);
        this.timeLabel.Size = new Size(411, 25);
        this.timeLabel.Text = "Start (UTC, 30 minutes)";
        this.timePicker.Name = "timePicker";
        this.timePicker.Location = new Point(18, 113);
        this.timePicker.Size = new Size(411, 28);
        this.timePicker.Format = DateTimePickerFormat.Custom;
        this.timePicker.CustomFormat = "yyyy-MM-dd HH:mm";
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(18, 151);
        this.feedback.Size = new Size(411, 42);
        this.saveButton.Name = "saveButton";
        this.saveButton.Location = new Point(205, 200);
        this.saveButton.Size = new Size(110, 35);
        this.saveButton.Text = "Book meeting";
        this.saveButton.Click += this.SaveClicked;
        this.cancelButton.Location = new Point(325, 200);
        this.cancelButton.Size = new Size(104, 35);
        this.cancelButton.Text = "Cancel";
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.AddRange(new Control[] { this.purposeLabel, this.purposeBox, this.timeLabel, this.timePicker,
            this.feedback, this.saveButton, this.cancelButton });
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(447, 253);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.StartPosition = FormStartPosition.CenterParent;
        this.AcceptButton = this.saveButton;
        this.CancelButton = this.cancelButton;
        this.Text = "Book Lead meeting";
        this.FormClosed += this.FormIsClosed;
        this.ResumeLayout(false);
    }

    private Label purposeLabel;
    private ComboBox purposeBox;
    private Label timeLabel;
    private RadDateTimePicker timePicker;
    private Label feedback;
    private Button saveButton;
    private Button cancelButton;
}
