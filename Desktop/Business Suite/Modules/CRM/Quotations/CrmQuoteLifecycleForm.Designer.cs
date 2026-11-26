#nullable disable
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CrmQuoteLifecycleForm
{
    private void InitializeComponent()
    {
        this.titleLabel = new Label();
        this.summary = new Label();
        this.linesGrid = new RadGridView();
        this.termsLabel = new Label();
        this.termsBox = new TextBox();
        this.actionLabel = new Label();
        this.actionBox = new ComboBox();
        this.commentsLabel = new Label();
        this.commentsBox = new TextBox();
        this.feedback = new Label();
        this.applyButton = new Button();
        this.doneButton = new Button();
        this.exportPdfButton = new Button();
        this.issuePdfButton = new Button();
        this.pdfDialog = new SaveFileDialog();
        this.nameColumn = new GridViewTextBoxColumn();
        this.quantityColumn = new GridViewDecimalColumn();
        this.priceColumn = new GridViewDecimalColumn();
        this.discountTypeColumn = new GridViewTextBoxColumn();
        this.discountColumn = new GridViewDecimalColumn();
        this.taxColumn = new GridViewDecimalColumn();
        ((System.ComponentModel.ISupportInitialize)this.linesGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.linesGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.titleLabel.Name = "titleLabel";
        this.titleLabel.Location = new Point(21, 14);
        this.titleLabel.Size = new Size(720, 46);
        this.titleLabel.Text = "Quotation review";
        this.titleLabel.Font = new Font("Segoe UI Semibold", 22F);
        this.Controls.Add(this.titleLabel);

        this.summary.Name = "summary";
        this.summary.Location = new Point(21, 69);
        this.summary.Size = new Size(720, 26);
        this.Controls.Add(this.summary);

        this.linesGrid.Name = "linesGrid";
        this.linesGrid.Location = new Point(21, 104);
        this.linesGrid.Size = new Size(720, 211);
        this.linesGrid.ReadOnly = true;
        this.linesGrid.ShowGroupPanel = false;
        this.linesGrid.MasterTemplate.AutoGenerateColumns = false;
        this.linesGrid.MasterTemplate.AllowAddNewRow = false;
        this.linesGrid.MasterTemplate.AllowDeleteRow = false;
        this.linesGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.Controls.Add(this.linesGrid);

        this.termsLabel.Name = "termsLabel";
        this.termsLabel.Location = new Point(21, 326);
        this.termsLabel.Size = new Size(720, 22);
        this.termsLabel.Text = "Quotation terms";
        this.Controls.Add(this.termsLabel);

        this.termsBox.Name = "termsBox";
        this.termsBox.Location = new Point(21, 351);
        this.termsBox.Size = new Size(720, 53);
        this.termsBox.ReadOnly = true;
        this.termsBox.Multiline = true;
        this.termsBox.ScrollBars = ScrollBars.Vertical;
        this.Controls.Add(this.termsBox);

        this.actionLabel.Name = "actionLabel";
        this.actionLabel.Location = new Point(21, 416);
        this.actionLabel.Size = new Size(300, 22);
        this.actionLabel.Text = "Action";
        this.Controls.Add(this.actionLabel);

        this.actionBox.Name = "actionBox";
        this.actionBox.Location = new Point(21, 441);
        this.actionBox.Size = new Size(261, 28);
        this.actionBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.actionBox.Enabled = false;
        this.actionBox.SelectedIndexChanged += this.ActionChanged;
        this.Controls.Add(this.actionBox);

        this.commentsLabel.Name = "commentsLabel";
        this.commentsLabel.Location = new Point(300, 416);
        this.commentsLabel.Size = new Size(441, 22);
        this.commentsLabel.Text = "Review comments";
        this.Controls.Add(this.commentsLabel);

        this.commentsBox.Name = "commentsBox";
        this.commentsBox.Location = new Point(300, 441);
        this.commentsBox.Size = new Size(441, 54);
        this.commentsBox.Multiline = true;
        this.commentsBox.MaxLength = 2000;
        this.Controls.Add(this.commentsBox);

        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(21, 504);
        this.feedback.Size = new Size(720, 40);
        this.feedback.Text = "Loading quotation…";
        this.Controls.Add(this.feedback);

        this.exportPdfButton.Name = "exportPdfButton";
        this.exportPdfButton.Location = new Point(21, 554);
        this.exportPdfButton.Size = new Size(169, 35);
        this.exportPdfButton.Text = "Export draft PDF";
        this.exportPdfButton.Enabled = false;
        this.exportPdfButton.Click += this.ExportPdfClicked;
        this.Controls.Add(this.exportPdfButton);

        this.issuePdfButton.Name = "issuePdfButton";
        this.issuePdfButton.Location = new Point(203, 554);
        this.issuePdfButton.Size = new Size(151, 35);
        this.issuePdfButton.Text = "Issue quotation PDF";
        this.issuePdfButton.Enabled = false;
        this.issuePdfButton.Click += this.IssuePdfClicked;
        this.Controls.Add(this.issuePdfButton);

        this.pdfDialog.DefaultExt = "pdf";
        this.pdfDialog.Filter = "PDF files (*.pdf)|*.pdf";
        this.pdfDialog.Title = "Save quotation PDF copy";
        this.pdfDialog.OverwritePrompt = true;
        this.pdfDialog.RestoreDirectory = true;

        this.applyButton.Name = "applyButton";
        this.applyButton.Location = new Point(524, 554);
        this.applyButton.Size = new Size(101, 35);
        this.applyButton.Text = "Apply action";
        this.applyButton.Enabled = false;
        this.applyButton.Click += this.ApplyClicked;
        this.Controls.Add(this.applyButton);

        this.doneButton.Name = "doneButton";
        this.doneButton.Location = new Point(640, 554);
        this.doneButton.Size = new Size(101, 35);
        this.doneButton.Text = "Done";
        this.doneButton.DialogResult = DialogResult.Cancel;
        this.Controls.Add(this.doneButton);
        this.nameColumn.Name = "nameColumn";
        this.nameColumn.FieldName = "Name";
        this.nameColumn.HeaderText = "Line description";
        this.nameColumn.Width = 190;
        this.quantityColumn.Name = "quantityColumn";
        this.quantityColumn.FieldName = "Quantity";
        this.quantityColumn.HeaderText = "Quantity";
        this.quantityColumn.Width = 75;
        this.priceColumn.Name = "priceColumn";
        this.priceColumn.FieldName = "UnitPrice";
        this.priceColumn.HeaderText = "Unit price";
        this.priceColumn.Width = 110;
        this.discountTypeColumn.Name = "discountTypeColumn";
        this.discountTypeColumn.FieldName = "DiscountType";
        this.discountTypeColumn.HeaderText = "Discount type";
        this.discountTypeColumn.Width = 104;
        this.discountColumn.Name = "discountColumn";
        this.discountColumn.FieldName = "DiscountValue";
        this.discountColumn.HeaderText = "Discount";
        this.discountColumn.Width = 90;
        this.taxColumn.Name = "taxColumn";
        this.taxColumn.FieldName = "TaxRate";
        this.taxColumn.HeaderText = "Tax %";
        this.taxColumn.Width = 70;
        this.linesGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.nameColumn, this.quantityColumn, this.priceColumn, this.discountTypeColumn, this.discountColumn, this.taxColumn });
        this.Text = "Business Suite | Quotation review";
        this.Name = "CrmQuoteLifecycleForm";
        this.ClientSize = new Size(762, 609);
        this.StartPosition = FormStartPosition.CenterParent;
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.Font = new Font("Segoe UI", 10F);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.CancelButton = this.doneButton;
        this.Shown += this.ReviewShown;
        this.FormClosed += this.ReviewClosed;
        this.FormClosing += this.ReviewClosing;
        ((System.ComponentModel.ISupportInitialize)this.linesGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.linesGrid).EndInit();
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label titleLabel;
    private Label summary;
    private RadGridView linesGrid;
    private Label termsLabel;
    private TextBox termsBox;
    private Label actionLabel;
    private ComboBox actionBox;
    private Label commentsLabel;
    private TextBox commentsBox;
    private Label feedback;
    private Button applyButton;
    private Button doneButton;
    private Button exportPdfButton;
    private Button issuePdfButton;
    private SaveFileDialog pdfDialog;
    private GridViewTextBoxColumn nameColumn;
    private GridViewDecimalColumn quantityColumn;
    private GridViewDecimalColumn priceColumn;
    private GridViewTextBoxColumn discountTypeColumn;
    private GridViewDecimalColumn discountColumn;
    private GridViewDecimalColumn taxColumn;
}
