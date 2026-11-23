using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class LeadMeetingMetricsForm
{
    private void InitializeComponent()
    {
        this.metricsGrid = new RadGridView();
        this.definition = new Label();
        this.feedback = new Label();
        this.refreshButton = new Button();
        this.closeButton = new Button();
        this.SuspendLayout();
        ((System.ComponentModel.ISupportInitialize)this.metricsGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.metricsGrid.MasterTemplate).BeginInit();
        var statusColumn = new GridViewTextBoxColumn();
        statusColumn.Name = "status";
        statusColumn.FieldName = "Status";
        statusColumn.HeaderText = "Meeting status";
        statusColumn.Width = 225;
        var countColumn = new GridViewTextBoxColumn();
        countColumn.Name = "occurrences";
        countColumn.FieldName = "Occurrences";
        countColumn.HeaderText = "Occurrences";
        countColumn.Width = 140;
        this.metricsGrid.Name = "metricsGrid";
        this.metricsGrid.Location = new Point(16, 52);
        this.metricsGrid.Size = new Size(478, 220);
        this.metricsGrid.AutoGenerateColumns = false;
        this.metricsGrid.ReadOnly = true;
        this.metricsGrid.MasterTemplate.AllowAddNewRow = false;
        this.metricsGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { statusColumn, countColumn });
        this.definition.Location = new Point(16, 13);
        this.definition.Size = new Size(478, 34);
        this.definition.Text = "Current counts across permitted Leads. Rescheduled meetings retain their original occurrence.";
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(16, 282);
        this.feedback.Size = new Size(478, 32);
        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Location = new Point(275, 319);
        this.refreshButton.Size = new Size(104, 34);
        this.refreshButton.Text = "Refresh";
        this.refreshButton.Click += this.RefreshClicked;
        this.closeButton.Location = new Point(390, 319);
        this.closeButton.Size = new Size(104, 34);
        this.closeButton.Text = "Close";
        this.closeButton.DialogResult = DialogResult.Cancel;
        this.Controls.AddRange(new Control[] { this.metricsGrid, this.definition, this.feedback,
            this.refreshButton, this.closeButton });
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(510, 369);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.CancelButton = this.closeButton;
        this.StartPosition = FormStartPosition.CenterParent;
        this.Text = "Consultations and demos";
        this.Shown += this.RefreshClicked;
        this.FormClosed += this.FormIsClosed;
        ((System.ComponentModel.ISupportInitialize)this.metricsGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.metricsGrid).EndInit();
        this.ResumeLayout(false);
    }

    private RadGridView metricsGrid;
    private Label definition;
    private Label feedback;
    private Button refreshButton;
    private Button closeButton;
}
