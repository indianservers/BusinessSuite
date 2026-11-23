using Telerik.WinControls.UI;

namespace Business_Suite;

partial class AppointmentMessageForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        channelLabel = new Label { Name = "channelLabel", Text = "Message channel", Location = new Point(20, 24), Size = new Size(114, 24) };
        channelBox = new RadDropDownList { Name = "channelBox", Location = new Point(142, 20), Size = new Size(170, 28),
            DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList, AccessibleName = "Message channel", Enabled = false };
        channelBox.Items.Add(new RadListDataItem("Email"));
        channelBox.Items.Add(new RadListDataItem("SMS"));
        channelBox.SelectedIndexChanged += ChannelChanged;
        refreshButton = new RadButton { Name = "refreshButton", Text = "Refresh booking", Location = new Point(525, 20), Size = new Size(155, 28) };
        refreshButton.Click += RefreshClicked;
        recipientLabel = new Label { Name = "recipientLabel", Text = "Recipient", Location = new Point(20, 63), Size = new Size(114, 24) };
        recipientBox = new RadTextBox { Name = "recipientBox", Location = new Point(142, 60), Size = new Size(538, 28),
            MaxLength = 320, AccessibleName = "Confirmation recipient", Enabled = false };
        recipientBox.TextChanged += DraftChanged;
        messageLabel = new Label { Name = "messageLabel", Text = "Confirmation text", Location = new Point(20, 103), Size = new Size(164, 24) };
        messageBox = new RadTextBox { Name = "messageBox", Location = new Point(20, 130), Size = new Size(660, 150),
            Multiline = true, ScrollBars = ScrollBars.Vertical, MaxLength = 8000, AccessibleName = "Confirmation text", Enabled = false };
        messageBox.TextChanged += DraftChanged;
        counter = new Label { Name = "counter", Location = new Point(20, 288), Size = new Size(660, 22) };
        guidance = new Label { Name = "guidance", Location = new Point(20, 313), Size = new Size(660, 25) };
        latestLabel = new Label { Name = "latestLabel", Text = "Latest booking text", Location = new Point(20, 343), Size = new Size(660, 23) };
        latestText = new RadTextBox { Name = "latestText", Location = new Point(20, 370), Size = new Size(660, 84),
            Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, AccessibleName = "Latest booking text" };
        resetButton = new RadButton { Name = "resetButton", Text = "Reset generated message", Location = new Point(20, 468),
            Size = new Size(172, 29), Enabled = false };
        resetButton.Click += ResetClicked;
        reviewButton = new RadButton { Name = "reviewButton", Text = "I reviewed my message", Location = new Point(202, 468),
            Size = new Size(164, 29), Enabled = false };
        reviewButton.Click += ReviewedClicked;
        copyButton = new RadButton { Name = "copyButton", Text = "Copy message text", Location = new Point(376, 468),
            Size = new Size(144, 29), Enabled = false };
        copyButton.Click += CopyClicked;
        openButton = new RadButton { Name = "openButton", Text = "Open email draft", Location = new Point(530, 468),
            Size = new Size(150, 29), Enabled = false };
        openButton.Click += OpenClicked;
        feedback = new Label { Name = "feedback", Location = new Point(20, 509), Size = new Size(660, 42) };
        Controls.AddRange(new Control[] { channelLabel, channelBox, refreshButton, recipientLabel, recipientBox,
            messageLabel, messageBox, counter, guidance, latestLabel, latestText, resetButton, reviewButton,
            copyButton, openButton, feedback });
        AutoScaleDimensions = new SizeF(7F, 15F);
        AutoScaleMode = AutoScaleMode.Font;
        ClientSize = new Size(700, 558);
        Font = new Font("Segoe UI", 9F);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        Name = "AppointmentMessageForm";
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.CenterParent;
        Text = "Confirmation preview";
        Shown += RefreshClicked;
        FormClosed += WindowClosed;
        ResumeLayout(false);
        PerformLayout();
    }

    private Label channelLabel;
    private RadDropDownList channelBox;
    private RadButton refreshButton;
    private Label recipientLabel;
    private RadTextBox recipientBox;
    private Label messageLabel;
    private RadTextBox messageBox;
    private Label counter;
    private Label guidance;
    private Label latestLabel;
    private RadTextBox latestText;
    private RadButton resetButton;
    private RadButton reviewButton;
    private RadButton copyButton;
    private RadButton openButton;
    private Label feedback;
}
