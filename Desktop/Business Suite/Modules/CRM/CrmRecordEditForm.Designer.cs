#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class CrmRecordEditForm
    {
        private void InitializeComponent()
        {
            this.extrasButton = new Button();
            this.headingLabel = new Label();
            this.nameLabel = new Label();
            this.nameBox = new TextBox();
            this.lastNameLabel = new Label();
            this.lastNameBox = new TextBox();
            this.detailLabel = new Label();
            this.detailBox = new TextBox();
            this.industryLabel = new Label();
            this.industryBox = new TextBox();
            this.emailLabel = new Label();
            this.emailBox = new TextBox();
            this.phoneLabel = new Label();
            this.phoneBox = new TextBox();
            this.phoneCodeLabel = new Label();
            this.phoneCodeBox = new ComboBox();
            this.websiteLabel = new Label();
            this.websiteBox = new TextBox();
            this.cityLabel = new Label();
            this.cityBox = new TextBox();
            this.stateLabel = new Label();
            this.stateBox = new TextBox();
            this.countryLabel = new Label();
            this.countryBox = new TextBox();
            this.companyLabel = new Label();
            this.companyBox = new ComboBox();
            this.branchLabel = new Label();
            this.branchBox = new ComboBox();
            this.classificationLabel = new Label();
            this.classificationBox = new TextBox();
            this.statusLabel = new Label();
            this.statusBox = new TextBox();
            this.tagsLabel = new Label();
            this.tagsBox = new TextBox();
            this.addressLabel = new Label();
            this.addressBox = new TextBox();
            this.notesLabel = new Label();
            this.notesBox = new TextBox();
            this.duplicateReasonLabel = new Label();
            this.duplicateReasonBox = new TextBox();
            this.saveStatus = new Label();
            this.saveButton = new Button();
            this.cancelButton = new Button();
            this.SuspendLayout();
            this.extrasButton.Location = new Point(24, 792);
            this.extrasButton.Size = new Size(264, 39);
            this.extrasButton.Name = "extrasButton";
            this.extrasButton.Text = "Custom fields, tax && channels";
            this.extrasButton.Click += this.ExtrasClicked;
            this.Controls.Add(this.extrasButton);
            // headingLabel
            this.headingLabel.Location = new Point(24, 16);
            this.headingLabel.Size = new Size(340, 49);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "New company";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 24F);
            // nameLabel
            this.nameLabel.Location = new Point(24, 79);
            this.nameLabel.Size = new Size(333, 21);
            this.nameLabel.Name = "nameLabel";
            this.nameLabel.Text = "Company name";
            // nameBox
            this.nameBox.Location = new Point(24, 101);
            this.nameBox.Size = new Size(330, 28);
            this.nameBox.Name = "nameBox";
            this.nameBox.AccessibleName = "Company name";
            this.nameBox.MaxLength = 180;
            this.nameBox.TextChanged += this.IdentityChanged;
            // lastNameLabel
            this.lastNameLabel.Location = new Point(379, 79);
            this.lastNameLabel.Size = new Size(333, 21);
            this.lastNameLabel.Name = "lastNameLabel";
            this.lastNameLabel.Text = "Last name";
            // lastNameBox
            this.lastNameBox.Location = new Point(379, 101);
            this.lastNameBox.Size = new Size(330, 28);
            this.lastNameBox.Name = "lastNameBox";
            this.lastNameBox.AccessibleName = "Last name";
            this.lastNameBox.MaxLength = 100;
            // detailLabel
            this.detailLabel.Location = new Point(24, 140);
            this.detailLabel.Size = new Size(333, 21);
            this.detailLabel.Name = "detailLabel";
            this.detailLabel.Text = "Legal name";
            // detailBox
            this.detailBox.Location = new Point(24, 162);
            this.detailBox.Size = new Size(330, 28);
            this.detailBox.Name = "detailBox";
            this.detailBox.AccessibleName = "Legal name";
            this.detailBox.MaxLength = 180;
            // industryLabel
            this.industryLabel.Location = new Point(379, 140);
            this.industryLabel.Size = new Size(333, 21);
            this.industryLabel.Name = "industryLabel";
            this.industryLabel.Text = "Industry";
            // industryBox
            this.industryBox.Location = new Point(379, 162);
            this.industryBox.Size = new Size(330, 28);
            this.industryBox.Name = "industryBox";
            this.industryBox.AccessibleName = "Industry";
            this.industryBox.MaxLength = 120;
            // emailLabel
            this.emailLabel.Location = new Point(24, 201);
            this.emailLabel.Size = new Size(333, 21);
            this.emailLabel.Name = "emailLabel";
            this.emailLabel.Text = "Email";
            // emailBox
            this.emailBox.Location = new Point(24, 223);
            this.emailBox.Size = new Size(330, 28);
            this.emailBox.Name = "emailBox";
            this.emailBox.AccessibleName = "Email";
            this.emailBox.MaxLength = 150;
            this.emailBox.TextChanged += this.IdentityChanged;
            // phoneLabel
            this.phoneLabel.Location = new Point(379, 201);
            this.phoneLabel.Size = new Size(333, 21);
            this.phoneLabel.Name = "phoneLabel";
            this.phoneLabel.Text = "Phone";
            // phoneBox
            this.phoneBox.Location = new Point(379, 223);
            this.phoneBox.Size = new Size(330, 28);
            this.phoneBox.Name = "phoneBox";
            this.phoneBox.AccessibleName = "Phone";
            this.phoneBox.MaxLength = 40;
            this.phoneBox.TextChanged += this.IdentityChanged;
            // phoneCodeLabel
            this.phoneCodeLabel.Location = new Point(24, 262);
            this.phoneCodeLabel.Size = new Size(333, 21);
            this.phoneCodeLabel.Name = "phoneCodeLabel";
            this.phoneCodeLabel.Text = "Phone country code";
            // phoneCodeBox
            this.phoneCodeBox.Location = new Point(24, 284);
            this.phoneCodeBox.Size = new Size(330, 28);
            this.phoneCodeBox.Name = "phoneCodeBox";
            this.phoneCodeBox.AccessibleName = "Phone country code";
            this.phoneCodeBox.MaxLength = 5;
            this.phoneCodeBox.AutoCompleteMode = AutoCompleteMode.SuggestAppend;
            this.phoneCodeBox.AutoCompleteSource = AutoCompleteSource.ListItems;
            this.phoneCodeBox.TextChanged += this.IdentityChanged;
            // websiteLabel
            this.websiteLabel.Location = new Point(379, 262);
            this.websiteLabel.Size = new Size(333, 21);
            this.websiteLabel.Name = "websiteLabel";
            this.websiteLabel.Text = "Website";
            // websiteBox
            this.websiteBox.Location = new Point(379, 284);
            this.websiteBox.Size = new Size(330, 28);
            this.websiteBox.Name = "websiteBox";
            this.websiteBox.AccessibleName = "Website";
            this.websiteBox.MaxLength = 200;
            // cityLabel
            this.cityLabel.Location = new Point(24, 323);
            this.cityLabel.Size = new Size(333, 21);
            this.cityLabel.Name = "cityLabel";
            this.cityLabel.Text = "City";
            // cityBox
            this.cityBox.Location = new Point(24, 345);
            this.cityBox.Size = new Size(330, 28);
            this.cityBox.Name = "cityBox";
            this.cityBox.AccessibleName = "City";
            this.cityBox.MaxLength = 100;
            // stateLabel
            this.stateLabel.Location = new Point(379, 323);
            this.stateLabel.Size = new Size(333, 21);
            this.stateLabel.Name = "stateLabel";
            this.stateLabel.Text = "State";
            // stateBox
            this.stateBox.Location = new Point(379, 345);
            this.stateBox.Size = new Size(330, 28);
            this.stateBox.Name = "stateBox";
            this.stateBox.AccessibleName = "State";
            this.stateBox.MaxLength = 100;
            // countryLabel
            this.countryLabel.Location = new Point(24, 384);
            this.countryLabel.Size = new Size(333, 21);
            this.countryLabel.Name = "countryLabel";
            this.countryLabel.Text = "Country";
            // countryBox
            this.countryBox.Location = new Point(24, 406);
            this.countryBox.Size = new Size(330, 28);
            this.countryBox.Name = "countryBox";
            this.countryBox.AccessibleName = "Country";
            this.countryBox.MaxLength = 100;
            // companyLabel
            this.companyLabel.Location = new Point(379, 384);
            this.companyLabel.Size = new Size(333, 21);
            this.companyLabel.Name = "companyLabel";
            this.companyLabel.Text = "Linked company";
            // companyBox
            this.companyBox.Location = new Point(379, 406);
            this.companyBox.Size = new Size(330, 28);
            this.companyBox.Name = "companyBox";
            this.companyBox.AccessibleName = "Linked company";
            this.companyBox.DropDownStyle = ComboBoxStyle.DropDownList;
            // branchLabel
            this.branchLabel.Location = new Point(379, 20);
            this.branchLabel.Size = new Size(330, 20);
            this.branchLabel.Name = "branchLabel";
            this.branchLabel.Text = "Branch";
            // branchBox
            this.branchBox.Location = new Point(379, 42);
            this.branchBox.Size = new Size(330, 28);
            this.branchBox.Name = "branchBox";
            this.branchBox.AccessibleName = "Branch";
            this.branchBox.DropDownStyle = ComboBoxStyle.DropDownList;
            // classificationLabel
            this.classificationLabel.Location = new Point(24, 445);
            this.classificationLabel.Size = new Size(333, 21);
            this.classificationLabel.Name = "classificationLabel";
            this.classificationLabel.Text = "Relationships (comma-separated)";
            // classificationBox
            this.classificationBox.Location = new Point(24, 467);
            this.classificationBox.Size = new Size(330, 28);
            this.classificationBox.Name = "classificationBox";
            this.classificationBox.AccessibleName = "Relationships (comma-separated)";
            this.classificationBox.MaxLength = 250;
            // statusLabel
            this.statusLabel.Location = new Point(379, 445);
            this.statusLabel.Size = new Size(333, 21);
            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Text = "Status";
            // statusBox
            this.statusBox.Location = new Point(379, 467);
            this.statusBox.Size = new Size(330, 28);
            this.statusBox.Name = "statusBox";
            this.statusBox.AccessibleName = "Status";
            this.statusBox.MaxLength = 40;
            // tagsLabel
            this.tagsLabel.Location = new Point(24, 506);
            this.tagsLabel.Size = new Size(333, 21);
            this.tagsLabel.Name = "tagsLabel";
            this.tagsLabel.Text = "Tags (comma-separated)";
            // tagsBox
            this.tagsBox.Location = new Point(24, 528);
            this.tagsBox.Size = new Size(330, 28);
            this.tagsBox.Name = "tagsBox";
            this.tagsBox.AccessibleName = "Tags (comma-separated)";
            this.tagsBox.MaxLength = 500;
            // addressLabel
            this.addressLabel.Location = new Point(379, 506);
            this.addressLabel.Size = new Size(333, 21);
            this.addressLabel.Name = "addressLabel";
            this.addressLabel.Text = "Address";
            // addressBox
            this.addressBox.Location = new Point(379, 528);
            this.addressBox.Size = new Size(330, 28);
            this.addressBox.Name = "addressBox";
            this.addressBox.AccessibleName = "Address";
            this.addressBox.MaxLength = 3000;
            // notesLabel
            this.notesLabel.Location = new Point(24, 567);
            this.notesLabel.Size = new Size(685, 21);
            this.notesLabel.Name = "notesLabel";
            this.notesLabel.Text = "Notes";
            // notesBox
            this.notesBox.Location = new Point(24, 590);
            this.notesBox.Size = new Size(685, 88);
            this.notesBox.Name = "notesBox";
            this.notesBox.Multiline = true;
            this.notesBox.ScrollBars = ScrollBars.Vertical;
            this.notesBox.MaxLength = 10000;
            this.notesBox.AccessibleName = "Notes";
            // duplicateReasonLabel
            this.duplicateReasonLabel.Location = new Point(24, 687);
            this.duplicateReasonLabel.Size = new Size(685, 20);
            this.duplicateReasonLabel.Name = "duplicateReasonLabel";
            this.duplicateReasonLabel.Text = "Reason for saving as a separate record";
            // duplicateReasonBox
            this.duplicateReasonBox.Location = new Point(24, 710);
            this.duplicateReasonBox.Size = new Size(685, 28);
            this.duplicateReasonBox.Name = "duplicateReasonBox";
            this.duplicateReasonBox.AccessibleName = "Reason for saving as a separate record";
            this.duplicateReasonBox.MaxLength = 250;
            // saveStatus
            this.saveStatus.Location = new Point(24, 748);
            this.saveStatus.Size = new Size(685, 42);
            this.saveStatus.Name = "saveStatus";
            this.saveStatus.TextAlign = ContentAlignment.MiddleLeft;
            // saveButton
            this.saveButton.Location = new Point(430, 792);
            this.saveButton.Size = new Size(164, 39);
            this.saveButton.Name = "saveButton";
            this.saveButton.Text = "Save";
            this.saveButton.Click += this.SaveClicked;
            // cancelButton
            this.cancelButton.Location = new Point(607, 792);
            this.cancelButton.Size = new Size(102, 39);
            this.cancelButton.Name = "cancelButton";
            this.cancelButton.Text = "Cancel";
            this.cancelButton.DialogResult = DialogResult.Cancel;
            this.FormClosing += this.EditorClosing;
            this.Shown += this.LoadChoices;
            this.FormClosed += this.EditorClosed;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.nameLabel);
            this.Controls.Add(this.nameBox);
            this.Controls.Add(this.lastNameLabel);
            this.Controls.Add(this.lastNameBox);
            this.Controls.Add(this.detailLabel);
            this.Controls.Add(this.detailBox);
            this.Controls.Add(this.industryLabel);
            this.Controls.Add(this.industryBox);
            this.Controls.Add(this.emailLabel);
            this.Controls.Add(this.emailBox);
            this.Controls.Add(this.phoneLabel);
            this.Controls.Add(this.phoneBox);
            this.Controls.Add(this.phoneCodeLabel);
            this.Controls.Add(this.phoneCodeBox);
            this.Controls.Add(this.websiteLabel);
            this.Controls.Add(this.websiteBox);
            this.Controls.Add(this.cityLabel);
            this.Controls.Add(this.cityBox);
            this.Controls.Add(this.stateLabel);
            this.Controls.Add(this.stateBox);
            this.Controls.Add(this.countryLabel);
            this.Controls.Add(this.countryBox);
            this.Controls.Add(this.companyLabel);
            this.Controls.Add(this.companyBox);
            this.Controls.Add(this.branchLabel);
            this.Controls.Add(this.branchBox);
            this.Controls.Add(this.classificationLabel);
            this.Controls.Add(this.classificationBox);
            this.Controls.Add(this.statusLabel);
            this.Controls.Add(this.statusBox);
            this.Controls.Add(this.tagsLabel);
            this.Controls.Add(this.tagsBox);
            this.Controls.Add(this.addressLabel);
            this.Controls.Add(this.addressBox);
            this.Controls.Add(this.notesLabel);
            this.Controls.Add(this.notesBox);
            this.Controls.Add(this.duplicateReasonLabel);
            this.Controls.Add(this.duplicateReasonBox);
            this.Controls.Add(this.saveStatus);
            this.Controls.Add(this.saveButton);
            this.Controls.Add(this.cancelButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.Font = new Font("Segoe UI", 10F);
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ForeColor = Color.FromArgb(24, 35, 58);
            this.Text = "Business Suite | CRM record";
            this.ClientSize = new Size(735, 850);
            this.FormBorderStyle = FormBorderStyle.Sizable;
            this.AutoScroll = true;
            this.MinimumSize = new Size(520, 420);
            this.StartPosition = FormStartPosition.CenterParent;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.CancelButton = this.cancelButton;
            this.AcceptButton = this.saveButton;
            this.Name = "CrmRecordEditForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Button extrasButton;
        private Label headingLabel;
        private Label nameLabel;
        private TextBox nameBox;
        private Label lastNameLabel;
        private TextBox lastNameBox;
        private Label detailLabel;
        private TextBox detailBox;
        private Label industryLabel;
        private TextBox industryBox;
        private Label emailLabel;
        private TextBox emailBox;
        private Label phoneLabel;
        private TextBox phoneBox;
        private Label phoneCodeLabel;
        private ComboBox phoneCodeBox;
        private Label websiteLabel;
        private TextBox websiteBox;
        private Label cityLabel;
        private TextBox cityBox;
        private Label stateLabel;
        private TextBox stateBox;
        private Label countryLabel;
        private TextBox countryBox;
        private Label companyLabel;
        private ComboBox companyBox;
        private Label branchLabel;
        private ComboBox branchBox;
        private Label classificationLabel;
        private TextBox classificationBox;
        private Label statusLabel;
        private TextBox statusBox;
        private Label tagsLabel;
        private TextBox tagsBox;
        private Label addressLabel;
        private TextBox addressBox;
        private Label notesLabel;
        private TextBox notesBox;
        private Label duplicateReasonLabel;
        private TextBox duplicateReasonBox;
        private Label saveStatus;
        private Button saveButton;
        private Button cancelButton;
    }
}
