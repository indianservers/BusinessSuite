using System.ComponentModel;
using Telerik.WinControls;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class PosReturnsForm
{
    private void InitializeComponent()
    {
        this.headingLabel = new Label();
        this.saleLabel = new Label();
        this.linesLabel = new Label();
        this.quantityLabel = new Label();
        this.conditionLabel = new Label();
        this.methodLabel = new Label();
        this.reasonLabel = new Label();
        this.instructionsLabel = new Label();
        this.statusLabel = new Label();
        this.searchBox = new RadTextBox();
        this.refreshButton = new RadButton();
        this.historyButton = new RadButton();
        this.quantityEditor = new RadSpinEditor();
        this.conditionPicker = new RadDropDownList();
        this.methodBox = new RadTextBox();
        this.reasonBox = new RadTextBox();
        this.restockCheck = new RadCheckBox();
        this.recordButton = new RadButton();
        this.closeButton = new RadButton();
        this.salesGrid = new RadGridView();
        this.orderColumn = new GridViewTextBoxColumn();
        this.invoiceColumn = new GridViewTextBoxColumn();
        this.customerColumn = new GridViewTextBoxColumn();
        this.currencyColumn = new GridViewTextBoxColumn();
        this.linesGrid = new RadGridView();
        this.productColumn = new GridViewTextBoxColumn();
        this.soldColumn = new GridViewDecimalColumn();
        this.returnedColumn = new GridViewDecimalColumn();
        this.remainingColumn = new GridViewDecimalColumn();
        this.unitColumn = new GridViewDecimalColumn();
        ((ISupportInitialize)this.searchBox).BeginInit();
        ((ISupportInitialize)this.refreshButton).BeginInit();
        ((ISupportInitialize)this.historyButton).BeginInit();
        ((ISupportInitialize)this.quantityEditor).BeginInit();
        ((ISupportInitialize)this.conditionPicker).BeginInit();
        ((ISupportInitialize)this.methodBox).BeginInit();
        ((ISupportInitialize)this.reasonBox).BeginInit();
        ((ISupportInitialize)this.restockCheck).BeginInit();
        ((ISupportInitialize)this.recordButton).BeginInit();
        ((ISupportInitialize)this.closeButton).BeginInit();
        ((ISupportInitialize)this.salesGrid).BeginInit();
        ((ISupportInitialize)this.salesGrid.MasterTemplate).BeginInit();
        ((ISupportInitialize)this.linesGrid).BeginInit();
        ((ISupportInitialize)this.linesGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.headingLabel.Name = "headingLabel";
        this.headingLabel.Text = "POS returns";
        this.headingLabel.Location = new Point(20, 13);
        this.headingLabel.Size = new Size(877, 33);

        this.saleLabel.Name = "saleLabel";
        this.saleLabel.Text = "Original POS sales";
        this.saleLabel.Location = new Point(20, 88);
        this.saleLabel.Size = new Size(877, 22);

        this.linesLabel.Name = "linesLabel";
        this.linesLabel.Text = "Original sale lines";
        this.linesLabel.Location = new Point(20, 267);
        this.linesLabel.Size = new Size(877, 22);

        this.quantityLabel.Name = "quantityLabel";
        this.quantityLabel.Text = "Quantity";
        this.quantityLabel.Location = new Point(20, 467);
        this.quantityLabel.Size = new Size(111, 21);

        this.conditionLabel.Name = "conditionLabel";
        this.conditionLabel.Text = "Condition";
        this.conditionLabel.Location = new Point(145, 467);
        this.conditionLabel.Size = new Size(174, 21);

        this.methodLabel.Name = "methodLabel";
        this.methodLabel.Text = "Refund method";
        this.methodLabel.Location = new Point(333, 467);
        this.methodLabel.Size = new Size(154, 21);

        this.reasonLabel.Name = "reasonLabel";
        this.reasonLabel.Text = "Reason";
        this.reasonLabel.Location = new Point(499, 467);
        this.reasonLabel.Size = new Size(388, 21);

        this.instructionsLabel.Name = "instructionsLabel";
        this.instructionsLabel.Text = "Record the refund already given. Enter any cash paid out separately in Cash drawer.";
        this.instructionsLabel.Location = new Point(20, 564);
        this.instructionsLabel.Size = new Size(880, 26);

        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Text = "";
        this.statusLabel.Location = new Point(20, 597);
        this.statusLabel.Size = new Size(880, 36);
        this.headingLabel.Font = new Font("Segoe UI Semibold", 16F);

        this.searchBox.Name = "searchBox";
        this.searchBox.Location = new Point(20, 56);
        this.searchBox.Size = new Size(440, 27);

        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Location = new Point(468, 56);
        this.refreshButton.Size = new Size(96, 27);
        this.refreshButton.Text = "Refresh";
        this.refreshButton.Click += this.RefreshClicked;

        this.historyButton.Name = "historyButton";
        this.historyButton.Text = "Return register";
        this.historyButton.Location = new Point(749, 56);
        this.historyButton.Size = new Size(151, 27);
        this.historyButton.Click += this.HistoryClicked;

        this.quantityEditor.Name = "quantityEditor";
        this.quantityEditor.Location = new Point(20, 491);
        this.quantityEditor.Size = new Size(115, 27);

        this.conditionPicker.Name = "conditionPicker";
        this.conditionPicker.Location = new Point(145, 491);
        this.conditionPicker.Size = new Size(178, 27);

        this.methodBox.Name = "methodBox";
        this.methodBox.Location = new Point(333, 491);
        this.methodBox.Size = new Size(154, 27);

        this.reasonBox.Name = "reasonBox";
        this.reasonBox.Location = new Point(499, 491);
        this.reasonBox.Size = new Size(388, 27);

        this.restockCheck.Name = "restockCheck";
        this.restockCheck.Location = new Point(20, 527);
        this.restockCheck.Size = new Size(292, 25);
        this.restockCheck.Text = "Add goods back to sellable stock";

        this.recordButton.Name = "recordButton";
        this.recordButton.Location = new Point(681, 526);
        this.recordButton.Size = new Size(124, 29);
        this.recordButton.Text = "Record return";
        this.recordButton.Click += this.RecordClicked;

        this.closeButton.Name = "closeButton";
        this.closeButton.Location = new Point(816, 526);
        this.closeButton.Size = new Size(84, 29);
        this.closeButton.Text = "Close";

        this.searchBox.AccessibleName = "Search sale or invoice";
        this.searchBox.NullText = "Search sale or invoice";
        this.searchBox.MaxLength = 120;
        this.quantityEditor.DecimalPlaces = 3;
        this.quantityEditor.Maximum = 9999999M;
        this.quantityEditor.Increment = 1M;
        this.quantityEditor.AccessibleName = "Return quantity";
        this.conditionPicker.DropDownStyle = RadDropDownStyle.DropDownList;
        this.conditionPicker.SelectedValueChanged += this.ConditionChanged;
        this.conditionPicker.AccessibleName = "Condition";
        this.methodBox.MaxLength = 60;
        this.methodBox.AccessibleName = "Refund method";
        this.methodBox.Text = "cash";
        this.reasonBox.AccessibleName = "Return reason";
        this.reasonBox.MaxLength = 500;
        this.restockCheck.Checked = true;
        this.recordButton.Enabled = false;
        this.closeButton.DialogResult = DialogResult.Cancel;


        this.salesGrid.Name = "salesGrid";
        this.salesGrid.Location = new Point(20, 112);
        this.salesGrid.Size = new Size(880, 146);
        this.salesGrid.ReadOnly = true;
        this.salesGrid.MasterTemplate.AutoGenerateColumns = false;
        this.salesGrid.MasterTemplate.AllowAddNewRow = false;
        this.salesGrid.MasterTemplate.AllowDeleteRow = false;
        this.salesGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.salesGrid.SelectionChanged += this.SaleSelected;
        this.orderColumn.Name = "orderColumn";
        this.orderColumn.FieldName = "Order";
        this.orderColumn.HeaderText = "Original sale";
        this.orderColumn.Width = 136;
        this.invoiceColumn.Name = "invoiceColumn";
        this.invoiceColumn.FieldName = "Invoice";
        this.invoiceColumn.HeaderText = "Invoice";
        this.invoiceColumn.Width = 125;
        this.customerColumn.Name = "customerColumn";
        this.customerColumn.FieldName = "Customer";
        this.customerColumn.HeaderText = "Customer";
        this.customerColumn.Width = 205;
        this.currencyColumn.Name = "currencyColumn";
        this.currencyColumn.FieldName = "Currency";
        this.currencyColumn.HeaderText = "Currency";
        this.currencyColumn.Width = 90;
        this.salesGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.orderColumn, this.invoiceColumn, this.customerColumn, this.currencyColumn });

        this.linesGrid.Name = "linesGrid";
        this.linesGrid.Location = new Point(20, 290);
        this.linesGrid.Size = new Size(880, 163);
        this.linesGrid.ReadOnly = true;
        this.linesGrid.MasterTemplate.AutoGenerateColumns = false;
        this.linesGrid.MasterTemplate.AllowAddNewRow = false;
        this.linesGrid.MasterTemplate.AllowDeleteRow = false;
        this.linesGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.linesGrid.SelectionChanged += this.LineSelected;
        this.productColumn.Name = "productColumn";
        this.productColumn.FieldName = "Product";
        this.productColumn.HeaderText = "Product";
        this.productColumn.Width = 235;
        this.soldColumn.Name = "soldColumn";
        this.soldColumn.FieldName = "Sold";
        this.soldColumn.HeaderText = "Sold";
        this.soldColumn.Width = 77;
        this.soldColumn.FormatString = "{0:0.###}";
        this.returnedColumn.Name = "returnedColumn";
        this.returnedColumn.FieldName = "Returned";
        this.returnedColumn.HeaderText = "Returned";
        this.returnedColumn.Width = 83;
        this.returnedColumn.FormatString = "{0:0.###}";
        this.remainingColumn.Name = "remainingColumn";
        this.remainingColumn.FieldName = "Remaining";
        this.remainingColumn.HeaderText = "Available";
        this.remainingColumn.Width = 89;
        this.remainingColumn.FormatString = "{0:0.###}";
        this.unitColumn.Name = "unitColumn";
        this.unitColumn.FieldName = "UnitPrice";
        this.unitColumn.HeaderText = "Original rate";
        this.unitColumn.Width = 95;
        this.unitColumn.FormatString = "{0:N2}";
        this.linesGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.productColumn, this.soldColumn, this.returnedColumn, this.remainingColumn, this.unitColumn });

        this.Name = "PosReturnsForm";
        this.Text = "POS returns";
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.ClientSize = new Size(922, 640);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.AutoScaleDimensions = new SizeF(7F, 15F);
        this.StartPosition = FormStartPosition.CenterParent;
        this.CancelButton = this.closeButton;
        this.Controls.Add(this.headingLabel);
        this.Controls.Add(this.saleLabel);
        this.Controls.Add(this.linesLabel);
        this.Controls.Add(this.quantityLabel);
        this.Controls.Add(this.conditionLabel);
        this.Controls.Add(this.methodLabel);
        this.Controls.Add(this.reasonLabel);
        this.Controls.Add(this.instructionsLabel);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.searchBox);
        this.Controls.Add(this.refreshButton);
        this.Controls.Add(this.historyButton);
        this.Controls.Add(this.quantityEditor);
        this.Controls.Add(this.conditionPicker);
        this.Controls.Add(this.methodBox);
        this.Controls.Add(this.reasonBox);
        this.Controls.Add(this.restockCheck);
        this.Controls.Add(this.recordButton);
        this.Controls.Add(this.closeButton);
        this.Controls.Add(this.salesGrid);
        this.Controls.Add(this.linesGrid);
        this.Shown += this.ReturnsShown;
        this.FormClosing += this.ReturnsClosing;
        this.FormClosed += this.ReturnsClosed;
        ((ISupportInitialize)this.salesGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.salesGrid).EndInit();
        ((ISupportInitialize)this.linesGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.linesGrid).EndInit();
        ((ISupportInitialize)this.searchBox).EndInit();
        ((ISupportInitialize)this.refreshButton).EndInit();
        ((ISupportInitialize)this.historyButton).EndInit();
        ((ISupportInitialize)this.quantityEditor).EndInit();
        ((ISupportInitialize)this.conditionPicker).EndInit();
        ((ISupportInitialize)this.methodBox).EndInit();
        ((ISupportInitialize)this.reasonBox).EndInit();
        ((ISupportInitialize)this.restockCheck).EndInit();
        ((ISupportInitialize)this.recordButton).EndInit();
        ((ISupportInitialize)this.closeButton).EndInit();
        this.ResumeLayout(false);
    }

    private Label headingLabel;
    private Label saleLabel;
    private Label linesLabel;
    private Label quantityLabel;
    private Label conditionLabel;
    private Label methodLabel;
    private Label reasonLabel;
    private Label instructionsLabel;
    private Label statusLabel;
    private RadTextBox searchBox;
    private RadButton refreshButton;
    private RadButton historyButton;
    private RadSpinEditor quantityEditor;
    private RadDropDownList conditionPicker;
    private RadTextBox methodBox;
    private RadTextBox reasonBox;
    private RadCheckBox restockCheck;
    private RadButton recordButton;
    private RadButton closeButton;
    private RadGridView salesGrid;
    private GridViewTextBoxColumn orderColumn;
    private GridViewTextBoxColumn invoiceColumn;
    private GridViewTextBoxColumn customerColumn;
    private GridViewTextBoxColumn currencyColumn;
    private RadGridView linesGrid;
    private GridViewTextBoxColumn productColumn;
    private GridViewDecimalColumn soldColumn;
    private GridViewDecimalColumn returnedColumn;
    private GridViewDecimalColumn remainingColumn;
    private GridViewDecimalColumn unitColumn;
}
