using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CommunicationMergePreviewForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        grid = new RadGridView();
        grid.Name = "grid";
        grid.Location = new Point(20, 18);
        grid.Size = new Size(676, 193);
        grid.ShowGroupPanel = false;
        grid.MasterTemplate.AllowAddNewRow = false;
        grid.MasterTemplate.AllowDeleteRow = false;
        grid.MasterTemplate.AutoGenerateColumns = false;
        grid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        grid.CellEndEdit += PreviewChanged;
        Controls.Add(grid);
        previewLabel = new Label();
        previewLabel.Name = "previewLabel";
        previewLabel.Location = new Point(20, 223);
        previewLabel.Size = new Size(640, 24);
        previewLabel.Text = "Email preview";
        Controls.Add(previewLabel);
        previewBox = new RadTextBox();
        previewBox.Name = "previewBox";
        previewBox.Location = new Point(20, 251);
        previewBox.Size = new Size(676, 237);
        previewBox.Multiline = true;
        previewBox.ReadOnly = true;
        previewBox.ScrollBars = ScrollBars.Vertical;
        previewBox.AccessibleName = "Rendered email preview";
        Controls.Add(previewBox);
        feedback = new Label();
        feedback.Name = "feedback";
        feedback.Location = new Point(20, 495);
        feedback.Size = new Size(676, 28);
        Controls.Add(feedback);
        acceptButton = new RadButton();
        acceptButton.Name = "acceptButton";
        acceptButton.Location = new Point(449, 532);
        acceptButton.Size = new Size(128, 30);
        acceptButton.Text = "Use values";
        acceptButton.Click += AcceptClicked;
        Controls.Add(acceptButton);
        cancelButton = new RadButton();
        cancelButton.Name = "cancelButton";
        cancelButton.Location = new Point(591, 532);
        cancelButton.Size = new Size(105, 30);
        cancelButton.Text = "Cancel";
        cancelButton.DialogResult = DialogResult.Cancel;
        Controls.Add(cancelButton);
        var fieldColumn = new GridViewTextBoxColumn();
        fieldColumn.Name = "fieldColumn";
        fieldColumn.FieldName = "Field";
        fieldColumn.HeaderText = "Template field";
        fieldColumn.Width = 185;
        fieldColumn.ReadOnly = true;
        grid.MasterTemplate.Columns.Add(fieldColumn);
        var valueColumn = new GridViewTextBoxColumn();
        valueColumn.Name = "valueColumn";
        valueColumn.FieldName = "Value";
        valueColumn.HeaderText = "Value";
        valueColumn.Width = 475;
        grid.MasterTemplate.Columns.Add(valueColumn);
        CancelButton = cancelButton;
        ClientSize = new Size(716, 580);
        AutoScaleDimensions = new SizeF(7F, 15F);
        AutoScaleMode = AutoScaleMode.Font;
        Font = new Font("Segoe UI", 9F);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        Name = "CommunicationMergePreviewForm";
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.CenterParent;
        Text = "Email merge fields and preview";
        ResumeLayout(false);
        PerformLayout();
    }

    private RadGridView grid;
    private Label previewLabel;
    private RadTextBox previewBox;
    private Label feedback;
    private RadButton acceptButton;
    private RadButton cancelButton;
 }
