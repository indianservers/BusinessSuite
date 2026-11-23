using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class LeadSequenceForm
{
    private void InitializeComponent()
    {
        this.currentLabel = new Label();
        this.sequenceBox = new RadDropDownList();
        this.stepsGrid = new RadGridView();
        this.feedback = new Label();
        this.startButton = new Button();
        this.stopButton = new Button();
        this.closeButton = new Button();
        this.SuspendLayout();
        ((System.ComponentModel.ISupportInitialize)this.stepsGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.stepsGrid.MasterTemplate).BeginInit();
        var dayColumn = new GridViewTextBoxColumn();
        dayColumn.Name = "Day";
        dayColumn.FieldName = "Day";
        dayColumn.HeaderText = "Day";
        dayColumn.Width = 55;
        var kindColumn = new GridViewTextBoxColumn();
        kindColumn.Name = "Kind";
        kindColumn.FieldName = "Kind";
        kindColumn.HeaderText = "Type";
        kindColumn.Width = 90;
        var titleColumn = new GridViewTextBoxColumn();
        titleColumn.Name = "Title";
        titleColumn.FieldName = "Title";
        titleColumn.HeaderText = "Task";
        titleColumn.Width = 347;
        this.currentLabel.Name = "currentLabel";
        this.currentLabel.Location = new Point(18, 13);
        this.currentLabel.Size = new Size(518, 29);
        this.currentLabel.Text = "Loading sequence…";
        this.sequenceBox.Name = "sequenceBox";
        this.sequenceBox.Location = new Point(18, 49);
        this.sequenceBox.Size = new Size(518, 28);
        this.sequenceBox.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.sequenceBox.Enabled = false;
        this.sequenceBox.SelectedIndexChanged += this.SelectionChanged;
        this.stepsGrid.Name = "stepsGrid";
        this.stepsGrid.Location = new Point(18, 92);
        this.stepsGrid.Size = new Size(518, 182);
        this.stepsGrid.AutoGenerateColumns = false;
        this.stepsGrid.ReadOnly = true;
        this.stepsGrid.MasterTemplate.AllowAddNewRow = false;
        this.stepsGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { dayColumn, kindColumn, titleColumn });
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(18, 283);
        this.feedback.Size = new Size(518, 36);
        this.startButton.Name = "startButton";
        this.startButton.Location = new Point(151, 325);
        this.startButton.Size = new Size(148, 34);
        this.startButton.Text = "Start sequence";
        this.startButton.Enabled = false;
        this.startButton.Click += this.StartClicked;
        this.stopButton.Name = "stopButton";
        this.stopButton.Location = new Point(310, 325);
        this.stopButton.Size = new Size(112, 34);
        this.stopButton.Text = "Stop sequence";
        this.stopButton.Enabled = false;
        this.stopButton.Click += this.StopClicked;
        this.closeButton.Location = new Point(433, 325);
        this.closeButton.Size = new Size(103, 34);
        this.closeButton.Text = "Close";
        this.closeButton.DialogResult = DialogResult.Cancel;
        this.Controls.AddRange(new Control[] { this.currentLabel, this.sequenceBox, this.stepsGrid, this.feedback,
            this.startButton, this.stopButton, this.closeButton });
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(554, 377);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.CancelButton = this.closeButton;
        this.StartPosition = FormStartPosition.CenterParent;
        this.Text = "Lead follow-up sequence";
        this.Shown += this.FormShown;
        this.FormClosed += this.FormIsClosed;
        ((System.ComponentModel.ISupportInitialize)this.stepsGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.stepsGrid).EndInit();
        this.ResumeLayout(false);
    }

    private Label currentLabel;
    private RadDropDownList sequenceBox;
    private RadGridView stepsGrid;
    private Label feedback;
    private Button startButton;
    private Button stopButton;
    private Button closeButton;
}
