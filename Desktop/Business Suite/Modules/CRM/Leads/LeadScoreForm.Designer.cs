using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class LeadScoreForm
{
    private void InitializeComponent()
    {
        this.scoreLabel = new Label();
        this.reasonsGrid = new RadGridView();
        this.replaceBox = new CheckBox();
        this.manualScoreLabel = new Label();
        this.manualScoreBox = new RadSpinEditor();
        this.reasonLabel = new Label();
        this.reasonBox = new TextBox();
        this.saveManualButton = new Button();
        this.feedback = new Label();
        this.calculateButton = new Button();
        this.closeButton = new Button();
        this.SuspendLayout();
        ((System.ComponentModel.ISupportInitialize)this.reasonsGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.reasonsGrid.MasterTemplate).BeginInit();
        var ruleColumn = new GridViewTextBoxColumn();
        ruleColumn.Name = "rule";
        ruleColumn.FieldName = "Name";
        ruleColumn.HeaderText = "Scoring rule";
        ruleColumn.Width = 325;
        var matchedColumn = new GridViewCheckBoxColumn();
        matchedColumn.Name = "matched";
        matchedColumn.FieldName = "Matched";
        matchedColumn.HeaderText = "Matched";
        matchedColumn.Width = 84;
        var pointsColumn = new GridViewTextBoxColumn();
        pointsColumn.Name = "points";
        pointsColumn.FieldName = "Points";
        pointsColumn.HeaderText = "Points";
        pointsColumn.Width = 82;
        this.reasonsGrid.Name = "reasonsGrid";
        this.reasonsGrid.Location = new Point(16, 55);
        this.reasonsGrid.Size = new Size(528, 225);
        this.reasonsGrid.AutoGenerateColumns = false;
        this.reasonsGrid.ReadOnly = true;
        this.reasonsGrid.MasterTemplate.AllowAddNewRow = false;
        this.reasonsGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { ruleColumn, matchedColumn, pointsColumn });
        this.scoreLabel.Name = "scoreLabel";
        this.scoreLabel.Location = new Point(16, 12);
        this.scoreLabel.Size = new Size(528, 32);
        this.scoreLabel.Font = new Font("Segoe UI Semibold", 13F);
        this.scoreLabel.Text = "Lead score";
        this.replaceBox.Name = "replaceBox";
        this.replaceBox.Location = new Point(16, 293);
        this.replaceBox.Size = new Size(528, 25);
        this.replaceBox.Text = "Replace the manual score with an automatic score";
        this.replaceBox.Visible = false;
        this.replaceBox.CheckedChanged += this.ReplaceChanged;
        this.manualScoreLabel.Location = new Point(16, 331);
        this.manualScoreLabel.Size = new Size(112, 23);
        this.manualScoreLabel.Text = "Manual score";
        this.manualScoreBox.Name = "manualScoreBox";
        this.manualScoreBox.Location = new Point(16, 357);
        this.manualScoreBox.Size = new Size(112, 25);
        this.manualScoreBox.Minimum = 0;
        this.manualScoreBox.Maximum = 100;
        this.reasonLabel.Location = new Point(144, 331);
        this.reasonLabel.Size = new Size(400, 23);
        this.reasonLabel.Text = "Reason for score override";
        this.reasonBox.Name = "reasonBox";
        this.reasonBox.Location = new Point(144, 357);
        this.reasonBox.Size = new Size(400, 25);
        this.reasonBox.MaxLength = 1000;
        this.saveManualButton.Name = "saveManualButton";
        this.saveManualButton.Location = new Point(16, 430);
        this.saveManualButton.Size = new Size(150, 33);
        this.saveManualButton.Text = "Save manual score";
        this.saveManualButton.Click += this.SaveManualClicked;
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(16, 390);
        this.feedback.Size = new Size(528, 30);
        this.feedback.Text = "Recalculate to see how each rule contributes.";
        this.calculateButton.Name = "calculateButton";
        this.calculateButton.Location = new Point(297, 430);
        this.calculateButton.Size = new Size(132, 33);
        this.calculateButton.Text = "Recalculate";
        this.calculateButton.Enabled = false;
        this.calculateButton.Click += this.CalculateClicked;
        this.closeButton.Name = "closeButton";
        this.closeButton.Location = new Point(444, 430);
        this.closeButton.Size = new Size(100, 33);
        this.closeButton.Text = "Close";
        this.closeButton.DialogResult = DialogResult.Cancel;
        this.Controls.AddRange(new Control[] { this.scoreLabel, this.reasonsGrid, this.replaceBox, this.manualScoreLabel,
            this.manualScoreBox, this.reasonLabel, this.reasonBox, this.feedback, this.saveManualButton,
            this.calculateButton, this.closeButton });
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(560, 478);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.CancelButton = this.closeButton;
        this.StartPosition = FormStartPosition.CenterParent;
        this.Text = "Lead score";
        this.FormClosed += this.FormIsClosed;
        ((System.ComponentModel.ISupportInitialize)this.reasonsGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.reasonsGrid).EndInit();
        this.ResumeLayout(false);
    }

    private Label scoreLabel;
    private RadGridView reasonsGrid;
    private CheckBox replaceBox;
    private Label manualScoreLabel;
    private RadSpinEditor manualScoreBox;
    private Label reasonLabel;
    private TextBox reasonBox;
    private Button saveManualButton;
    private Label feedback;
    private Button calculateButton;
    private Button closeButton;
}
