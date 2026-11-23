#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class CrmExtrasForm
    {
        private void InitializeComponent()
        {
            this.layoutTabs = new TabControl();
            this.customPage = new TabPage();
            this.customGrid = new RadGridView();
            this.customLabelColumn = new GridViewTextBoxColumn();
            this.customKindColumn = new GridViewTextBoxColumn();
            this.customRequiredColumn = new GridViewCheckBoxColumn();
            this.customChoicesColumn = new GridViewTextBoxColumn();
            this.customValueColumn = new GridViewTextBoxColumn();
            this.taxPage = new TabPage();
            this.taxGrid = new RadGridView();
            this.taxTypeColumn = new GridViewTextBoxColumn();
            this.taxCountryColumn = new GridViewTextBoxColumn();
            this.taxNumberColumn = new GridViewTextBoxColumn();
            this.taxAddButton = new Button();
            this.taxRemoveButton = new Button();
            this.channelPage = new TabPage();
            this.channelGrid = new RadGridView();
            this.channelKindColumn = new GridViewTextBoxColumn();
            this.channelLabelColumn = new GridViewTextBoxColumn();
            this.channelValueColumn = new GridViewTextBoxColumn();
            this.channelCountryCodeColumn = new GridViewComboBoxColumn();
            this.channelPrimaryColumn = new GridViewCheckBoxColumn();
            this.channelWhatsAppColumn = new GridViewCheckBoxColumn();
            this.channelVerificationColumn = new GridViewTextBoxColumn();
            this.channelNotesColumn = new GridViewTextBoxColumn();
            this.channelAddButton = new Button();
            this.channelRemoveButton = new Button();
            this.customHint = new Label();
            this.gstLabel = new Label();
            this.gstBox = new TextBox();
            this.feedbackLabel = new Label();
            this.applyButton = new Button();
            this.cancelButton = new Button();
            ((System.ComponentModel.ISupportInitialize)this.customGrid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.taxGrid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.channelGrid).BeginInit();
            this.SuspendLayout();
            // layoutTabs
            this.layoutTabs.Location = new Point(18, 18);
            this.layoutTabs.Size = new Size(1004, 464);
            this.layoutTabs.Name = "layoutTabs";
            this.layoutTabs.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            // customPage
            this.customPage.Name = "customPage";
            this.customPage.Text = "Custom fields";
            this.customPage.UseVisualStyleBackColor = true;
            // customGrid
            this.customGrid.Location = new Point(13, 45);
            this.customGrid.Size = new Size(963, 330);
            this.customGrid.Name = "customGrid";
            this.customGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.customGrid.MasterTemplate.AllowAddNewRow = false;
            this.customGrid.MasterTemplate.AllowDeleteRow = false;
            this.customGrid.MasterTemplate.AutoGenerateColumns = false;
            this.customGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
            this.customGrid.ShowGroupPanel = false;
            // customLabelColumn
            this.customLabelColumn.Name = "customLabelColumn";
            this.customLabelColumn.FieldName = "Label";
            this.customLabelColumn.HeaderText = "Field";
            this.customLabelColumn.Width = 190;
            this.customLabelColumn.ReadOnly = true;
            // customKindColumn
            this.customKindColumn.Name = "customKindColumn";
            this.customKindColumn.FieldName = "Kind";
            this.customKindColumn.HeaderText = "Type";
            this.customKindColumn.Width = 108;
            this.customKindColumn.ReadOnly = true;
            // customRequiredColumn
            this.customRequiredColumn.Name = "customRequiredColumn";
            this.customRequiredColumn.FieldName = "Required";
            this.customRequiredColumn.HeaderText = "Required";
            this.customRequiredColumn.Width = 74;
            this.customRequiredColumn.ReadOnly = true;
            // customChoicesColumn
            this.customChoicesColumn.Name = "customChoicesColumn";
            this.customChoicesColumn.FieldName = "Choices";
            this.customChoicesColumn.HeaderText = "Options";
            this.customChoicesColumn.Width = 208;
            this.customChoicesColumn.ReadOnly = true;
            // customValueColumn
            this.customValueColumn.Name = "customValueColumn";
            this.customValueColumn.FieldName = "Value";
            this.customValueColumn.HeaderText = "Value";
            this.customValueColumn.Width = 300;
            this.customValueColumn.ReadOnly = false;
            // taxPage
            this.taxPage.Name = "taxPage";
            this.taxPage.Text = "Tax registrations";
            this.taxPage.UseVisualStyleBackColor = true;
            // taxGrid
            this.taxGrid.Location = new Point(13, 45);
            this.taxGrid.Size = new Size(963, 330);
            this.taxGrid.Name = "taxGrid";
            this.taxGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.taxGrid.MasterTemplate.AllowAddNewRow = false;
            this.taxGrid.MasterTemplate.AllowDeleteRow = false;
            this.taxGrid.MasterTemplate.AutoGenerateColumns = false;
            this.taxGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
            this.taxGrid.ShowGroupPanel = false;
            // taxTypeColumn
            this.taxTypeColumn.Name = "taxTypeColumn";
            this.taxTypeColumn.FieldName = "Type";
            this.taxTypeColumn.HeaderText = "Type";
            this.taxTypeColumn.Width = 150;
            this.taxTypeColumn.ReadOnly = false;
            // taxCountryColumn
            this.taxCountryColumn.Name = "taxCountryColumn";
            this.taxCountryColumn.FieldName = "Country";
            this.taxCountryColumn.HeaderText = "Country";
            this.taxCountryColumn.Width = 180;
            this.taxCountryColumn.ReadOnly = false;
            // taxNumberColumn
            this.taxNumberColumn.Name = "taxNumberColumn";
            this.taxNumberColumn.FieldName = "Number";
            this.taxNumberColumn.HeaderText = "Registration number";
            this.taxNumberColumn.Width = 490;
            this.taxNumberColumn.ReadOnly = false;
            // taxAddButton
            this.taxAddButton.Location = new Point(13, 7);
            this.taxAddButton.Size = new Size(100, 31);
            this.taxAddButton.Name = "taxAddButton";
            this.taxAddButton.Text = "Add";
            this.taxAddButton.Click += this.taxAddClicked;
            // taxRemoveButton
            this.taxRemoveButton.Location = new Point(117, 7);
            this.taxRemoveButton.Size = new Size(100, 31);
            this.taxRemoveButton.Name = "taxRemoveButton";
            this.taxRemoveButton.Text = "Remove";
            this.taxRemoveButton.Click += this.taxRemoveClicked;
            // channelPage
            this.channelPage.Name = "channelPage";
            this.channelPage.Text = "Communication channels";
            this.channelPage.UseVisualStyleBackColor = true;
            // channelGrid
            this.channelGrid.Location = new Point(13, 45);
            this.channelGrid.Size = new Size(963, 330);
            this.channelGrid.Name = "channelGrid";
            this.channelGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.channelGrid.MasterTemplate.AllowAddNewRow = false;
            this.channelGrid.MasterTemplate.AllowDeleteRow = false;
            this.channelGrid.MasterTemplate.AutoGenerateColumns = false;
            this.channelGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
            this.channelGrid.ShowGroupPanel = false;
            // channelKindColumn
            this.channelKindColumn.Name = "channelKindColumn";
            this.channelKindColumn.FieldName = "Kind";
            this.channelKindColumn.HeaderText = "Kind";
            this.channelKindColumn.Width = 75;
            this.channelKindColumn.ReadOnly = false;
            // channelLabelColumn
            this.channelLabelColumn.Name = "channelLabelColumn";
            this.channelLabelColumn.FieldName = "Label";
            this.channelLabelColumn.HeaderText = "Label";
            this.channelLabelColumn.Width = 110;
            this.channelLabelColumn.ReadOnly = false;
            // channelValueColumn
            this.channelValueColumn.Name = "channelValueColumn";
            this.channelValueColumn.FieldName = "Value";
            this.channelValueColumn.HeaderText = "Value";
            this.channelValueColumn.Width = 210;
            this.channelValueColumn.ReadOnly = false;
            // channelCountryCodeColumn
            this.channelCountryCodeColumn.Name = "channelCountryCodeColumn";
            this.channelCountryCodeColumn.FieldName = "CountryCode";
            this.channelCountryCodeColumn.HeaderText = "Calling code";
            this.channelCountryCodeColumn.Width = 80;
            this.channelCountryCodeColumn.ReadOnly = false;
            // channelPrimaryColumn
            this.channelPrimaryColumn.Name = "channelPrimaryColumn";
            this.channelPrimaryColumn.FieldName = "Primary";
            this.channelPrimaryColumn.HeaderText = "Primary";
            this.channelPrimaryColumn.Width = 66;
            this.channelPrimaryColumn.ReadOnly = false;
            // channelWhatsAppColumn
            this.channelWhatsAppColumn.Name = "channelWhatsAppColumn";
            this.channelWhatsAppColumn.FieldName = "WhatsApp";
            this.channelWhatsAppColumn.HeaderText = "WhatsApp";
            this.channelWhatsAppColumn.Width = 74;
            this.channelWhatsAppColumn.ReadOnly = false;
            // channelVerificationColumn
            this.channelVerificationColumn.Name = "channelVerificationColumn";
            this.channelVerificationColumn.FieldName = "Verification";
            this.channelVerificationColumn.HeaderText = "Verification";
            this.channelVerificationColumn.Width = 110;
            this.channelVerificationColumn.ReadOnly = true;
            // channelNotesColumn
            this.channelNotesColumn.Name = "channelNotesColumn";
            this.channelNotesColumn.FieldName = "Notes";
            this.channelNotesColumn.HeaderText = "Notes";
            this.channelNotesColumn.Width = 220;
            this.channelNotesColumn.ReadOnly = false;
            // channelAddButton
            this.channelAddButton.Location = new Point(13, 7);
            this.channelAddButton.Size = new Size(100, 31);
            this.channelAddButton.Name = "channelAddButton";
            this.channelAddButton.Text = "Add";
            this.channelAddButton.Click += this.channelAddClicked;
            // channelRemoveButton
            this.channelRemoveButton.Location = new Point(117, 7);
            this.channelRemoveButton.Size = new Size(100, 31);
            this.channelRemoveButton.Name = "channelRemoveButton";
            this.channelRemoveButton.Text = "Remove";
            this.channelRemoveButton.Click += this.channelRemoveClicked;
            // customHint
            this.customHint.Location = new Point(13, 8);
            this.customHint.Size = new Size(960, 30);
            this.customHint.Name = "customHint";
            this.customHint.Text = "Enter dates as YYYY-MM-DD, multiple choices separated by commas, and structured phone values as JSON.";
            // gstLabel
            this.gstLabel.Location = new Point(13, 12);
            this.gstLabel.Size = new Size(350, 25);
            this.gstLabel.Name = "gstLabel";
            this.gstLabel.Text = "GSTIN";
            // gstBox
            this.gstBox.Location = new Point(13, 44);
            this.gstBox.Size = new Size(380, 31);
            this.gstBox.Name = "gstBox";
            this.gstBox.MaxLength = 15;
            this.gstBox.AccessibleName = "Contact GSTIN";
            // feedbackLabel
            this.feedbackLabel.Location = new Point(18, 486);
            this.feedbackLabel.Size = new Size(720, 55);
            this.feedbackLabel.Name = "feedbackLabel";
            this.feedbackLabel.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.feedbackLabel.TextAlign = ContentAlignment.MiddleLeft;
            // applyButton
            this.applyButton.Location = new Point(791, 493);
            this.applyButton.Size = new Size(109, 39);
            this.applyButton.Name = "applyButton";
            this.applyButton.Text = "Apply";
            this.applyButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.applyButton.Click += this.ApplyClicked;
            // cancelButton
            this.cancelButton.Location = new Point(913, 493);
            this.cancelButton.Size = new Size(109, 39);
            this.cancelButton.Name = "cancelButton";
            this.cancelButton.Text = "Cancel";
            this.cancelButton.DialogResult = DialogResult.Cancel;
            this.cancelButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.layoutTabs.TabPages.Add(this.customPage);
            this.customGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.customLabelColumn, this.customKindColumn, this.customRequiredColumn, this.customChoicesColumn, this.customValueColumn });
            this.layoutTabs.TabPages.Add(this.taxPage);
            this.taxGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.taxTypeColumn, this.taxCountryColumn, this.taxNumberColumn });
            this.layoutTabs.TabPages.Add(this.channelPage);
            this.channelGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.channelKindColumn, this.channelLabelColumn, this.channelValueColumn, this.channelCountryCodeColumn, this.channelPrimaryColumn, this.channelWhatsAppColumn, this.channelVerificationColumn, this.channelNotesColumn });
            this.Controls.Add(this.layoutTabs);
            this.customPage.Controls.Add(this.customGrid);
            this.taxPage.Controls.Add(this.taxGrid);
            this.taxPage.Controls.Add(this.taxAddButton);
            this.taxPage.Controls.Add(this.taxRemoveButton);
            this.channelPage.Controls.Add(this.channelGrid);
            this.channelPage.Controls.Add(this.channelAddButton);
            this.channelPage.Controls.Add(this.channelRemoveButton);
            this.customPage.Controls.Add(this.customHint);
            this.taxPage.Controls.Add(this.gstLabel);
            this.taxPage.Controls.Add(this.gstBox);
            this.Controls.Add(this.feedbackLabel);
            this.Controls.Add(this.applyButton);
            this.Controls.Add(this.cancelButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.Font = new Font("Segoe UI", 10F);
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ForeColor = Color.FromArgb(24, 35, 58);
            this.Text = "Business Suite | CRM record details";
            this.ClientSize = new Size(1040, 556);
            this.MinimumSize = new Size(800, 450);
            this.StartPosition = FormStartPosition.CenterParent;
            this.CancelButton = this.cancelButton;
            this.Name = "CrmExtrasForm";
            ((System.ComponentModel.ISupportInitialize)this.customGrid).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.taxGrid).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.channelGrid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private TabControl layoutTabs;
        private TabPage customPage;
        private RadGridView customGrid;
        private GridViewTextBoxColumn customLabelColumn;
        private GridViewTextBoxColumn customKindColumn;
        private GridViewCheckBoxColumn customRequiredColumn;
        private GridViewTextBoxColumn customChoicesColumn;
        private GridViewTextBoxColumn customValueColumn;
        private TabPage taxPage;
        private RadGridView taxGrid;
        private GridViewTextBoxColumn taxTypeColumn;
        private GridViewTextBoxColumn taxCountryColumn;
        private GridViewTextBoxColumn taxNumberColumn;
        private Button taxAddButton;
        private Button taxRemoveButton;
        private TabPage channelPage;
        private RadGridView channelGrid;
        private GridViewTextBoxColumn channelKindColumn;
        private GridViewTextBoxColumn channelLabelColumn;
        private GridViewTextBoxColumn channelValueColumn;
        private GridViewComboBoxColumn channelCountryCodeColumn;
        private GridViewCheckBoxColumn channelPrimaryColumn;
        private GridViewCheckBoxColumn channelWhatsAppColumn;
        private GridViewTextBoxColumn channelVerificationColumn;
        private GridViewTextBoxColumn channelNotesColumn;
        private Button channelAddButton;
        private Button channelRemoveButton;
        private Label customHint;
        private Label gstLabel;
        private TextBox gstBox;
        private Label feedbackLabel;
        private Button applyButton;
        private Button cancelButton;
    }
}
