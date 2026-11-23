#nullable disable
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class AppointmentEditorForm
{
    private void InitializeComponent()
    {
        this.heading = new Label();
        this.customerLabel = new Label();
        this.customerBox = new ComboBox();
        this.serviceLabel = new Label();
        this.serviceBox = new ComboBox();
        this.providerLabel = new Label();
        this.providerBox = new ComboBox();
        this.timezoneLabel = new Label();
        this.startsLabel = new Label();
        this.startsPicker = new DateTimePicker();
        this.durationLabel = new Label();
        this.durationBox = new NumericUpDown();
        this.resourcesLabel = new Label();
        this.resourceList = new CheckedListBox();
        this.notesLabel = new Label();
        this.notesBox = new TextBox();
        this.customerNotesLabel = new Label();
        this.customerNotesBox = new TextBox();
        this.walkInBox = new CheckBox();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.checkButton = new Button();
        this.customerContextButton = new Telerik.WinControls.UI.RadButton();
        this.slotPickerButton = new Telerik.WinControls.UI.RadButton();
        this.cancelButton = new Button();
        this.SuspendLayout();

        this.heading.Name = "heading";
        this.heading.Location = new Point(23, 18);
        this.heading.Size = new Size(435, 45);
        this.heading.Text = "New appointment";
        this.heading.Font = new Font("Segoe UI Semibold", 23F);
        this.Controls.Add(this.heading);
        this.slotPickerButton.Name = "slotPickerButton";
        this.slotPickerButton.Location = new Point(484, 26);
        this.slotPickerButton.Size = new Size(172, 28);
        this.slotPickerButton.Text = "Browse provider times";
        this.slotPickerButton.Enabled = false;
        this.slotPickerButton.Click += this.SlotPickerClicked;
        this.Controls.Add(this.slotPickerButton);

        this.customerLabel.Name = "customerLabel";
        this.customerLabel.Location = new Point(23, 75);
        this.customerLabel.Size = new Size(300, 21);
        this.customerLabel.Text = "Customer";
        this.Controls.Add(this.customerLabel);

        this.customerBox.Name = "customerBox";
        this.customerBox.Location = new Point(23, 98);
        this.customerBox.Size = new Size(305, 28);
        this.customerBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.customerBox.SelectedIndexChanged += this.CustomerSelectionChanged;
        this.Controls.Add(this.customerBox);

        this.serviceLabel.Name = "serviceLabel";
        this.serviceLabel.Location = new Point(351, 75);
        this.serviceLabel.Size = new Size(300, 21);
        this.serviceLabel.Text = "Catalog service";
        this.Controls.Add(this.serviceLabel);

        this.serviceBox.Name = "serviceBox";
        this.serviceBox.Location = new Point(351, 98);
        this.serviceBox.Size = new Size(305, 28);
        this.serviceBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.serviceBox.SelectedIndexChanged += this.ServiceChanged;
        this.Controls.Add(this.serviceBox);

        this.providerLabel.Name = "providerLabel";
        this.providerLabel.Location = new Point(23, 142);
        this.providerLabel.Size = new Size(300, 21);
        this.providerLabel.Text = "Provider";
        this.Controls.Add(this.providerLabel);

        this.providerBox.Name = "providerBox";
        this.providerBox.Location = new Point(23, 165);
        this.providerBox.Size = new Size(305, 28);
        this.providerBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.providerBox.SelectedIndexChanged += this.ProviderChanged;
        this.Controls.Add(this.providerBox);

        this.timezoneLabel.Name = "timezoneLabel";
        this.timezoneLabel.Location = new Point(351, 169);
        this.timezoneLabel.Size = new Size(305, 21);
        this.timezoneLabel.Text = "Choose a provider";
        this.Controls.Add(this.timezoneLabel);

        this.startsLabel.Name = "startsLabel";
        this.startsLabel.Location = new Point(23, 204);
        this.startsLabel.Size = new Size(307, 21);
        this.startsLabel.Text = "Start time in provider timezone";
        this.Controls.Add(this.startsLabel);

        this.startsPicker.Name = "startsPicker";
        this.startsPicker.ValueChanged += this.StartsEdited;
        this.startsPicker.Location = new Point(23, 227);
        this.startsPicker.Size = new Size(307, 28);
        this.startsPicker.CustomFormat = "ddd, dd MMM yyyy  HH:mm";
        this.startsPicker.Format = DateTimePickerFormat.Custom;
        this.Controls.Add(this.startsPicker);

        this.durationLabel.Name = "durationLabel";
        this.durationLabel.Location = new Point(351, 204);
        this.durationLabel.Size = new Size(305, 21);
        this.durationLabel.Text = "Duration (minutes)";
        this.Controls.Add(this.durationLabel);

        this.durationBox.Name = "durationBox";
        this.durationBox.Location = new Point(351, 227);
        this.durationBox.Size = new Size(156, 28);
        this.durationBox.Minimum = 5;
        this.durationBox.Maximum = 720;
        this.durationBox.Value = 30;
        this.Controls.Add(this.durationBox);

        this.resourcesLabel.Name = "resourcesLabel";
        this.resourcesLabel.Location = new Point(23, 269);
        this.resourcesLabel.Size = new Size(300, 21);
        this.resourcesLabel.Text = "Additional resources";
        this.Controls.Add(this.resourcesLabel);

        this.resourceList.Name = "resourceList";
        this.resourceList.Location = new Point(23, 292);
        this.resourceList.Size = new Size(305, 102);
        this.resourceList.CheckOnClick = true;
        this.Controls.Add(this.resourceList);

        this.notesLabel.Name = "notesLabel";
        this.notesLabel.Location = new Point(351, 269);
        this.notesLabel.Size = new Size(301, 21);
        this.notesLabel.Text = "Internal notes";
        this.Controls.Add(this.notesLabel);

        this.notesBox.Name = "notesBox";
        this.notesBox.Location = new Point(351, 292);
        this.notesBox.Size = new Size(305, 102);
        this.notesBox.Multiline = true;
        this.notesBox.MaxLength = 4000;
        this.notesBox.ScrollBars = ScrollBars.Vertical;
        this.Controls.Add(this.notesBox);

        this.customerNotesLabel.Name = "customerNotesLabel";
        this.customerNotesLabel.Location = new Point(23, 410);
        this.customerNotesLabel.Size = new Size(305, 21);
        this.customerNotesLabel.Text = "Customer notes";
        this.Controls.Add(this.customerNotesLabel);

        this.customerNotesBox.Name = "customerNotesBox";
        this.customerNotesBox.Location = new Point(23, 435);
        this.customerNotesBox.Size = new Size(305, 72);
        this.customerNotesBox.MaxLength = 4000;
        this.customerNotesBox.Multiline = true;
        this.customerNotesBox.ScrollBars = ScrollBars.Vertical;
        this.customerNotesBox.AccessibleName = "Customer notes";
        this.Controls.Add(this.customerNotesBox);

        this.walkInBox.Name = "walkInBox";
        this.walkInBox.Location = new Point(351, 406);
        this.walkInBox.Size = new Size(150, 28);
        this.walkInBox.Text = "Walk-in";
        this.Controls.Add(this.walkInBox);

        this.seriesButton = new Telerik.WinControls.UI.RadButton { Name = "seriesButton", Text = "Recurring booking",
            Location = new Point(351, 450), Size = new Size(233, 28), Enabled = false };
        this.seriesButton.Click += this.SeriesClicked;
        this.projectLabel = new Label();
        this.projectLabel.Name = "projectLabel";
        this.projectLabel.Location = new Point(23, 514);
        this.projectLabel.Size = new Size(305, 21);
        this.projectLabel.Text = "PMS delivery project (optional)";
        this.projectBox = new Telerik.WinControls.UI.RadDropDownList();
        this.projectBox.Name = "projectBox";
        this.projectBox.Location = new Point(23, 536);
        this.projectBox.Size = new Size(305, 28);
        this.projectBox.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.projectBox.Enabled = false;
        this.projectBox.SelectedIndexChanged += this.ProjectChanged;
        this.Controls.Add(this.projectLabel);
        this.Controls.Add(this.projectBox);
        this.dealLabel = new Label();
        this.dealLabel.Name = "dealLabel";
        this.dealLabel.Location = new Point(351, 514);
        this.dealLabel.Size = new Size(305, 21);
        this.dealLabel.Text = "CRM opportunity (optional)";
        this.dealBox = new Telerik.WinControls.UI.RadDropDownList();
        this.dealBox.Name = "dealBox";
        this.dealBox.Location = new Point(351, 536);
        this.dealBox.Size = new Size(305, 28);
        this.dealBox.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.dealBox.Enabled = false;
        this.dealBox.SelectedIndexChanged += this.DealChanged;
        this.Controls.Add(this.dealLabel);
        this.Controls.Add(this.dealBox);
        this.Controls.Add(this.seriesButton);

        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(23, 575);
        this.feedback.Size = new Size(633, 56);
        this.feedback.Text = "Loading shared scheduling records…";
        this.Controls.Add(this.feedback);

        this.customerContextButton.Name = "customerContextButton";
        this.customerContextButton.Location = new Point(23, 636);
        this.customerContextButton.Size = new Size(201, 34);
        this.customerContextButton.Text = "Customer visits and preferences";
        this.customerContextButton.Enabled = false;
        this.customerContextButton.Click += this.CustomerContextClicked;
        this.Controls.Add(this.customerContextButton);
        this.checkButton.Name = "checkButton";
        this.checkButton.Location = new Point(242, 636);
        this.checkButton.Size = new Size(150, 34);
        this.checkButton.Enabled = false;
        this.checkButton.Text = "Check availability";
        this.checkButton.Click += this.CheckClicked;
        this.Controls.Add(this.checkButton);

        this.saveButton.Name = "saveButton";
        this.saveButton.Location = new Point(403, 636);
        this.saveButton.Size = new Size(150, 34);
        this.saveButton.Text = "Confirm booking";
        this.saveButton.Click += this.SaveClicked;
        this.saveButton.Enabled = false;
        this.Controls.Add(this.saveButton);

        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Location = new Point(564, 636);
        this.cancelButton.Size = new Size(92, 34);
        this.cancelButton.Text = "Cancel";
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.Add(this.cancelButton);
        this.Text = "Business Suite | Appointment";
        this.Name = "AppointmentEditorForm";
        this.ClientSize = new Size(682, 687);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.Font = new Font("Segoe UI", 10F);
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.ForeColor = Color.FromArgb(24, 35, 58);
        this.StartPosition = FormStartPosition.CenterParent;
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MinimizeBox = false;
        this.MaximizeBox = false;
        this.AcceptButton = this.saveButton;
        this.CancelButton = this.cancelButton;
        this.Shown += this.EditorShown;
        this.FormClosing += this.EditorClosing;
        this.FormClosed += this.EditorClosed;
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label heading;
    private Label customerLabel;
    private ComboBox customerBox;
    private Label serviceLabel;
    private ComboBox serviceBox;
    private Label providerLabel;
    private ComboBox providerBox;
    private Label timezoneLabel;
    private Label startsLabel;
    private DateTimePicker startsPicker;
    private Label durationLabel;
    private NumericUpDown durationBox;
    private Label resourcesLabel;
    private CheckedListBox resourceList;
    private Label notesLabel;
    private TextBox notesBox;
    private Label customerNotesLabel;
    private TextBox customerNotesBox;
    private CheckBox walkInBox;
    private Telerik.WinControls.UI.RadButton seriesButton;
    private Label projectLabel;
    private Telerik.WinControls.UI.RadDropDownList projectBox;
    private Label dealLabel;
    private Telerik.WinControls.UI.RadDropDownList dealBox;
    private Label feedback;
    private Button saveButton;
    private Button checkButton;
    private Telerik.WinControls.UI.RadButton customerContextButton;
    private Telerik.WinControls.UI.RadButton slotPickerButton;
    private Button cancelButton;
}
