using Telerik.WinControls.UI;

namespace Business_Suite;

partial class AppointmentSeriesForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        intervalLabel = new Label { Name = "intervalLabel", Text = "Frequency", Location = new Point(20, 25), Size = new Size(82, 23) };
        intervalBox = new RadDropDownList { Name = "intervalBox", Location = new Point(105, 21), Size = new Size(162, 27),
            DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList, AccessibleName = "Frequency" };
        intervalBox.Items.Add(new RadListDataItem("Daily"));
        intervalBox.Items.Add(new RadListDataItem("Weekly"));
        intervalBox.Items.Add(new RadListDataItem("Every two weeks"));
        intervalBox.SelectedIndexChanged += InputChanged;
        countLabel = new Label { Name = "countLabel", Text = "Occurrences", Location = new Point(286, 25), Size = new Size(87, 23) };
        countBox = new NumericUpDown { Name = "countBox", Location = new Point(378, 22), Size = new Size(68, 27),
            Minimum = 2, Maximum = 12, Value = 3, AccessibleName = "Number of occurrences" };
        countBox.ValueChanged += InputChanged;
        previewButton = new RadButton { Name = "previewButton", Text = "Preview dates", Location = new Point(570, 21),
            Size = new Size(159, 29), Enabled = false };
        previewButton.Click += PreviewClicked;
        timezoneLabel = new Label { Name = "timezoneLabel", Text = "Dates use the provider timezone.", Location = new Point(20, 61), Size = new Size(700, 23) };
        grid = new RadGridView { Name = "grid", Location = new Point(20, 88), Size = new Size(709, 302), ShowGroupPanel = false,
            AccessibleName = "Recurring appointment dates" };
        grid.MasterTemplate.AutoGenerateColumns = false;
        grid.MasterTemplate.AllowAddNewRow = false;
        grid.MasterTemplate.AllowDeleteRow = false;
        grid.MasterTemplate.AllowColumnReorder = false;
        grid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewCheckBoxColumn { Name = "includeColumn", FieldName = "Include", HeaderText = "Include", Width = 75 },
            new GridViewDateTimeColumn { Name = "dateColumn", FieldName = "LocalTime", HeaderText = "Provider-local date and time",
                FormatString = "{0:g}", Width = 192, ReadOnly = true },
            new GridViewTextBoxColumn { Name = "statusColumn", FieldName = "Status", HeaderText = "Availability", Width = 440, ReadOnly = true }
        });
        grid.CellBeginEdit += BeginCellEdit;
        feedback = new Label { Name = "feedback", Location = new Point(20, 398), Size = new Size(709, 35),
            Text = "Preview dates before reserving. Booking does not collect payment." };
        resultLabel = new Label { Name = "resultLabel", Location = new Point(20, 438), Size = new Size(709, 31) };
        checkButton = new RadButton { Name = "checkButton", Text = "Check request status", Location = new Point(240, 474),
            Size = new Size(170, 29), Visible = false };
        checkButton.Click += CheckClicked;
        saveButton = new RadButton { Name = "saveButton", Text = "Confirm selected dates", Location = new Point(421, 474),
            Size = new Size(170, 29), Enabled = false };
        saveButton.Click += SaveClicked;
        closeButton = new RadButton { Name = "closeButton", Text = "Close", Location = new Point(602, 474),
            Size = new Size(127, 29), DialogResult = DialogResult.Cancel };
        Controls.AddRange(new Control[] { intervalLabel, intervalBox, countLabel, countBox, previewButton, timezoneLabel,
            grid, feedback, resultLabel, checkButton, saveButton, closeButton });
        CancelButton = closeButton;
        ClientSize = new Size(750, 519);
        Font = new Font("Segoe UI", 9F);
        AutoScaleDimensions = new SizeF(7F, 15F);
        AutoScaleMode = AutoScaleMode.Font;
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        ShowInTaskbar = MaximizeBox = MinimizeBox = false;
        Name = "AppointmentSeriesForm";
        Text = "Recurring appointment preview";
        Shown += SeriesShown;
        FormClosing += SeriesClosing;
        FormClosed += SeriesClosed;
        ResumeLayout(false);
        PerformLayout();
    }

    private Label intervalLabel, countLabel, timezoneLabel, feedback, resultLabel;
    private RadDropDownList intervalBox;
    private NumericUpDown countBox;
    private RadGridView grid;
    private RadButton previewButton, checkButton, saveButton, closeButton;
}
