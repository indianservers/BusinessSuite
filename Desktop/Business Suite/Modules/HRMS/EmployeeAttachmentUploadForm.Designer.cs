using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeAttachmentUploadForm
    {
        private void InitializeComponent()
        {
            this.sourceDialog = new OpenFileDialog();
            this.documentNameLabel = new Label();
            this.kindLabel = new Label();
            this.expiryLabel = new Label();
            this.sourceLabel = new Label();
            this.status = new Label();
            this.kind = new RadDropDownList();
            this.expiry = new RadDateTimePicker();
            this.documentName = new RadTextBox();
            this.source = new RadTextBox();
            this.upload = new RadButton();
            this.browse = new RadButton();
            this.close = new RadButton();
            this.SuspendLayout();
            this.documentNameLabel.Text = "Document Name";
            this.documentNameLabel.Location = new Point(14, 14);
            this.documentNameLabel.Size = new Size(230, 24);
            this.documentName.Name = "documentName";
            this.documentName.Location = new Point(14, 39);
            this.documentName.Size = new Size(502, 25);
            this.documentName.MaxLength = 200;
            this.kindLabel.Text = "Document Type";
            this.kindLabel.Location = new Point(14, 76);
            this.kindLabel.Size = new Size(230, 22);
            this.kind.Name = "kind";
            this.kind.Location = new Point(14, 100);
            this.kind.Size = new Size(237, 27);
            this.kind.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.kind.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Education"), new RadListDataItem("Experience"),
                new RadListDataItem("Identity"), new RadListDataItem("Other") });
            this.kind.SelectedIndex = 0;
            this.expiryLabel.Text = "Expiry Date";
            this.expiryLabel.Location = new Point(274, 76);
            this.expiryLabel.Size = new Size(242, 22);
            this.expiry.Name = "expiry";
            this.expiry.Location = new Point(274, 100);
            this.expiry.Size = new Size(242, 27);
            this.expiry.Format = DateTimePickerFormat.Short;
            this.expiry.ShowCheckBox = true;
            this.expiry.Checked = false;
            this.sourceLabel.Text = "Document File";
            this.sourceLabel.Location = new Point(14, 142);
            this.sourceLabel.Size = new Size(230, 22);
            this.source.Name = "source";
            this.source.Location = new Point(14, 166);
            this.source.Size = new Size(404, 25);
            this.source.ReadOnly = true;
            this.browse.Name = "browse";
            this.browse.Text = "Browse…";
            this.browse.Location = new Point(428, 164);
            this.browse.Size = new Size(88, 28);
            this.browse.Click += this.BrowseClicked;
            this.status.Location = new Point(14, 204);
            this.status.Size = new Size(502, 38);
            this.status.Text = "Choose a PDF, Word document or image up to 10 MB.";
            this.upload.Name = "upload";
            this.upload.Text = "Upload document";
            this.upload.Location = new Point(279, 250);
            this.upload.Size = new Size(138, 29);
            this.upload.Enabled = false;
            this.upload.Click += this.UploadClicked;
            this.close.Name = "close";
            this.close.Text = "Cancel";
            this.close.Location = new Point(428, 250);
            this.close.Size = new Size(88, 29);
            this.close.DialogResult = DialogResult.Cancel;
            this.sourceDialog.CheckFileExists = true;
            this.sourceDialog.Filter = "Employee documents (*.pdf;*.doc;*.docx;*.jpg;*.jpeg;*.png)|*.pdf;*.doc;*.docx;*.jpg;*.jpeg;*.png";
            this.sourceDialog.Title = "Choose employee document";
            this.Controls.AddRange(new Control[] {
                this.documentNameLabel, this.documentName, this.kindLabel, this.kind,
                this.expiryLabel, this.expiry, this.sourceLabel, this.source,
                this.status, this.browse, this.upload, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(532, 295);
            this.StartPosition = FormStartPosition.CenterParent;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.Text = "Upload Employee Document";
            this.ResumeLayout(false);
        }

        private OpenFileDialog sourceDialog;
        private Label documentNameLabel, kindLabel, expiryLabel, sourceLabel, status;
        private RadTextBox documentName, source;
        private RadDropDownList kind;
        private RadDateTimePicker expiry;
        private RadButton upload, browse, close;
    }
}
