using System.ComponentModel;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class AppointmentHistoryForm
{
    private void InitializeComponent()
    {
        heading = new Label();
        refreshButton = new RadButton();
        historyGrid = new RadGridView();
        reasonLabel = new Label();
        reasonBox = new RadTextBox();
        statusLabel = new Label();
        var recordedColumn = new GridViewTextBoxColumn();
        var actionColumn = new GridViewTextBoxColumn();
        var statusColumn = new GridViewTextBoxColumn();
        var revisionColumn = new GridViewTextBoxColumn();
        var actorColumn = new GridViewTextBoxColumn();
        var startsColumn = new GridViewTextBoxColumn();
        ((ISupportInitialize)refreshButton).BeginInit();
        ((ISupportInitialize)historyGrid).BeginInit();
        ((ISupportInitialize)historyGrid.MasterTemplate).BeginInit();
        ((ISupportInitialize)reasonBox).BeginInit();
        SuspendLayout();

        heading.Name = "heading";
        heading.Font = new Font("Segoe UI Semibold", 18F);
        heading.Text = "Appointment history";
        heading.Location = new Point(20, 18);
        heading.Size = new Size(615, 32);
        heading.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
        heading.AutoEllipsis = true;
        refreshButton.Name = "refreshButton";
        refreshButton.Location = new Point(654, 21);
        refreshButton.Size = new Size(104, 28);
        refreshButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        refreshButton.Text = "Refresh";
        refreshButton.Click += LoadClicked;

        historyGrid.Name = "historyGrid";
        historyGrid.Location = new Point(20, 62);
        historyGrid.Size = new Size(738, 271);
        historyGrid.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
        historyGrid.ReadOnly = true;
        historyGrid.ShowGroupPanel = false;
        historyGrid.MasterTemplate.AllowAddNewRow = false;
        historyGrid.MasterTemplate.AllowDeleteRow = false;
        historyGrid.MasterTemplate.AllowEditRow = false;
        historyGrid.MasterTemplate.AutoGenerateColumns = false;
        historyGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        historyGrid.MasterTemplate.EnableFiltering = true;
        recordedColumn.Name = "recordedColumn";
        recordedColumn.FieldName = "Recorded";
        recordedColumn.HeaderText = "Date recorded";
        recordedColumn.Width = 132;
        actionColumn.Name = "actionColumn";
        actionColumn.FieldName = "Action";
        actionColumn.HeaderText = "Action";
        actionColumn.Width = 113;
        statusColumn.Name = "statusColumn";
        statusColumn.FieldName = "Status";
        statusColumn.HeaderText = "Status";
        statusColumn.Width = 125;
        revisionColumn.Name = "revisionColumn";
        revisionColumn.FieldName = "Revision";
        revisionColumn.HeaderText = "Revision";
        revisionColumn.Width = 58;
        actorColumn.Name = "actorColumn";
        actorColumn.FieldName = "Actor";
        actorColumn.HeaderText = "Actor ID";
        actorColumn.Width = 68;
        startsColumn.Name = "startsColumn";
        startsColumn.FieldName = "Starts";
        startsColumn.HeaderText = "Scheduled start";
        startsColumn.Width = 135;
        recordedColumn.FormatString = "{0:g}";
        startsColumn.FormatString = "{0:g}";
        historyGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            recordedColumn, actionColumn, statusColumn, revisionColumn, actorColumn, startsColumn
        });
        historyGrid.SelectionChanged += HistorySelectionChanged;

        reasonLabel.Name = "reasonLabel";
        reasonLabel.Location = new Point(20, 347);
        reasonLabel.Size = new Size(200, 22);
        reasonLabel.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
        reasonLabel.Text = "Action reason";
        reasonBox.Name = "reasonBox";
        reasonBox.AccessibleName = "Selected appointment action reason";
        reasonBox.Location = new Point(20, 373);
        reasonBox.Size = new Size(738, 71);
        reasonBox.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        reasonBox.ReadOnly = true;
        reasonBox.Multiline = true;
        reasonBox.ScrollBars = ScrollBars.Vertical;
        statusLabel.Name = "statusLabel";
        statusLabel.Location = new Point(20, 457);
        statusLabel.Size = new Size(738, 25);
        statusLabel.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;

        AutoScaleDimensions = new SizeF(96F, 96F);
        AutoScaleMode = AutoScaleMode.Dpi;
        BackColor = Color.FromArgb(243, 246, 251);
        ClientSize = new Size(778, 491);
        Controls.Add(heading);
        Controls.Add(refreshButton);
        Controls.Add(historyGrid);
        Controls.Add(reasonLabel);
        Controls.Add(reasonBox);
        Controls.Add(statusLabel);
        Font = new Font("Segoe UI", 10F);
        MinimumSize = new Size(650, 433);
        Name = "AppointmentHistoryForm";
        Text = "Appointment history";
        StartPosition = FormStartPosition.CenterParent;
        ShowInTaskbar = false;
        Shown += LoadClicked;
        FormClosed += HistoryClosed;
        ((ISupportInitialize)refreshButton).EndInit();
        ((ISupportInitialize)historyGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)historyGrid).EndInit();
        ((ISupportInitialize)reasonBox).EndInit();
        ResumeLayout(false);
        PerformLayout();
    }

    private Label heading;
    private RadButton refreshButton;
    private RadGridView historyGrid;
    private Label reasonLabel;
    private RadTextBox reasonBox;
    private Label statusLabel;
}
