using System.ComponentModel;
using Telerik.WinControls;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class PosSplitTenderForm
{
    private void InitializeComponent()
    {
        this.headingLabel = new Label();
        this.summaryLabel = new Label();
        this.methodLabel = new Label();
        this.amountLabel = new Label();
        this.referenceLabel = new Label();
        this.statusLabel = new Label();
        this.methodPicker = new RadDropDownList();
        this.amountEditor = new RadSpinEditor();
        this.referenceBox = new RadTextBox();
        this.addButton = new RadButton();
        this.removeButton = new RadButton();
        this.confirmButton = new RadButton();
        this.closeButton = new RadButton();
        this.paymentGrid = new RadGridView();
        this.methodColumn = new GridViewTextBoxColumn();
        this.amountColumn = new GridViewDecimalColumn();
        this.referenceColumn = new GridViewTextBoxColumn();
        ((ISupportInitialize)this.methodPicker).BeginInit();
        ((ISupportInitialize)this.amountEditor).BeginInit();
        ((ISupportInitialize)this.referenceBox).BeginInit();
        ((ISupportInitialize)this.addButton).BeginInit();
        ((ISupportInitialize)this.removeButton).BeginInit();
        ((ISupportInitialize)this.confirmButton).BeginInit();
        ((ISupportInitialize)this.closeButton).BeginInit();
        ((ISupportInitialize)this.paymentGrid).BeginInit();
        ((ISupportInitialize)this.paymentGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.headingLabel.Name = "headingLabel";
        this.headingLabel.Text = "Split payment";
        this.headingLabel.Location = new Point(20, 14);
        this.headingLabel.Size = new Size(611, 32);

        this.summaryLabel.Name = "summaryLabel";
        this.summaryLabel.Text = "";
        this.summaryLabel.Location = new Point(20, 48);
        this.summaryLabel.Size = new Size(611, 29);

        this.methodLabel.Name = "methodLabel";
        this.methodLabel.Text = "Payment method";
        this.methodLabel.Location = new Point(20, 282);
        this.methodLabel.Size = new Size(170, 21);

        this.amountLabel.Name = "amountLabel";
        this.amountLabel.Text = "Amount";
        this.amountLabel.Location = new Point(205, 282);
        this.amountLabel.Size = new Size(116, 21);

        this.referenceLabel.Name = "referenceLabel";
        this.referenceLabel.Text = "Reference";
        this.referenceLabel.Location = new Point(334, 282);
        this.referenceLabel.Size = new Size(192, 21);

        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Text = "";
        this.statusLabel.Location = new Point(20, 385);
        this.statusLabel.Size = new Size(611, 27);
        this.headingLabel.Font = new Font("Segoe UI Semibold", 16F);

        this.methodPicker.Name = "methodPicker";
        this.methodPicker.Location = new Point(20, 305);
        this.methodPicker.Size = new Size(173, 28);

        this.amountEditor.Name = "amountEditor";
        this.amountEditor.Location = new Point(205, 305);
        this.amountEditor.Size = new Size(116, 28);

        this.referenceBox.Name = "referenceBox";
        this.referenceBox.Location = new Point(334, 305);
        this.referenceBox.Size = new Size(192, 28);

        this.addButton.Name = "addButton";
        this.addButton.Location = new Point(540, 304);
        this.addButton.Size = new Size(91, 27);
        this.addButton.Text = "Add";
        this.addButton.Click += this.AddClicked;

        this.removeButton.Name = "removeButton";
        this.removeButton.Location = new Point(20, 350);
        this.removeButton.Size = new Size(137, 28);
        this.removeButton.Text = "Remove payment";
        this.removeButton.Click += this.RemoveClicked;

        this.confirmButton.Name = "confirmButton";
        this.confirmButton.Location = new Point(333, 417);
        this.confirmButton.Size = new Size(193, 29);
        this.confirmButton.Text = "Complete split checkout";
        this.confirmButton.Click += this.ConfirmClicked;

        this.closeButton.Name = "closeButton";
        this.closeButton.Location = new Point(539, 417);
        this.closeButton.Size = new Size(92, 29);
        this.closeButton.Text = "Back";

        this.methodPicker.DropDownStyle = RadDropDownStyle.DropDownList;
        this.methodPicker.SelectedValueChanged += this.MethodChanged;
        this.methodPicker.AccessibleName = "Payment method";
        this.amountEditor.DecimalPlaces = 2;
        this.amountEditor.Maximum = 99999999999M;
        this.amountEditor.Increment = 0.01M;
        this.amountEditor.AccessibleName = "Amount";
        this.referenceBox.MaxLength = 120;
        this.referenceBox.AccessibleName = "Reference";
        this.closeButton.DialogResult = DialogResult.Cancel;
        this.confirmButton.Enabled = false;
        this.removeButton.Enabled = false;

        this.paymentGrid.Name = "paymentGrid";
        this.paymentGrid.Location = new Point(20, 87);
        this.paymentGrid.Size = new Size(611, 183);
        this.paymentGrid.ReadOnly = true;
        this.paymentGrid.MasterTemplate.AutoGenerateColumns = false;
        this.paymentGrid.MasterTemplate.AllowAddNewRow = false;
        this.paymentGrid.MasterTemplate.AllowDeleteRow = false;
        this.paymentGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.paymentGrid.SelectionChanged += this.SelectionChanged;
        this.methodColumn.Name = "methodColumn";
        this.methodColumn.FieldName = "MethodLabel";
        this.methodColumn.HeaderText = "Payment method";
        this.methodColumn.Width = 176;
        this.amountColumn.Name = "amountColumn";
        this.amountColumn.FieldName = "Amount";
        this.amountColumn.HeaderText = "Amount";
        this.amountColumn.FormatString = "{0:N2}";
        this.amountColumn.Width = 127;
        this.referenceColumn.Name = "referenceColumn";
        this.referenceColumn.FieldName = "Reference";
        this.referenceColumn.HeaderText = "Reference";
        this.referenceColumn.Width = 277;
        this.paymentGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.methodColumn,this.amountColumn,this.referenceColumn });

        this.Name = "PosSplitTenderForm";
        this.Text = "Split payment";
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.ClientSize = new Size(651, 465);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.AutoScaleDimensions = new SizeF(7F, 15F);
        this.StartPosition = FormStartPosition.CenterParent;
        this.CancelButton = this.closeButton;
        this.Controls.Add(this.headingLabel);
        this.Controls.Add(this.summaryLabel);
        this.Controls.Add(this.methodLabel);
        this.Controls.Add(this.amountLabel);
        this.Controls.Add(this.referenceLabel);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.methodPicker);
        this.Controls.Add(this.amountEditor);
        this.Controls.Add(this.referenceBox);
        this.Controls.Add(this.addButton);
        this.Controls.Add(this.removeButton);
        this.Controls.Add(this.confirmButton);
        this.Controls.Add(this.closeButton);
        this.Controls.Add(this.paymentGrid);
        ((ISupportInitialize)this.paymentGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.paymentGrid).EndInit();
        ((ISupportInitialize)this.methodPicker).EndInit();
        ((ISupportInitialize)this.amountEditor).EndInit();
        ((ISupportInitialize)this.referenceBox).EndInit();
        ((ISupportInitialize)this.addButton).EndInit();
        ((ISupportInitialize)this.removeButton).EndInit();
        ((ISupportInitialize)this.confirmButton).EndInit();
        ((ISupportInitialize)this.closeButton).EndInit();
        this.ResumeLayout(false);
    }

    private Label headingLabel;
    private Label summaryLabel;
    private Label methodLabel;
    private Label amountLabel;
    private Label referenceLabel;
    private Label statusLabel;
    private RadDropDownList methodPicker;
    private RadSpinEditor amountEditor;
    private RadTextBox referenceBox;
    private RadButton addButton;
    private RadButton removeButton;
    private RadButton confirmButton;
    private RadButton closeButton;
    private RadGridView paymentGrid;
    private GridViewTextBoxColumn methodColumn;
    private GridViewDecimalColumn amountColumn;
    private GridViewTextBoxColumn referenceColumn;
}
