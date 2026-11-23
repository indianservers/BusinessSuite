using System.ComponentModel;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class SalesReceiptHistoryForm
{
    private void InitializeComponent()
    {
        this.summaryLabel = new Label();
        this.statusLabel = new Label();
        this.reasonLabel = new Label();
        this.historyGrid = new RadGridView();
        this.numberColumn = new GridViewTextBoxColumn();
        this.amountColumn = new GridViewDecimalColumn();
        this.methodColumn = new GridViewTextBoxColumn();
        this.referenceColumn = new GridViewTextBoxColumn();
        this.receiptDateColumn = new GridViewDateTimeColumn();
        this.appliedDateColumn = new GridViewDateTimeColumn();
        this.reversedDateColumn = new GridViewDateTimeColumn();
        this.reasonColumn = new GridViewTextBoxColumn();
        this.reasonBox = new RadTextBox();
        this.refreshButton = new RadButton();
        this.reverseButton = new RadButton();
        this.closeButton = new RadButton();
        ((ISupportInitialize)this.historyGrid).BeginInit();
        ((ISupportInitialize)this.historyGrid.MasterTemplate).BeginInit();
        ((ISupportInitialize)this.reasonBox).BeginInit();
        ((ISupportInitialize)this.refreshButton).BeginInit();
        ((ISupportInitialize)this.reverseButton).BeginInit();
        ((ISupportInitialize)this.closeButton).BeginInit();
        this.SuspendLayout();

        this.summaryLabel.Name = "summaryLabel";
        this.summaryLabel.Location = new Point(20, 17);
        this.summaryLabel.Size = new Size(820, 30);
        this.summaryLabel.Font = new Font("Segoe UI Semibold", 14F);
        this.summaryLabel.Text = "Payment history";

        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Text = "Refresh";
        this.refreshButton.Location = new Point(865, 16);
        this.refreshButton.Size = new Size(115, 28);
        this.refreshButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.refreshButton.Click += this.RefreshClicked;

        this.historyGrid.Name = "historyGrid";
        this.historyGrid.Location = new Point(20, 56);
        this.historyGrid.Size = new Size(960, 344);
        this.historyGrid.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
        this.historyGrid.ReadOnly = true;
        this.historyGrid.MasterTemplate.AutoGenerateColumns = false;
        this.historyGrid.MasterTemplate.AllowAddNewRow = false;
        this.historyGrid.MasterTemplate.AllowDeleteRow = false;
        this.historyGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.historyGrid.SelectionChanged += this.HistorySelectionChanged;

        this.numberColumn.Name = "numberColumn";
        this.numberColumn.FieldName = "Number";
        this.numberColumn.HeaderText = "Receipt";
        this.numberColumn.Width = 130;

        this.amountColumn.Name = "amountColumn";
        this.amountColumn.FieldName = "Amount";
        this.amountColumn.HeaderText = "Applied amount";
        this.amountColumn.Width = 100;
        this.amountColumn.FormatString = "{0:N2}";

        this.methodColumn.Name = "methodColumn";
        this.methodColumn.FieldName = "Method";
        this.methodColumn.HeaderText = "Method";
        this.methodColumn.Width = 105;

        this.referenceColumn.Name = "referenceColumn";
        this.referenceColumn.FieldName = "Reference";
        this.referenceColumn.HeaderText = "Reference";
        this.referenceColumn.Width = 155;

        this.receiptDateColumn.Name = "receiptDateColumn";
        this.receiptDateColumn.FieldName = "Date";
        this.receiptDateColumn.HeaderText = "Received";
        this.receiptDateColumn.Width = 94;
        this.receiptDateColumn.FormatString = "{0:d}";

        this.appliedDateColumn.Name = "appliedDateColumn";
        this.appliedDateColumn.FieldName = "Applied";
        this.appliedDateColumn.HeaderText = "Applied at";
        this.appliedDateColumn.Width = 133;
        this.appliedDateColumn.FormatString = "{0:g}";

        this.reversedDateColumn.Name = "reversedDateColumn";
        this.reversedDateColumn.FieldName = "Reversed";
        this.reversedDateColumn.HeaderText = "Reversed at";
        this.reversedDateColumn.Width = 133;
        this.reversedDateColumn.FormatString = "{0:g}";

        this.reasonColumn.Name = "reasonColumn";
        this.reasonColumn.FieldName = "Reason";
        this.reasonColumn.HeaderText = "Reversal reason";
        this.reasonColumn.Width = 165;
        this.historyGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            this.numberColumn, this.amountColumn, this.methodColumn, this.referenceColumn,
            this.receiptDateColumn, this.appliedDateColumn, this.reversedDateColumn, this.reasonColumn
        });

        this.reasonLabel.Name = "reasonLabel";
        this.reasonLabel.Text = "Reversal reason";
        this.reasonLabel.Location = new Point(20, 420);
        this.reasonLabel.Size = new Size(124, 25);
        this.reasonLabel.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;

        this.reasonBox.Name = "reasonBox";
        this.reasonBox.AccessibleName = "Reversal reason";
        this.reasonBox.Location = new Point(145, 419);
        this.reasonBox.Size = new Size(533, 28);
        this.reasonBox.Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
        this.reasonBox.Enabled = false;
        this.reasonBox.MaxLength = 500;
        this.reasonBox.TextChanged += this.ReasonChanged;

        this.reverseButton.Name = "reverseButton";
        this.reverseButton.Text = "Reverse payment";
        this.reverseButton.Location = new Point(692, 416);
        this.reverseButton.Size = new Size(155, 31);
        this.reverseButton.Anchor = AnchorStyles.Right | AnchorStyles.Bottom;
        this.reverseButton.Enabled = false;
        this.reverseButton.Click += this.ReverseClicked;

        this.closeButton.Name = "closeButton";
        this.closeButton.Text = "Close";
        this.closeButton.Location = new Point(865, 416);
        this.closeButton.Size = new Size(115, 31);
        this.closeButton.Anchor = AnchorStyles.Right | AnchorStyles.Bottom;
        this.closeButton.DialogResult = DialogResult.Cancel;

        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Location = new Point(20, 460);
        this.statusLabel.Size = new Size(960, 42);
        this.statusLabel.Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;

        this.AutoScaleDimensions = new SizeF(7F, 15F);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(1000, 510);
        this.MinimumSize = new Size(820, 392);
        this.Name = "SalesReceiptHistoryForm";
        this.Text = "Invoice payment history";
        this.StartPosition = FormStartPosition.CenterParent;
        this.CancelButton = this.closeButton;
        this.Controls.Add(this.summaryLabel);
        this.Controls.Add(this.refreshButton);
        this.Controls.Add(this.historyGrid);
        this.Controls.Add(this.reasonLabel);
        this.Controls.Add(this.reasonBox);
        this.Controls.Add(this.reverseButton);
        this.Controls.Add(this.closeButton);
        this.Controls.Add(this.statusLabel);
        this.Shown += this.HistoryShown;
        this.FormClosing += this.HistoryClosing;
        ((ISupportInitialize)this.historyGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.historyGrid).EndInit();
        ((ISupportInitialize)this.reasonBox).EndInit();
        ((ISupportInitialize)this.refreshButton).EndInit();
        ((ISupportInitialize)this.reverseButton).EndInit();
        ((ISupportInitialize)this.closeButton).EndInit();
        this.ResumeLayout(false);
    }

    private Label summaryLabel;
    private Label statusLabel;
    private Label reasonLabel;
    private RadGridView historyGrid;
    private GridViewTextBoxColumn numberColumn;
    private GridViewDecimalColumn amountColumn;
    private GridViewTextBoxColumn methodColumn;
    private GridViewTextBoxColumn referenceColumn;
    private GridViewDateTimeColumn receiptDateColumn;
    private GridViewDateTimeColumn appliedDateColumn;
    private GridViewDateTimeColumn reversedDateColumn;
    private GridViewTextBoxColumn reasonColumn;
    private RadTextBox reasonBox;
    private RadButton refreshButton;
    private RadButton reverseButton;
    private RadButton closeButton;
}
