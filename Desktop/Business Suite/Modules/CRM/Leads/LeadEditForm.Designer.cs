#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class LeadEditForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.branchLabel = new Label();
            this.branchBox = new ComboBox();
            this.captureOwnerLabel = new Label();
            this.captureOwnerBox = new ComboBox();
            this.editTabs = new TabControl();
            this.editPage0 = new TabPage();
            this.editPage1 = new TabPage();
            this.editPage2 = new TabPage();
            this.first_nameLabel = new Label();
            this.first_nameBox = new TextBox();
            this.last_nameLabel = new Label();
            this.last_nameBox = new TextBox();
            this.company_nameLabel = new Label();
            this.company_nameBox = new TextBox();
            this.job_titleLabel = new Label();
            this.job_titleBox = new TextBox();
            this.emailLabel = new Label();
            this.emailBox = new TextBox();
            this.sourceLabel = new Label();
            this.sourceBox = new TextBox();
            this.phone_country_codeLabel = new Label();
            this.phone_country_codeBox = new ComboBox();
            this.phoneLabel = new Label();
            this.phoneBox = new TextBox();
            this.alternate_phone_country_codeLabel = new Label();
            this.alternate_phone_country_codeBox = new ComboBox();
            this.alternate_phoneLabel = new Label();
            this.alternate_phoneBox = new TextBox();
            this.statusLabel = new Label();
            this.statusBox = new ComboBox();
            this.ratingLabel = new Label();
            this.ratingBox = new ComboBox();
            this.estimated_valueLabel = new Label();
            this.estimated_valueBox = new TextBox();
            this.expected_close_dateLabel = new Label();
            this.expected_close_dateBox = new TextBox();
            this.next_follow_up_atLabel = new Label();
            this.next_follow_up_atBox = new TextBox();
            this.industryLabel = new Label();
            this.industryBox = new TextBox();
            this.websiteLabel = new Label();
            this.websiteBox = new TextBox();
            this.company_websiteLabel = new Label();
            this.company_websiteBox = new TextBox();
            this.linkedin_urlLabel = new Label();
            this.linkedin_urlBox = new TextBox();
            this.addressLabel = new Label();
            this.addressBox = new TextBox();
            this.cityLabel = new Label();
            this.cityBox = new TextBox();
            this.stateLabel = new Label();
            this.stateBox = new TextBox();
            this.countryLabel = new Label();
            this.countryBox = new TextBox();
            this.tags_textLabel = new Label();
            this.tags_textBox = new TextBox();
            this.needLabel = new Label();
            this.needBox = new TextBox();
            this.budgetLabel = new Label();
            this.budgetBox = new TextBox();
            this.decisionMakerLabel = new Label();
            this.decisionMakerBox = new TextBox();
            this.timelineLabel = new Label();
            this.timelineBox = new TextBox();
            this.lossReasonLabel = new Label();
            this.lossReasonBox = new TextBox();
            this.competitorLabel = new Label();
            this.competitorBox = new TextBox();
            this.notesLabel = new Label();
            this.notesBox = new TextBox();
            this.feedback = new Label();
            this.saveButton = new Button();
            this.cancelButton = new Button();
            this.SuspendLayout();
            // heading
            this.heading.Location = new Point(21, 13);
            this.heading.Size = new Size(397, 44);
            this.heading.Name = "heading";
            this.heading.Text = "New lead";
            this.heading.Font = new Font("Segoe UI Semibold", 24F);
            // branchLabel
            this.branchLabel.Location = new Point(444, 12);
            this.branchLabel.Size = new Size(165, 20);
            this.branchLabel.Name = "branchLabel";
            this.branchLabel.Text = "Branch";
            // branchBox
            this.branchBox.Location = new Point(444, 34);
            this.branchBox.Size = new Size(165, 26);
            this.branchBox.Name = "branchBox";
            this.branchBox.DropDownStyle = ComboBoxStyle.DropDownList;
            this.branchBox.SelectedIndexChanged += this.BranchChanged;
            this.captureOwnerLabel.Name = "captureOwnerLabel";
            this.captureOwnerLabel.Location = new Point(620, 12);
            this.captureOwnerLabel.Size = new Size(174, 20);
            this.captureOwnerLabel.Text = "Lead owner";
            this.captureOwnerBox.Name = "captureOwnerBox";
            this.captureOwnerBox.Location = new Point(620, 34);
            this.captureOwnerBox.Size = new Size(174, 26);
            this.captureOwnerBox.DisplayMember = "Name";
            this.captureOwnerBox.DropDownStyle = ComboBoxStyle.DropDownList;
            this.captureOwnerBox.Enabled = false;
            // editTabs
            this.editTabs.Location = new Point(18, 68);
            this.editTabs.Size = new Size(791, 465);
            this.editTabs.Name = "editTabs";
            this.editTabs.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            // editPage0
            this.editPage0.Name = "editPage0";
            this.editPage0.Text = "Profile";
            this.editPage0.UseVisualStyleBackColor = true;
            this.editPage0.AutoScroll = true;
            // editPage1
            this.editPage1.Name = "editPage1";
            this.editPage1.Text = "Business";
            this.editPage1.UseVisualStyleBackColor = true;
            this.editPage1.AutoScroll = true;
            // editPage2
            this.editPage2.Name = "editPage2";
            this.editPage2.Text = "Qualification";
            this.editPage2.UseVisualStyleBackColor = true;
            this.editPage2.AutoScroll = true;
            // first_nameLabel
            this.first_nameLabel.Location = new Point(16, 16);
            this.first_nameLabel.Size = new Size(355, 20);
            this.first_nameLabel.Name = "first_nameLabel";
            this.first_nameLabel.Text = "First name";
            // first_nameBox
            this.first_nameBox.Location = new Point(16, 37);
            this.first_nameBox.Size = new Size(355, 26);
            this.first_nameBox.Name = "first_nameBox";
            this.first_nameBox.MaxLength = 100;
            this.first_nameBox.AccessibleName = "First name";
            // last_nameLabel
            this.last_nameLabel.Location = new Point(395, 16);
            this.last_nameLabel.Size = new Size(355, 20);
            this.last_nameLabel.Name = "last_nameLabel";
            this.last_nameLabel.Text = "Last name";
            // last_nameBox
            this.last_nameBox.Location = new Point(395, 37);
            this.last_nameBox.Size = new Size(355, 26);
            this.last_nameBox.Name = "last_nameBox";
            this.last_nameBox.MaxLength = 100;
            this.last_nameBox.AccessibleName = "Last name";
            // company_nameLabel
            this.company_nameLabel.Location = new Point(16, 72);
            this.company_nameLabel.Size = new Size(355, 20);
            this.company_nameLabel.Name = "company_nameLabel";
            this.company_nameLabel.Text = "Company";
            // company_nameBox
            this.company_nameBox.Location = new Point(16, 93);
            this.company_nameBox.Size = new Size(355, 26);
            this.company_nameBox.Name = "company_nameBox";
            this.company_nameBox.MaxLength = 180;
            this.company_nameBox.AccessibleName = "Company";
            // job_titleLabel
            this.job_titleLabel.Location = new Point(395, 72);
            this.job_titleLabel.Size = new Size(355, 20);
            this.job_titleLabel.Name = "job_titleLabel";
            this.job_titleLabel.Text = "Job title";
            // job_titleBox
            this.job_titleBox.Location = new Point(395, 93);
            this.job_titleBox.Size = new Size(355, 26);
            this.job_titleBox.Name = "job_titleBox";
            this.job_titleBox.MaxLength = 120;
            this.job_titleBox.AccessibleName = "Job title";
            // emailLabel
            this.emailLabel.Location = new Point(16, 128);
            this.emailLabel.Size = new Size(355, 20);
            this.emailLabel.Name = "emailLabel";
            this.emailLabel.Text = "Email";
            // emailBox
            this.emailBox.Location = new Point(16, 149);
            this.emailBox.Size = new Size(355, 26);
            this.emailBox.Name = "emailBox";
            this.emailBox.MaxLength = 150;
            this.emailBox.AccessibleName = "Email";
            // sourceLabel
            this.sourceLabel.Location = new Point(395, 128);
            this.sourceLabel.Size = new Size(355, 20);
            this.sourceLabel.Name = "sourceLabel";
            this.sourceLabel.Text = "Source";
            // sourceBox
            this.sourceBox.Location = new Point(395, 149);
            this.sourceBox.Size = new Size(355, 26);
            this.sourceBox.Name = "sourceBox";
            this.sourceBox.MaxLength = 80;
            this.sourceBox.AccessibleName = "Source";
            // phone_country_codeLabel
            this.phone_country_codeLabel.Location = new Point(16, 184);
            this.phone_country_codeLabel.Size = new Size(355, 20);
            this.phone_country_codeLabel.Name = "phone_country_codeLabel";
            this.phone_country_codeLabel.Text = "Calling code";
            // phone_country_codeBox
            this.phone_country_codeBox.Location = new Point(16, 205);
            this.phone_country_codeBox.Size = new Size(355, 26);
            this.phone_country_codeBox.Name = "phone_country_codeBox";
            this.phone_country_codeBox.DropDownStyle = ComboBoxStyle.DropDown;
            this.phone_country_codeBox.AccessibleName = "Calling code";
            // phoneLabel
            this.phoneLabel.Location = new Point(395, 184);
            this.phoneLabel.Size = new Size(355, 20);
            this.phoneLabel.Name = "phoneLabel";
            this.phoneLabel.Text = "Phone number";
            // phoneBox
            this.phoneBox.Location = new Point(395, 205);
            this.phoneBox.Size = new Size(355, 26);
            this.phoneBox.Name = "phoneBox";
            this.phoneBox.MaxLength = 40;
            this.phoneBox.AccessibleName = "Phone number";
            // alternate_phone_country_codeLabel
            this.alternate_phone_country_codeLabel.Location = new Point(16, 240);
            this.alternate_phone_country_codeLabel.Size = new Size(355, 20);
            this.alternate_phone_country_codeLabel.Name = "alternate_phone_country_codeLabel";
            this.alternate_phone_country_codeLabel.Text = "Alternate calling code";
            // alternate_phone_country_codeBox
            this.alternate_phone_country_codeBox.Location = new Point(16, 261);
            this.alternate_phone_country_codeBox.Size = new Size(355, 26);
            this.alternate_phone_country_codeBox.Name = "alternate_phone_country_codeBox";
            this.alternate_phone_country_codeBox.DropDownStyle = ComboBoxStyle.DropDown;
            this.alternate_phone_country_codeBox.AccessibleName = "Alternate calling code";
            // alternate_phoneLabel
            this.alternate_phoneLabel.Location = new Point(395, 240);
            this.alternate_phoneLabel.Size = new Size(355, 20);
            this.alternate_phoneLabel.Name = "alternate_phoneLabel";
            this.alternate_phoneLabel.Text = "Alternate number";
            // alternate_phoneBox
            this.alternate_phoneBox.Location = new Point(395, 261);
            this.alternate_phoneBox.Size = new Size(355, 26);
            this.alternate_phoneBox.Name = "alternate_phoneBox";
            this.alternate_phoneBox.MaxLength = 40;
            this.alternate_phoneBox.AccessibleName = "Alternate number";
            // statusLabel
            this.statusLabel.Location = new Point(16, 296);
            this.statusLabel.Size = new Size(355, 20);
            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Text = "Stage";
            // statusBox
            this.statusBox.Location = new Point(16, 317);
            this.statusBox.Size = new Size(355, 26);
            this.statusBox.Name = "statusBox";
            this.statusBox.DropDownStyle = ComboBoxStyle.DropDownList;
            this.statusBox.AccessibleName = "Stage";
            // ratingLabel
            this.ratingLabel.Location = new Point(395, 296);
            this.ratingLabel.Size = new Size(355, 20);
            this.ratingLabel.Name = "ratingLabel";
            this.ratingLabel.Text = "Rating";
            // ratingBox
            this.ratingBox.Location = new Point(395, 317);
            this.ratingBox.Size = new Size(355, 26);
            this.ratingBox.Name = "ratingBox";
            this.ratingBox.DropDownStyle = ComboBoxStyle.DropDownList;
            this.ratingBox.AccessibleName = "Rating";
            // estimated_valueLabel
            this.estimated_valueLabel.Location = new Point(16, 352);
            this.estimated_valueLabel.Size = new Size(355, 20);
            this.estimated_valueLabel.Name = "estimated_valueLabel";
            this.estimated_valueLabel.Text = "Estimated value";
            // estimated_valueBox
            this.estimated_valueBox.Location = new Point(16, 373);
            this.estimated_valueBox.Size = new Size(355, 26);
            this.estimated_valueBox.Name = "estimated_valueBox";
            this.estimated_valueBox.MaxLength = 18;
            this.estimated_valueBox.AccessibleName = "Estimated value";
            // expected_close_dateLabel
            this.expected_close_dateLabel.Location = new Point(395, 352);
            this.expected_close_dateLabel.Size = new Size(355, 20);
            this.expected_close_dateLabel.Name = "expected_close_dateLabel";
            this.expected_close_dateLabel.Text = "Expected close date · YYYY-MM-DD";
            // expected_close_dateBox
            this.expected_close_dateBox.Location = new Point(395, 373);
            this.expected_close_dateBox.Size = new Size(355, 26);
            this.expected_close_dateBox.Name = "expected_close_dateBox";
            this.expected_close_dateBox.MaxLength = 10;
            this.expected_close_dateBox.AccessibleName = "Expected close date · YYYY-MM-DD";
            // next_follow_up_atLabel
            this.next_follow_up_atLabel.Location = new Point(16, 16);
            this.next_follow_up_atLabel.Size = new Size(355, 20);
            this.next_follow_up_atLabel.Name = "next_follow_up_atLabel";
            this.next_follow_up_atLabel.Text = "Next follow-up · YYYY-MM-DD HH:mm";
            // next_follow_up_atBox
            this.next_follow_up_atBox.Location = new Point(16, 37);
            this.next_follow_up_atBox.Size = new Size(355, 26);
            this.next_follow_up_atBox.Name = "next_follow_up_atBox";
            this.next_follow_up_atBox.MaxLength = 16;
            this.next_follow_up_atBox.AccessibleName = "Next follow-up · YYYY-MM-DD HH:mm";
            // industryLabel
            this.industryLabel.Location = new Point(395, 16);
            this.industryLabel.Size = new Size(355, 20);
            this.industryLabel.Name = "industryLabel";
            this.industryLabel.Text = "Industry";
            // industryBox
            this.industryBox.Location = new Point(395, 37);
            this.industryBox.Size = new Size(355, 26);
            this.industryBox.Name = "industryBox";
            this.industryBox.MaxLength = 120;
            this.industryBox.AccessibleName = "Industry";
            // websiteLabel
            this.websiteLabel.Location = new Point(16, 72);
            this.websiteLabel.Size = new Size(355, 20);
            this.websiteLabel.Name = "websiteLabel";
            this.websiteLabel.Text = "Website";
            // websiteBox
            this.websiteBox.Location = new Point(16, 93);
            this.websiteBox.Size = new Size(355, 26);
            this.websiteBox.Name = "websiteBox";
            this.websiteBox.MaxLength = 200;
            this.websiteBox.AccessibleName = "Website";
            // company_websiteLabel
            this.company_websiteLabel.Location = new Point(395, 72);
            this.company_websiteLabel.Size = new Size(355, 20);
            this.company_websiteLabel.Name = "company_websiteLabel";
            this.company_websiteLabel.Text = "Company website";
            // company_websiteBox
            this.company_websiteBox.Location = new Point(395, 93);
            this.company_websiteBox.Size = new Size(355, 26);
            this.company_websiteBox.Name = "company_websiteBox";
            this.company_websiteBox.MaxLength = 200;
            this.company_websiteBox.AccessibleName = "Company website";
            // linkedin_urlLabel
            this.linkedin_urlLabel.Location = new Point(16, 128);
            this.linkedin_urlLabel.Size = new Size(355, 20);
            this.linkedin_urlLabel.Name = "linkedin_urlLabel";
            this.linkedin_urlLabel.Text = "LinkedIn";
            // linkedin_urlBox
            this.linkedin_urlBox.Location = new Point(16, 149);
            this.linkedin_urlBox.Size = new Size(355, 26);
            this.linkedin_urlBox.Name = "linkedin_urlBox";
            this.linkedin_urlBox.MaxLength = 300;
            this.linkedin_urlBox.AccessibleName = "LinkedIn";
            // addressLabel
            this.addressLabel.Location = new Point(395, 128);
            this.addressLabel.Size = new Size(355, 20);
            this.addressLabel.Name = "addressLabel";
            this.addressLabel.Text = "Address";
            // addressBox
            this.addressBox.Location = new Point(395, 149);
            this.addressBox.Size = new Size(355, 26);
            this.addressBox.Name = "addressBox";
            this.addressBox.MaxLength = 2500;
            this.addressBox.AccessibleName = "Address";
            // cityLabel
            this.cityLabel.Location = new Point(16, 184);
            this.cityLabel.Size = new Size(355, 20);
            this.cityLabel.Name = "cityLabel";
            this.cityLabel.Text = "City";
            // cityBox
            this.cityBox.Location = new Point(16, 205);
            this.cityBox.Size = new Size(355, 26);
            this.cityBox.Name = "cityBox";
            this.cityBox.MaxLength = 100;
            this.cityBox.AccessibleName = "City";
            // stateLabel
            this.stateLabel.Location = new Point(395, 184);
            this.stateLabel.Size = new Size(355, 20);
            this.stateLabel.Name = "stateLabel";
            this.stateLabel.Text = "State";
            // stateBox
            this.stateBox.Location = new Point(395, 205);
            this.stateBox.Size = new Size(355, 26);
            this.stateBox.Name = "stateBox";
            this.stateBox.MaxLength = 100;
            this.stateBox.AccessibleName = "State";
            // countryLabel
            this.countryLabel.Location = new Point(16, 240);
            this.countryLabel.Size = new Size(355, 20);
            this.countryLabel.Name = "countryLabel";
            this.countryLabel.Text = "Country";
            // countryBox
            this.countryBox.Location = new Point(16, 261);
            this.countryBox.Size = new Size(355, 26);
            this.countryBox.Name = "countryBox";
            this.countryBox.MaxLength = 100;
            this.countryBox.AccessibleName = "Country";
            // tags_textLabel
            this.tags_textLabel.Location = new Point(395, 240);
            this.tags_textLabel.Size = new Size(355, 20);
            this.tags_textLabel.Name = "tags_textLabel";
            this.tags_textLabel.Text = "Tags";
            // tags_textBox
            this.tags_textBox.Location = new Point(395, 261);
            this.tags_textBox.Size = new Size(355, 26);
            this.tags_textBox.Name = "tags_textBox";
            this.tags_textBox.MaxLength = 500;
            this.tags_textBox.AccessibleName = "Tags";
            // needLabel
            this.needLabel.Location = new Point(16, 16);
            this.needLabel.Size = new Size(355, 20);
            this.needLabel.Name = "needLabel";
            this.needLabel.Text = "Need";
            // needBox
            this.needBox.Location = new Point(16, 37);
            this.needBox.Size = new Size(355, 26);
            this.needBox.Name = "needBox";
            this.needBox.MaxLength = 1000;
            this.needBox.AccessibleName = "Need";
            // budgetLabel
            this.budgetLabel.Location = new Point(395, 16);
            this.budgetLabel.Size = new Size(355, 20);
            this.budgetLabel.Name = "budgetLabel";
            this.budgetLabel.Text = "Budget";
            // budgetBox
            this.budgetBox.Location = new Point(395, 37);
            this.budgetBox.Size = new Size(355, 26);
            this.budgetBox.Name = "budgetBox";
            this.budgetBox.MaxLength = 1000;
            this.budgetBox.AccessibleName = "Budget";
            // decisionMakerLabel
            this.decisionMakerLabel.Location = new Point(16, 72);
            this.decisionMakerLabel.Size = new Size(355, 20);
            this.decisionMakerLabel.Name = "decisionMakerLabel";
            this.decisionMakerLabel.Text = "Decision maker";
            // decisionMakerBox
            this.decisionMakerBox.Location = new Point(16, 93);
            this.decisionMakerBox.Size = new Size(355, 26);
            this.decisionMakerBox.Name = "decisionMakerBox";
            this.decisionMakerBox.MaxLength = 1000;
            this.decisionMakerBox.AccessibleName = "Decision maker";
            // timelineLabel
            this.timelineLabel.Location = new Point(395, 72);
            this.timelineLabel.Size = new Size(355, 20);
            this.timelineLabel.Name = "timelineLabel";
            this.timelineLabel.Text = "Timeline";
            // timelineBox
            this.timelineBox.Location = new Point(395, 93);
            this.timelineBox.Size = new Size(355, 26);
            this.timelineBox.Name = "timelineBox";
            this.timelineBox.MaxLength = 1000;
            this.timelineBox.AccessibleName = "Timeline";
            // lossReasonLabel
            this.lossReasonLabel.Location = new Point(16, 128);
            this.lossReasonLabel.Size = new Size(355, 20);
            this.lossReasonLabel.Name = "lossReasonLabel";
            this.lossReasonLabel.Text = "Loss reason";
            // lossReasonBox
            this.lossReasonBox.Location = new Point(16, 149);
            this.lossReasonBox.Size = new Size(355, 26);
            this.lossReasonBox.Name = "lossReasonBox";
            this.lossReasonBox.MaxLength = 1000;
            this.lossReasonBox.AccessibleName = "Loss reason";
            this.competitorLabel.Location = new Point(16, 184);
            this.competitorLabel.Size = new Size(355, 20);
            this.competitorLabel.Text = "Competitor";
            this.competitorBox.Name = "competitorBox";
            this.competitorBox.Location = new Point(16, 205);
            this.competitorBox.Size = new Size(355, 26);
            this.competitorBox.MaxLength = 200;
            this.competitorBox.AccessibleName = "Competitor";
            // notesLabel
            this.notesLabel.Location = new Point(395, 128);
            this.notesLabel.Size = new Size(355, 20);
            this.notesLabel.Name = "notesLabel";
            this.notesLabel.Text = "Notes";
            // notesBox
            this.notesBox.Location = new Point(395, 149);
            this.notesBox.Size = new Size(355, 105);
            this.notesBox.Name = "notesBox";
            this.notesBox.MaxLength = 10000;
            this.notesBox.AccessibleName = "Notes";
            this.notesBox.Multiline = true;
            this.notesBox.ScrollBars = ScrollBars.Vertical;
            // feedback
            this.feedback.Location = new Point(21, 538);
            this.feedback.Size = new Size(545, 51);
            this.feedback.Name = "feedback";
            this.feedback.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.feedback.TextAlign = ContentAlignment.MiddleLeft;
            // saveButton
            this.saveButton.Location = new Point(581, 548);
            this.saveButton.Size = new Size(106, 39);
            this.saveButton.Name = "saveButton";
            this.saveButton.Text = "Save";
            this.saveButton.Enabled = false;
            this.saveButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.saveButton.Click += this.SaveClicked;
            // cancelButton
            this.cancelButton.Location = new Point(701, 548);
            this.cancelButton.Size = new Size(108, 39);
            this.cancelButton.Name = "cancelButton";
            this.cancelButton.Text = "Cancel";
            this.cancelButton.DialogResult = DialogResult.Cancel;
            this.cancelButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.editTabs.TabPages.AddRange(new TabPage[] { this.editPage0, this.editPage1, this.editPage2 });
            this.Shown += this.EditorShown;
            this.FormClosing += this.EditorClosing;
            this.FormClosed += this.EditorClosed;
            this.Controls.Add(this.heading);
            this.Controls.Add(this.branchLabel);
            this.Controls.Add(this.branchBox);
            this.Controls.Add(this.captureOwnerLabel);
            this.Controls.Add(this.captureOwnerBox);
            this.Controls.Add(this.editTabs);
            this.editPage0.Controls.Add(this.first_nameLabel);
            this.editPage0.Controls.Add(this.first_nameBox);
            this.editPage0.Controls.Add(this.last_nameLabel);
            this.editPage0.Controls.Add(this.last_nameBox);
            this.editPage0.Controls.Add(this.company_nameLabel);
            this.editPage0.Controls.Add(this.company_nameBox);
            this.editPage0.Controls.Add(this.job_titleLabel);
            this.editPage0.Controls.Add(this.job_titleBox);
            this.editPage0.Controls.Add(this.emailLabel);
            this.editPage0.Controls.Add(this.emailBox);
            this.editPage0.Controls.Add(this.sourceLabel);
            this.editPage0.Controls.Add(this.sourceBox);
            this.editPage0.Controls.Add(this.phone_country_codeLabel);
            this.editPage0.Controls.Add(this.phone_country_codeBox);
            this.editPage0.Controls.Add(this.phoneLabel);
            this.editPage0.Controls.Add(this.phoneBox);
            this.editPage0.Controls.Add(this.alternate_phone_country_codeLabel);
            this.editPage0.Controls.Add(this.alternate_phone_country_codeBox);
            this.editPage0.Controls.Add(this.alternate_phoneLabel);
            this.editPage0.Controls.Add(this.alternate_phoneBox);
            this.editPage0.Controls.Add(this.statusLabel);
            this.editPage0.Controls.Add(this.statusBox);
            this.editPage0.Controls.Add(this.ratingLabel);
            this.editPage0.Controls.Add(this.ratingBox);
            this.editPage0.Controls.Add(this.estimated_valueLabel);
            this.editPage0.Controls.Add(this.estimated_valueBox);
            this.editPage0.Controls.Add(this.expected_close_dateLabel);
            this.editPage0.Controls.Add(this.expected_close_dateBox);
            this.editPage1.Controls.Add(this.next_follow_up_atLabel);
            this.editPage1.Controls.Add(this.next_follow_up_atBox);
            this.editPage1.Controls.Add(this.industryLabel);
            this.editPage1.Controls.Add(this.industryBox);
            this.editPage1.Controls.Add(this.websiteLabel);
            this.editPage1.Controls.Add(this.websiteBox);
            this.editPage1.Controls.Add(this.company_websiteLabel);
            this.editPage1.Controls.Add(this.company_websiteBox);
            this.editPage1.Controls.Add(this.linkedin_urlLabel);
            this.editPage1.Controls.Add(this.linkedin_urlBox);
            this.editPage1.Controls.Add(this.addressLabel);
            this.editPage1.Controls.Add(this.addressBox);
            this.editPage1.Controls.Add(this.cityLabel);
            this.editPage1.Controls.Add(this.cityBox);
            this.editPage1.Controls.Add(this.stateLabel);
            this.editPage1.Controls.Add(this.stateBox);
            this.editPage1.Controls.Add(this.countryLabel);
            this.editPage1.Controls.Add(this.countryBox);
            this.editPage1.Controls.Add(this.tags_textLabel);
            this.editPage1.Controls.Add(this.tags_textBox);
            this.editPage2.Controls.Add(this.needLabel);
            this.editPage2.Controls.Add(this.needBox);
            this.editPage2.Controls.Add(this.budgetLabel);
            this.editPage2.Controls.Add(this.budgetBox);
            this.editPage2.Controls.Add(this.decisionMakerLabel);
            this.editPage2.Controls.Add(this.decisionMakerBox);
            this.editPage2.Controls.Add(this.timelineLabel);
            this.editPage2.Controls.Add(this.timelineBox);
            this.editPage2.Controls.Add(this.lossReasonLabel);
            this.editPage2.Controls.Add(this.lossReasonBox);
            this.editPage2.Controls.Add(this.competitorLabel);
            this.editPage2.Controls.Add(this.competitorBox);
            this.editPage2.Controls.Add(this.notesLabel);
            this.editPage2.Controls.Add(this.notesBox);
            this.Controls.Add(this.feedback);
            this.Controls.Add(this.saveButton);
            this.Controls.Add(this.cancelButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.Font = new Font("Segoe UI", 10F);
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ForeColor = Color.FromArgb(24, 35, 58);
            this.Text = "Business Suite | Lead";
            this.ClientSize = new Size(827, 607);
            this.MinimumSize = new Size(845, 570);
            this.StartPosition = FormStartPosition.CenterParent;
            this.AcceptButton = this.saveButton;
            this.CancelButton = this.cancelButton;
            this.Name = "LeadEditForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label heading;
        private Label branchLabel;
        private ComboBox branchBox;
        private Label captureOwnerLabel;
        private ComboBox captureOwnerBox;
        private TabControl editTabs;
        private TabPage editPage0;
        private TabPage editPage1;
        private TabPage editPage2;
        private Label first_nameLabel;
        private TextBox first_nameBox;
        private Label last_nameLabel;
        private TextBox last_nameBox;
        private Label company_nameLabel;
        private TextBox company_nameBox;
        private Label job_titleLabel;
        private TextBox job_titleBox;
        private Label emailLabel;
        private TextBox emailBox;
        private Label sourceLabel;
        private TextBox sourceBox;
        private Label phone_country_codeLabel;
        private ComboBox phone_country_codeBox;
        private Label phoneLabel;
        private TextBox phoneBox;
        private Label alternate_phone_country_codeLabel;
        private ComboBox alternate_phone_country_codeBox;
        private Label alternate_phoneLabel;
        private TextBox alternate_phoneBox;
        private Label statusLabel;
        private ComboBox statusBox;
        private Label ratingLabel;
        private ComboBox ratingBox;
        private Label estimated_valueLabel;
        private TextBox estimated_valueBox;
        private Label expected_close_dateLabel;
        private TextBox expected_close_dateBox;
        private Label next_follow_up_atLabel;
        private TextBox next_follow_up_atBox;
        private Label industryLabel;
        private TextBox industryBox;
        private Label websiteLabel;
        private TextBox websiteBox;
        private Label company_websiteLabel;
        private TextBox company_websiteBox;
        private Label linkedin_urlLabel;
        private TextBox linkedin_urlBox;
        private Label addressLabel;
        private TextBox addressBox;
        private Label cityLabel;
        private TextBox cityBox;
        private Label stateLabel;
        private TextBox stateBox;
        private Label countryLabel;
        private TextBox countryBox;
        private Label tags_textLabel;
        private TextBox tags_textBox;
        private Label needLabel;
        private TextBox needBox;
        private Label budgetLabel;
        private TextBox budgetBox;
        private Label decisionMakerLabel;
        private TextBox decisionMakerBox;
        private Label timelineLabel;
        private TextBox timelineBox;
        private Label lossReasonLabel;
        private TextBox lossReasonBox;
        private Label competitorLabel;
        private TextBox competitorBox;
        private Label notesLabel;
        private TextBox notesBox;
        private Label feedback;
        private Button saveButton;
        private Button cancelButton;
    }
}
