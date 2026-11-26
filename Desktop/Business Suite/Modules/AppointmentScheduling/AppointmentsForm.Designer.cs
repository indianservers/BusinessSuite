#nullable disable
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class AppointmentsForm
{
    private void InitializeComponent()
    {
        this.heading = new Label();
        this.agendaDate = new DateTimePicker();
        this.weekCheck = new CheckBox();
        this.statusFilter = new ComboBox();
        this.refreshButton = new Button();
        this.newButton = new Button();
        this.rescheduleButton = new Button();
        this.appointmentsGrid = new RadGridView();
        this.actionBox = new ComboBox();
        this.reasonBox = new CueTextBox();
        this.transitionButton = new Button();
        this.historyButton = new Telerik.WinControls.UI.RadButton();
        this.confirmationButton = new Telerik.WinControls.UI.RadButton();
        ((System.ComponentModel.ISupportInitialize)this.historyButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.confirmationButton).BeginInit();
        this.feedback = new Label();
        this.customerColumn = new GridViewTextBoxColumn();
        this.serviceColumn = new GridViewTextBoxColumn();
        this.startColumn = new GridViewDateTimeColumn();
        this.endColumn = new GridViewDateTimeColumn();
        this.statusColumn = new GridViewTextBoxColumn();
        this.notesColumn = new GridViewTextBoxColumn();
        ((System.ComponentModel.ISupportInitialize)this.appointmentsGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.appointmentsGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.heading.Name = "heading";
        this.heading.Location = new Point(24, 14);
        this.heading.Size = new Size(255, 52);
        this.heading.Text = "Appointments";
        this.heading.Font = new Font("Segoe UI Semibold", 26F);
        this.Controls.Add(this.heading);
        this.resourcesButton = new RadButton();
        this.resourcesButton.Name = "resourcesButton";
        this.resourcesButton.Text = "Scheduling resources";
        this.resourcesButton.Location = new Point(283, 28);
        this.resourcesButton.Size = new Size(152, 31);
        this.resourcesButton.Enabled = false;
        this.resourcesButton.Click += this.ResourcesClicked;
        this.Controls.Add(this.resourcesButton);

        this.serviceFilter = new RadDropDownList {
            Name = "serviceFilter", Location = new Point(444, 30), Size = new Size(190, 27),
            AccessibleName = "Appointment service", DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList,
            DisplayMember = "Label", ValueMember = "Service"
        };
        this.serviceFilter.SelectedValueChanged += this.FilterChanged;
        this.Controls.Add(this.serviceFilter);

        this.agendaSearch = new RadTextBox();
        this.agendaSearch.Name = "agendaSearch";
        this.agendaSearch.Location = new Point(649, 30);
        this.agendaSearch.Size = new Size(240, 27);
        this.agendaSearch.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.agendaSearch.AccessibleName = "Search appointments by customer or service";
        this.agendaSearch.NullText = "Search customer or service · Enter";
        this.agendaSearch.MaxLength = 180;
        this.agendaSearch.KeyDown += this.AgendaSearchKeyDown;
        this.Controls.Add(this.agendaSearch);
        this.timelineButton = new RadButton();
        this.timelineButton.Name = "timelineButton";
        this.timelineButton.Location = new Point(899, 28);
        this.timelineButton.Size = new Size(135, 31);
        this.timelineButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.timelineButton.Text = "Booking timeline";
        this.timelineButton.Enabled = false;
        this.timelineButton.Click += this.TimelineClicked;
        this.Controls.Add(this.timelineButton);

        this.agendaDate.Name = "agendaDate";
        this.agendaDate.Location = new Point(24, 80);
        this.agendaDate.Size = new Size(170, 28);
        this.agendaDate.Format = DateTimePickerFormat.Short;
        this.agendaDate.AccessibleName = "Agenda date";
        this.agendaDate.ValueChanged += this.FilterChanged;
        this.Controls.Add(this.agendaDate);

        this.weekCheck.Name = "weekCheck";
        this.weekCheck.Location = new Point(207, 75);
        this.weekCheck.Size = new Size(95, 35);
        this.weekCheck.Text = "7 days";
        this.weekCheck.CheckedChanged += this.FilterChanged;
        this.Controls.Add(this.weekCheck);

        this.statusFilter.Name = "statusFilter";
        this.statusFilter.Location = new Point(322, 80);
        this.statusFilter.Size = new Size(149, 28);
        this.statusFilter.DropDownStyle = ComboBoxStyle.DropDownList;
        this.statusFilter.AccessibleName = "Appointment status";
        this.statusFilter.Items.AddRange(new object[] { "All statuses", "Booked", "Checked in", "In service", "Completed", "Cancelled", "No show" });
        this.statusFilter.SelectedIndexChanged += this.FilterChanged;
        this.Controls.Add(this.statusFilter);

        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Location = new Point(485, 76);
        this.refreshButton.Size = new Size(106, 34);
        this.refreshButton.Text = "Refresh";
        this.refreshButton.AccessibleName = "Refresh appointments";
        this.refreshButton.Click += this.RefreshClicked;
        this.Controls.Add(this.refreshButton);

        this.waitlistButton = new RadButton { Name = "waitlistButton", Text = "Waitlist", Location = new Point(600, 76),
            Size = new Size(95, 34), Enabled = false };
        this.waitlistButton.AccessibleName = "Open appointment waitlist";
        this.waitlistButton.Click += this.WaitlistClicked;
        this.Controls.Add(this.waitlistButton);

        this.newButton.Name = "newButton";
        this.newButton.Location = new Point(704, 76);
        this.newButton.Size = new Size(158, 34);
        this.newButton.Text = "New appointment";
        this.newButton.AccessibleName = "Create new appointment";
        this.newButton.Click += this.NewClicked;
        this.newButton.Enabled = false;
        this.Controls.Add(this.newButton);

        this.rescheduleButton.Name = "rescheduleButton";
        this.rescheduleButton.Location = new Point(875, 76);
        this.rescheduleButton.Size = new Size(159, 34);
        this.rescheduleButton.Text = "Reschedule";
        this.rescheduleButton.AccessibleName = "Reschedule selected appointment";
        this.rescheduleButton.Click += this.RescheduleClicked;
        this.rescheduleButton.Enabled = false;
        this.Controls.Add(this.rescheduleButton);

        this.providerFilter = new RadDropDownList {
            Name = "providerFilter", Location = new Point(24, 123), Size = new Size(240, 28),
            AccessibleName = "Appointment provider", DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList,
            DisplayMember = "Name", ValueMember = "Id"
        };
        this.providerFilter.SelectedValueChanged += this.FilterChanged;
        this.Controls.Add(this.providerFilter);

        this.assetFilter = new RadDropDownList {
            Name = "assetFilter", Location = new Point(280, 123), Size = new Size(245, 28),
            AccessibleName = "Appointment room or equipment", DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList,
            DisplayMember = "Name", ValueMember = "Id"
        };
        this.assetFilter.SelectedValueChanged += this.FilterChanged;
        this.Controls.Add(this.assetFilter);

        this.previousDate = new RadButton {
            Name = "previousDate", Text = "Previous", AccessibleName = "Previous agenda period",
            Location = new Point(551, 120), Size = new Size(105, 30)
        };
        this.previousDate.Click += this.PreviousDateClicked;
        this.todayDate = new RadButton {
            Name = "todayDate", Text = "Today", AccessibleName = "Today in the agenda time zone",
            Location = new Point(668, 120), Size = new Size(105, 30)
        };
        this.todayDate.Click += this.TodayDateClicked;
        this.nextDate = new RadButton {
            Name = "nextDate", Text = "Next", AccessibleName = "Next agenda period",
            Location = new Point(785, 120), Size = new Size(105, 30)
        };
        this.nextDate.Click += this.NextDateClicked;
        this.Controls.Add(this.previousDate);
        this.Controls.Add(this.todayDate);
        this.Controls.Add(this.nextDate);

        this.clearFilters = new RadButton {
            Name = "clearFilters", Text = "Clear filters", Location = new Point(903, 120),
            Size = new Size(131, 30)
        };
        this.clearFilters.Click += this.ClearFiltersClicked;
        this.Controls.Add(this.clearFilters);

        this.appointmentsGrid.Name = "appointmentsGrid";
        this.appointmentsGrid.Location = new Point(24, 164);
        this.appointmentsGrid.Size = new Size(1010, 314);
        this.appointmentsGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.appointmentsGrid.MasterTemplate.AutoGenerateColumns = false;
        this.appointmentsGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.appointmentsGrid.MasterTemplate.AllowAddNewRow = false;
        this.appointmentsGrid.MasterTemplate.AllowDeleteRow = false;
        this.appointmentsGrid.ReadOnly = true;
        this.appointmentsGrid.ShowGroupPanel = false;
        this.appointmentsGrid.SelectionChanged += this.SelectionChanged;
        this.Controls.Add(this.appointmentsGrid);

        this.actionBox.Name = "actionBox";
        this.actionBox.Location = new Point(24, 497);
        this.actionBox.Size = new Size(142, 28);
        this.actionBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.actionBox.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
        this.actionBox.AccessibleName = "Appointment action";
        this.actionBox.Items.AddRange(new object[] { "Check in", "Start service", "Complete", "Cancel booking", "Mark no show" });
        this.actionBox.SelectedIndexChanged += this.SelectionChanged;
        this.actionBox.Enabled = false;
        this.Controls.Add(this.actionBox);

        this.reasonBox.Name = "reasonBox";
        this.reasonBox.Location = new Point(181, 497);
        this.reasonBox.Size = new Size(300, 29);
        this.reasonBox.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
        this.reasonBox.AccessibleName = "Cancellation or no-show reason";
        this.reasonBox.PlaceholderText = "Reason for cancelling or no-show";
        this.reasonBox.MaxLength = 1000;
        this.reasonBox.TextChanged += this.SelectionChanged;
        this.reasonBox.Enabled = false;
        this.Controls.Add(this.reasonBox);

        this.transitionButton.Name = "transitionButton";
        this.transitionButton.Location = new Point(493, 493);
        this.transitionButton.Size = new Size(112, 34);
        this.transitionButton.Text = "Apply action";
        this.transitionButton.AccessibleName = "Apply appointment status action";
        this.transitionButton.Click += this.TransitionClicked;
        this.transitionButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
        this.transitionButton.Enabled = false;
        this.Controls.Add(this.transitionButton);
        this.historyButton.Name = "historyButton";
        this.historyButton.Location = new Point(617, 493);
        this.historyButton.Size = new Size(115, 34);
        this.historyButton.Text = "Booking history";
        this.historyButton.AccessibleName = "View selected appointment history";
        this.historyButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
        this.historyButton.Enabled = false;
        this.historyButton.Click += this.HistoryClicked;
        this.Controls.Add(this.historyButton);
        ((System.ComponentModel.ISupportInitialize)this.historyButton).EndInit();
        this.confirmationButton.Name = "confirmationButton";
        this.confirmationButton.Location = new Point(744, 493);
        this.confirmationButton.Size = new Size(161, 34);
        this.confirmationButton.Text = "Booking confirmation";
        this.confirmationButton.AccessibleName = "View selected booking confirmation";
        this.confirmationButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
        this.confirmationButton.Enabled = false;
        this.confirmationButton.Click += this.ConfirmationClicked;
        this.Controls.Add(this.confirmationButton);
        ((System.ComponentModel.ISupportInitialize)this.confirmationButton).EndInit();
        this.billingButton = new RadButton();
        this.billingButton.Name = "billingButton";
        this.billingButton.Location = new Point(914, 493);
        this.billingButton.Size = new Size(120, 34);
        this.billingButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
        this.billingButton.Text = "Visit payments";
        this.billingButton.AccessibleName = "View selected appointment payments";
        this.billingButton.Enabled = false;
        this.billingButton.Click += this.BillingClicked;
        this.Controls.Add(this.billingButton);

        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(24, 546);
        this.feedback.Size = new Size(1010, 26);
        this.feedback.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.feedback.Text = "Loading the agenda…";
        this.Controls.Add(this.feedback);
        this.customerColumn.Name = "customerColumn";
        this.customerColumn.FieldName = "customer";
        this.customerColumn.HeaderText = "Customer";
        this.customerColumn.Width = 185;
        this.serviceColumn.Name = "serviceColumn";
        this.serviceColumn.FieldName = "service";
        this.serviceColumn.HeaderText = "Service";
        this.serviceColumn.Width = 185;
        this.startColumn.Name = "startColumn";
        this.startColumn.FieldName = "starts_local";
        this.startColumn.HeaderText = "Starts";
        this.startColumn.Width = 140;
        this.startColumn.FormatString = "{0:dd MMM, HH:mm}";
        this.endColumn.Name = "endColumn";
        this.endColumn.FieldName = "ends_local";
        this.endColumn.HeaderText = "Ends";
        this.endColumn.Width = 140;
        this.endColumn.FormatString = "{0:dd MMM, HH:mm}";
        this.statusColumn.Name = "statusColumn";
        this.statusColumn.FieldName = "status_label";
        this.statusColumn.HeaderText = "Status";
        this.statusColumn.Width = 130;
        this.notesColumn.Name = "notesColumn";
        this.notesColumn.FieldName = "notes";
        this.notesColumn.HeaderText = "Notes";
        this.notesColumn.Width = 185;
        this.appointmentsGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.customerColumn, this.serviceColumn, this.startColumn, this.endColumn, this.statusColumn, this.notesColumn });
        this.Text = "Business Suite | Appointments";
        this.Name = "AppointmentsForm";
        this.ClientSize = new Size(1060, 593);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.Font = new Font("Segoe UI", 10F);
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.ForeColor = Color.FromArgb(24, 35, 58);
        this.StartPosition = FormStartPosition.CenterParent;
        this.MinimumSize = new Size(1060, 490);
        this.Shown += this.AgendaShown;
        this.FormClosed += this.AgendaClosed;
        ((System.ComponentModel.ISupportInitialize)this.appointmentsGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.appointmentsGrid).EndInit();
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private RadTextBox agendaSearch;
    private RadDropDownList providerFilter, assetFilter, serviceFilter;
    private RadButton previousDate, todayDate, nextDate, clearFilters;
    private Label heading;
    private DateTimePicker agendaDate;
    private CheckBox weekCheck;
    private ComboBox statusFilter;
    private Button refreshButton;
    private RadButton waitlistButton;
    private Button newButton;
    private Button rescheduleButton;
    private RadButton billingButton;
    private RadButton resourcesButton;
    private RadButton timelineButton;
    private RadGridView appointmentsGrid;
    private ComboBox actionBox;
    private CueTextBox reasonBox;
    private Button transitionButton;
    private Telerik.WinControls.UI.RadButton historyButton;
    private Telerik.WinControls.UI.RadButton confirmationButton;
    private Label feedback;
    private GridViewTextBoxColumn customerColumn;
    private GridViewTextBoxColumn serviceColumn;
    private GridViewDateTimeColumn startColumn;
    private GridViewDateTimeColumn endColumn;
    private GridViewTextBoxColumn statusColumn;
    private GridViewTextBoxColumn notesColumn;
}
