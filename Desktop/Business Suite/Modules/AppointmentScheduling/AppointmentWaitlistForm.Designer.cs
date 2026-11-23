using Telerik.WinControls.UI;

namespace Business_Suite;

partial class AppointmentWaitlistForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        grid = new RadGridView { Name = "grid", Location = new Point(20, 42), Size = new Size(743, 184),
            ReadOnly = true, ShowGroupPanel = false, AccessibleName = "My waiting preferences" };
        grid.MasterTemplate.AutoGenerateColumns = false;
        grid.MasterTemplate.AllowAddNewRow = false;
        grid.MasterTemplate.AllowDeleteRow = false;
        grid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        grid.MasterTemplate.Columns.AddRange(
            new GridViewDataColumn[] {
                new GridViewTextBoxColumn { Name = "idColumn", FieldName = "Id", HeaderText = "Reference", Width = 70 },
                new GridViewTextBoxColumn { Name = "customerColumn", FieldName = "Customer", HeaderText = "Customer", Width = 160 },
                new GridViewTextBoxColumn { Name = "serviceColumn", FieldName = "Service", HeaderText = "Service", Width = 160 },
                new GridViewTextBoxColumn { Name = "fromColumn", FieldName = "From", HeaderText = "From", Width = 95 },
                new GridViewTextBoxColumn { Name = "untilColumn", FieldName = "Until", HeaderText = "Until", Width = 95 },
                new GridViewTextBoxColumn { Name = "zoneColumn", FieldName = "Zone", HeaderText = "Timezone", Width = 125 }
            });
        grid.SelectionChanged += SelectionChanged;
        listLabel = new Label { Name = "listLabel", Text = "My waiting preferences · latest 20", Location = new Point(20, 15), Size = new Size(300, 22) };
        refreshButton = new RadButton { Name = "refreshButton", Text = "Refresh list", Location = new Point(458, 10), Size = new Size(125, 25) };
        refreshButton.Click += RefreshClicked;
        cancelButton = new RadButton { Name = "cancelButton", Text = "Cancel selected preference", Location = new Point(593, 10), Size = new Size(170, 25), Enabled = false };
        cancelButton.Click += CancelClicked;
        entryPanel = new Panel { Name = "entryPanel", Location = new Point(20, 242), Size = new Size(743, 278), Enabled = false };
        customerLabel = new Label { Name = "customerLabel", Text = "Customer", Location = new Point(0, 6), Size = new Size(90, 22) };
        customer = new ComboBox { Name = "customer", Location = new Point(93, 2), Size = new Size(264, 26),
            DropDownStyle = ComboBoxStyle.DropDownList, DisplayMember = "Name", AccessibleName = "Customer" };
        serviceLabel = new Label { Name = "serviceLabel", Text = "Service", Location = new Point(373, 6), Size = new Size(82, 22) };
        service = new ComboBox { Name = "service", Location = new Point(458, 2), Size = new Size(285, 26),
            DropDownStyle = ComboBoxStyle.DropDownList, DisplayMember = "Name", AccessibleName = "Service" };
        service.SelectedIndexChanged += ServiceChanged;
        fromLabel = new Label { Name = "fromLabel", Text = "From date", Location = new Point(0, 47), Size = new Size(90, 22) };
        from = new DateTimePicker { Name = "from", Location = new Point(93, 43), Size = new Size(129, 26), Format = DateTimePickerFormat.Short, AccessibleName = "From date" };
        untilLabel = new Label { Name = "untilLabel", Text = "Until date", Location = new Point(243, 47), Size = new Size(75, 22) };
        until = new DateTimePicker { Name = "until", Location = new Point(325, 43), Size = new Size(129, 26), Format = DateTimePickerFormat.Short, AccessibleName = "Until date" };
        opensLabel = new Label { Name = "opensLabel", Text = "From time", Location = new Point(0, 85), Size = new Size(90, 22) };
        opens = new DateTimePicker { Name = "opens", Location = new Point(93, 81), Size = new Size(129, 26), Format = DateTimePickerFormat.Custom,
            CustomFormat = "HH:mm", ShowUpDown = true, AccessibleName = "From time" };
        closesLabel = new Label { Name = "closesLabel", Text = "Until time", Location = new Point(243, 85), Size = new Size(75, 22) };
        closes = new DateTimePicker { Name = "closes", Location = new Point(325, 81), Size = new Size(129, 26), Format = DateTimePickerFormat.Custom,
            CustomFormat = "HH:mm", ShowUpDown = true, AccessibleName = "Until time" };
        zoneLabel = new Label { Name = "zoneLabel", Text = "Timezone: UTC", Location = new Point(482, 84), Size = new Size(261, 22) };
        providerLabel = new Label { Name = "providerLabel", Text = "Provider", Location = new Point(0, 124), Size = new Size(90, 22) };
        provider = new ComboBox { Name = "provider", Location = new Point(93, 120), Size = new Size(264, 26),
            DropDownStyle = ComboBoxStyle.DropDownList, DisplayMember = "Name", AccessibleName = "Preferred provider" };
        provider.SelectedIndexChanged += ProviderChanged;
        flexibleProvider = new CheckBox { Name = "flexibleProvider", Text = "Allow any qualified employee", Location = new Point(93, 151),
            Size = new Size(264, 24), Checked = true };
        resourceLabel = new Label { Name = "resourceLabel", Text = "Additional resources", Location = new Point(373, 121), Size = new Size(370, 22) };
        resources = new CheckedListBox { Name = "resources", Location = new Point(373, 145), Size = new Size(370, 76),
            DisplayMember = "Name", CheckOnClick = true, AccessibleName = "Preferred additional resources" };
        flexibleResources = new CheckBox { Name = "flexibleResources", Text = "Allow alternative required resources", Location = new Point(373, 221),
            Size = new Size(370, 24), Checked = true };
        notesLabel = new Label { Name = "notesLabel", Text = "Notes", Location = new Point(0, 183), Size = new Size(90, 22) };
        notes = new RadTextBox { Name = "notes", Location = new Point(0, 210), Size = new Size(357, 59),
            Multiline = true, MaxLength = 1000, ScrollBars = ScrollBars.Vertical, AccessibleName = "Waitlist notes" };
        entryPanel.Controls.AddRange(new Control[] { customerLabel, customer, serviceLabel, service, fromLabel, from, untilLabel, until,
            opensLabel, opens, closesLabel, closes, providerLabel, provider, flexibleProvider, resourceLabel, resources, flexibleResources,
            notesLabel, notes, zoneLabel });
        saveButton = new RadButton { Name = "saveButton", Text = "Save waitlist preference", Location = new Point(565, 525),
            Size = new Size(198, 28), Enabled = false };
        saveButton.Click += SaveClicked;
        checkButton = new RadButton { Name = "checkButton", Text = "Check request status", Location = new Point(407, 525),
            Size = new Size(148, 28), Visible = false };
        checkButton.Click += CheckClicked;
        feedback = new Label { Name = "feedback", Text = "A waiting preference does not reserve a slot.",
            Location = new Point(20, 523), Size = new Size(374, 38) };
        Controls.AddRange(new Control[] { listLabel, grid, refreshButton, cancelButton, entryPanel, saveButton, checkButton, feedback });
        ClientSize = new Size(783, 567);
        Font = new Font("Segoe UI", 9F);
        AutoScaleDimensions = new SizeF(7F, 15F);
        AutoScaleMode = AutoScaleMode.Font;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = MinimizeBox = false;
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.CenterParent;
        Name = "AppointmentWaitlistForm";
        Text = "Appointment waitlist";
        Shown += ShownList;
        FormClosing += ClosingList;
        ResumeLayout(false);
        PerformLayout();
    }

    private RadGridView grid;
    private Panel entryPanel;
    private Label listLabel, customerLabel, serviceLabel, fromLabel, untilLabel, opensLabel, closesLabel, zoneLabel,
        providerLabel, resourceLabel, notesLabel, feedback;
    private ComboBox customer, service, provider;
    private DateTimePicker from, until, opens, closes;
    private CheckBox flexibleProvider, flexibleResources;
    private CheckedListBox resources;
    private RadTextBox notes;
    private RadButton refreshButton, cancelButton, saveButton, checkButton;
}
