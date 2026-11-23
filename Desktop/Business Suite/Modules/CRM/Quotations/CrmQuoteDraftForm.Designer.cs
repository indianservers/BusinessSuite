#nullable disable
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CrmQuoteDraftForm
{
    private void InitializeComponent()
    {
        this.titleLabel = new Label();
        this.numberLabel = new Label();
        this.numberBox = new TextBox();
        this.issueLabel = new Label();
        this.issuePicker = new DateTimePicker();
        this.expiryLabel = new Label();
        this.expiryPicker = new DateTimePicker();
        this.currencyLabel = new Label();
        this.currencyBox = new TextBox();
        this.customerLabel = new Label();
        this.customerBox = new ComboBox();
        this.dealLabel = new Label();
        this.dealBox = new ComboBox();
        this.termsLabel = new Label();
        this.termsBox = new TextBox();
        this.notesLabel = new Label();
        this.notesBox = new TextBox();
        this.addLineButton = new Button();
        this.removeLineButton = new Button();
        this.reviewButton = new Button();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.cancelButton = new Button();
        this.linesGrid = new RadGridView();
        this.NameColumn = new GridViewTextBoxColumn();
        this.QuantityColumn = new GridViewDecimalColumn();
        this.UnitPriceColumn = new GridViewDecimalColumn();
        this.DiscountTypeColumn = new GridViewTextBoxColumn();
        this.DiscountValueColumn = new GridViewDecimalColumn();
        this.TaxRateColumn = new GridViewDecimalColumn();
        ((System.ComponentModel.ISupportInitialize)this.linesGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.linesGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.titleLabel.Name = "titleLabel";
        this.titleLabel.Location = new Point(21, 13);
        this.titleLabel.Size = new Size(893, 44);
        this.titleLabel.Text = "Quotation draft";
        this.titleLabel.Font = new Font("Segoe UI Semibold", 22F);
        this.Controls.Add(this.titleLabel);

        this.numberLabel.Name = "numberLabel";
        this.numberLabel.Location = new Point(21, 66);
        this.numberLabel.Size = new Size(240, 22);
        this.numberLabel.Text = "Quotation number";
        this.Controls.Add(this.numberLabel);

        this.numberBox.Name = "numberBox";
        this.numberBox.Location = new Point(21, 90);
        this.numberBox.Size = new Size(240, 28);
        this.numberBox.MaxLength = 60;
        this.Controls.Add(this.numberBox);

        this.issueLabel.Name = "issueLabel";
        this.issueLabel.Location = new Point(277, 66);
        this.issueLabel.Size = new Size(153, 22);
        this.issueLabel.Text = "Issue date";
        this.Controls.Add(this.issueLabel);

        this.issuePicker.Name = "issuePicker";
        this.issuePicker.Location = new Point(277, 90);
        this.issuePicker.Size = new Size(153, 28);
        this.issuePicker.Format = DateTimePickerFormat.Short;
        this.Controls.Add(this.issuePicker);

        this.expiryLabel.Name = "expiryLabel";
        this.expiryLabel.Location = new Point(444, 66);
        this.expiryLabel.Size = new Size(153, 22);
        this.expiryLabel.Text = "Expiry date";
        this.Controls.Add(this.expiryLabel);

        this.expiryPicker.Name = "expiryPicker";
        this.expiryPicker.Location = new Point(444, 90);
        this.expiryPicker.Size = new Size(153, 28);
        this.expiryPicker.Format = DateTimePickerFormat.Short;
        this.Controls.Add(this.expiryPicker);

        this.currencyLabel.Name = "currencyLabel";
        this.currencyLabel.Location = new Point(611, 66);
        this.currencyLabel.Size = new Size(110, 22);
        this.currencyLabel.Text = "Currency";
        this.Controls.Add(this.currencyLabel);

        this.currencyBox.Name = "currencyBox";
        this.currencyBox.Location = new Point(611, 90);
        this.currencyBox.Size = new Size(110, 28);
        this.currencyBox.CharacterCasing = CharacterCasing.Upper;
        this.currencyBox.MaxLength = 3;
        this.Controls.Add(this.currencyBox);

        this.customerLabel.Name = "customerLabel";
        this.customerLabel.Location = new Point(21, 126);
        this.customerLabel.Size = new Size(440, 22);
        this.customerLabel.Text = "Customer";
        this.Controls.Add(this.customerLabel);

        this.customerBox.Name = "customerBox";
        this.customerBox.Location = new Point(21, 149);
        this.customerBox.Size = new Size(440, 28);
        this.customerBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.Controls.Add(this.customerBox);

        this.dealLabel.Name = "dealLabel";
        this.dealLabel.Location = new Point(478, 126);
        this.dealLabel.Size = new Size(458, 22);
        this.dealLabel.Text = "Linked deal";
        this.Controls.Add(this.dealLabel);

        this.dealBox.Name = "dealBox";
        this.dealBox.Location = new Point(478, 149);
        this.dealBox.Size = new Size(458, 28);
        this.dealBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.dealBox.SelectedIndexChanged += this.DealChanged;
        this.Controls.Add(this.dealBox);

        this.termsLabel.Name = "termsLabel";
        this.termsLabel.Location = new Point(21, 188);
        this.termsLabel.Size = new Size(440, 22);
        this.termsLabel.Text = "Terms";
        this.Controls.Add(this.termsLabel);

        this.termsBox.Name = "termsBox";
        this.termsBox.Location = new Point(21, 211);
        this.termsBox.Size = new Size(440, 75);
        this.termsBox.Multiline = true;
        this.termsBox.ScrollBars = ScrollBars.Vertical;
        this.termsBox.MaxLength = 10000;
        this.Controls.Add(this.termsBox);

        this.notesLabel.Name = "notesLabel";
        this.notesLabel.Location = new Point(478, 188);
        this.notesLabel.Size = new Size(458, 22);
        this.notesLabel.Text = "Internal notes";
        this.Controls.Add(this.notesLabel);

        this.notesBox.Name = "notesBox";
        this.notesBox.Location = new Point(478, 211);
        this.notesBox.Size = new Size(458, 75);
        this.notesBox.Multiline = true;
        this.notesBox.ScrollBars = ScrollBars.Vertical;
        this.notesBox.MaxLength = 10000;
        this.Controls.Add(this.notesBox);

        this.addLineButton.Name = "addLineButton";
        this.addLineButton.Location = new Point(21, 298);
        this.addLineButton.Size = new Size(108, 35);
        this.addLineButton.Text = "Add line";
        this.addLineButton.Click += this.AddLineClicked;
        this.addLineButton.Enabled = false;
        this.Controls.Add(this.addLineButton);

        this.removeLineButton.Name = "removeLineButton";
        this.removeLineButton.Location = new Point(141, 298);
        this.removeLineButton.Size = new Size(123, 35);
        this.removeLineButton.Text = "Remove line";
        this.removeLineButton.Click += this.RemoveLineClicked;
        this.removeLineButton.Enabled = false;
        this.Controls.Add(this.removeLineButton);

        this.reviewButton.Name = "reviewButton";
        this.reviewButton.Location = new Point(277, 298);
        this.reviewButton.Size = new Size(133, 35);
        this.reviewButton.Text = "Review totals";
        this.reviewButton.Click += this.ReviewClicked;
        this.Controls.Add(this.reviewButton);

        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(21, 574);
        this.feedback.Size = new Size(913, 44);
        this.feedback.Text = "Loading quotation…";
        this.Controls.Add(this.feedback);

        this.saveButton.Name = "saveButton";
        this.saveButton.Location = new Point(718, 618);
        this.saveButton.Size = new Size(102, 35);
        this.saveButton.Text = "Save draft";
        this.saveButton.Click += this.SaveClicked;
        this.saveButton.Enabled = false;
        this.Controls.Add(this.saveButton);

        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Location = new Point(831, 618);
        this.cancelButton.Size = new Size(105, 35);
        this.cancelButton.Text = "Cancel";
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.Add(this.cancelButton);

        this.linesGrid.Name = "linesGrid";
        this.linesGrid.Location = new Point(21, 346);
        this.linesGrid.Size = new Size(915, 215);
        this.linesGrid.MasterTemplate.AutoGenerateColumns = false;
        this.linesGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.linesGrid.MasterTemplate.AllowAddNewRow = false;
        this.linesGrid.MasterTemplate.AllowDeleteRow = false;
        this.linesGrid.ShowGroupPanel = false;
        this.linesGrid.MasterTemplate.EnableSorting = false;
        this.Controls.Add(this.linesGrid);
        this.NameColumn.Name = "Name";
        this.NameColumn.FieldName = "Name";
        this.NameColumn.HeaderText = "Line description";
        this.NameColumn.Width = 280;
        this.QuantityColumn.Name = "Quantity";
        this.QuantityColumn.FieldName = "Quantity";
        this.QuantityColumn.HeaderText = "Quantity";
        this.QuantityColumn.Width = 90;
        this.QuantityColumn.DecimalPlaces = 2;
        this.QuantityColumn.Minimum = 0;
        this.QuantityColumn.Maximum = 9999999999m;
        this.UnitPriceColumn.Name = "UnitPrice";
        this.UnitPriceColumn.FieldName = "UnitPrice";
        this.UnitPriceColumn.HeaderText = "Unit price";
        this.UnitPriceColumn.Width = 130;
        this.UnitPriceColumn.DecimalPlaces = 2;
        this.UnitPriceColumn.Minimum = 0;
        this.UnitPriceColumn.Maximum = 9999999999m;
        this.DiscountTypeColumn.Name = "DiscountType";
        this.DiscountTypeColumn.FieldName = "DiscountType";
        this.DiscountTypeColumn.HeaderText = "Discount type (amount/percent)";
        this.DiscountTypeColumn.Width = 173;
        this.DiscountValueColumn.Name = "DiscountValue";
        this.DiscountValueColumn.FieldName = "DiscountValue";
        this.DiscountValueColumn.HeaderText = "Discount";
        this.DiscountValueColumn.Width = 105;
        this.DiscountValueColumn.DecimalPlaces = 2;
        this.DiscountValueColumn.Minimum = 0;
        this.DiscountValueColumn.Maximum = 9999999999m;
        this.TaxRateColumn.Name = "TaxRate";
        this.TaxRateColumn.FieldName = "TaxRate";
        this.TaxRateColumn.HeaderText = "Tax %";
        this.TaxRateColumn.Width = 73;
        this.TaxRateColumn.DecimalPlaces = 2;
        this.TaxRateColumn.Minimum = 0;
        this.TaxRateColumn.Maximum = 100;
        this.linesGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.NameColumn, this.QuantityColumn, this.UnitPriceColumn, this.DiscountTypeColumn, this.DiscountValueColumn, this.TaxRateColumn });
        this.Text = "Business Suite | Quotation draft";
        this.Name = "CrmQuoteDraftForm";
        this.ClientSize = new Size(960, 670);
        this.StartPosition = FormStartPosition.CenterParent;
        this.Font = new Font("Segoe UI", 10F);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.AcceptButton = this.saveButton;
        this.CancelButton = this.cancelButton;
        this.Shown += this.DraftShown;
        this.FormClosing += this.DraftClosing;
        this.FormClosed += this.DraftClosed;
        ((System.ComponentModel.ISupportInitialize)this.linesGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.linesGrid).EndInit();
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label titleLabel;
    private Label numberLabel;
    private TextBox numberBox;
    private Label issueLabel;
    private DateTimePicker issuePicker;
    private Label expiryLabel;
    private DateTimePicker expiryPicker;
    private Label currencyLabel;
    private TextBox currencyBox;
    private Label customerLabel;
    private ComboBox customerBox;
    private Label dealLabel;
    private ComboBox dealBox;
    private Label termsLabel;
    private TextBox termsBox;
    private Label notesLabel;
    private TextBox notesBox;
    private Button addLineButton;
    private Button removeLineButton;
    private Button reviewButton;
    private Label feedback;
    private Button saveButton;
    private Button cancelButton;
    private RadGridView linesGrid;
    private GridViewTextBoxColumn NameColumn;
    private GridViewDecimalColumn QuantityColumn;
    private GridViewDecimalColumn UnitPriceColumn;
    private GridViewTextBoxColumn DiscountTypeColumn;
    private GridViewDecimalColumn DiscountValueColumn;
    private GridViewDecimalColumn TaxRateColumn;
}
