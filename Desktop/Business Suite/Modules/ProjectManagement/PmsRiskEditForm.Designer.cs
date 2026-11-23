#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsRiskEditForm
    {
        private void InitializeComponent()
        {
            this.titleLabel = new Label();
            this.titleInput = new RadTextBox();
            this.categoryLabel = new Label();
            this.categoryInput = new RadTextBox();
            this.ownerLabel = new Label();
            this.ownerInput = new RadDropDownList();
            this.taskLabel = new Label();
            this.taskInput = new RadDropDownList();
            this.probabilityLabel = new Label();
            this.probabilityInput = new RadSpinEditor();
            this.impactLabel = new Label();
            this.impactInput = new RadSpinEditor();
            this.statusLabel = new Label();
            this.statusInput = new RadDropDownList();
            this.dueLabel = new Label();
            this.dueInput = new RadDateTimePicker();
            this.descriptionLabel = new Label();
            this.descriptionInput = new RadTextBox();
            this.mitigationLabel = new Label();
            this.mitigationInput = new RadTextBox();
            this.contingencyLabel = new Label();
            this.contingencyInput = new RadTextBox();
            this.scoreLabel = new Label();
            this.errorLabel = new Label();
            this.saveButton = new RadButton();
            this.cancelButton = new RadButton();
            this.SuspendLayout();

            this.titleLabel.Name = "titleLabel";
            this.titleLabel.Text = "Title";
            this.titleLabel.Location = new Point(14, 15);
            this.titleLabel.Size = new Size(530, 23);
            this.titleInput.Name = "titleInput";
            this.titleInput.Location = new Point(14, 37);
            this.titleInput.Size = new Size(530, 25);

            this.categoryLabel.Name = "categoryLabel";
            this.categoryLabel.Text = "Category";
            this.categoryLabel.Location = new Point(556, 15);
            this.categoryLabel.Size = new Size(260, 23);
            this.categoryInput.Name = "categoryInput";
            this.categoryInput.Location = new Point(556, 37);
            this.categoryInput.Size = new Size(260, 25);

            this.ownerLabel.Name = "ownerLabel";
            this.ownerLabel.Text = "Owner";
            this.ownerLabel.Location = new Point(14, 69);
            this.ownerLabel.Size = new Size(400, 23);
            this.ownerInput.Name = "ownerInput";
            this.ownerInput.Location = new Point(14, 91);
            this.ownerInput.Size = new Size(400, 25);

            this.taskLabel.Name = "taskLabel";
            this.taskLabel.Text = "Linked task";
            this.taskLabel.Location = new Point(426, 69);
            this.taskLabel.Size = new Size(390, 23);
            this.taskInput.Name = "taskInput";
            this.taskInput.Location = new Point(426, 91);
            this.taskInput.Size = new Size(390, 25);

            this.probabilityLabel.Name = "probabilityLabel";
            this.probabilityLabel.Text = "Probability";
            this.probabilityLabel.Location = new Point(14, 125);
            this.probabilityLabel.Size = new Size(110, 23);
            this.probabilityInput.Name = "probabilityInput";
            this.probabilityInput.Location = new Point(14, 147);
            this.probabilityInput.Size = new Size(110, 25);

            this.impactLabel.Name = "impactLabel";
            this.impactLabel.Text = "Impact";
            this.impactLabel.Location = new Point(139, 125);
            this.impactLabel.Size = new Size(110, 23);
            this.impactInput.Name = "impactInput";
            this.impactInput.Location = new Point(139, 147);
            this.impactInput.Size = new Size(110, 25);

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Text = "Status";
            this.statusLabel.Location = new Point(264, 125);
            this.statusLabel.Size = new Size(182, 23);
            this.statusInput.Name = "statusInput";
            this.statusInput.Location = new Point(264, 147);
            this.statusInput.Size = new Size(182, 25);

            this.dueLabel.Name = "dueLabel";
            this.dueLabel.Text = "Due date";
            this.dueLabel.Location = new Point(461, 125);
            this.dueLabel.Size = new Size(220, 23);
            this.dueInput.Name = "dueInput";
            this.dueInput.Location = new Point(461, 147);
            this.dueInput.Size = new Size(220, 25);

            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Description";
            this.descriptionLabel.Location = new Point(14, 183);
            this.descriptionLabel.Size = new Size(802, 23);
            this.descriptionInput.Name = "descriptionInput";
            this.descriptionInput.Location = new Point(14, 205);
            this.descriptionInput.Size = new Size(802, 57);

            this.mitigationLabel.Name = "mitigationLabel";
            this.mitigationLabel.Text = "Mitigation plan";
            this.mitigationLabel.Location = new Point(14, 272);
            this.mitigationLabel.Size = new Size(802, 23);
            this.mitigationInput.Name = "mitigationInput";
            this.mitigationInput.Location = new Point(14, 294);
            this.mitigationInput.Size = new Size(802, 57);

            this.contingencyLabel.Name = "contingencyLabel";
            this.contingencyLabel.Text = "Contingency plan";
            this.contingencyLabel.Location = new Point(14, 361);
            this.contingencyLabel.Size = new Size(802, 23);
            this.contingencyInput.Name = "contingencyInput";
            this.contingencyInput.Location = new Point(14, 383);
            this.contingencyInput.Size = new Size(802, 57);

            this.titleInput.MaxLength = 220;
            this.categoryInput.MaxLength = 80;
            this.ownerInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.taskInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.statusInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.statusInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Open") { Value = "open" },
                new RadListDataItem("Mitigating") { Value = "mitigating" },
                new RadListDataItem("Closed") { Value = "closed" } });
            this.statusInput.SelectedIndex = 0;
            this.dueInput.Format = DateTimePickerFormat.Short;
            this.dueInput.ShowCheckBox = true;
            this.probabilityInput.Minimum = this.impactInput.Minimum = 1;
            this.probabilityInput.Maximum = this.impactInput.Maximum = 5;
            this.probabilityInput.Value = this.impactInput.Value = 3;
            this.probabilityInput.ValueChanged += this.ScoreChanged;
            this.impactInput.ValueChanged += this.ScoreChanged;
            this.descriptionInput.Multiline = true;
            this.descriptionInput.ScrollBars = ScrollBars.Vertical;
            this.mitigationInput.Multiline = true;
            this.mitigationInput.ScrollBars = ScrollBars.Vertical;
            this.contingencyInput.Multiline = true;
            this.contingencyInput.ScrollBars = ScrollBars.Vertical;

            this.scoreLabel.Name = "scoreLabel";
            this.scoreLabel.Location = new Point(695, 143);
            this.scoreLabel.Size = new Size(121, 35);
            this.scoreLabel.Text = "Score 9 · Medium";

            this.errorLabel.Name = "errorLabel";
            this.errorLabel.Location = new Point(14, 452);
            this.errorLabel.Size = new Size(800, 44);
            this.errorLabel.ForeColor = Color.Firebrick;

            this.saveButton.Name = "saveButton";
            this.saveButton.Text = "Save";
            this.saveButton.Location = new Point(632, 500);
            this.saveButton.Size = new Size(88, 29);
            this.saveButton.Click += this.SaveClicked;

            this.cancelButton.Name = "cancelButton";
            this.cancelButton.Text = "Cancel";
            this.cancelButton.Location = new Point(730, 500);
            this.cancelButton.Size = new Size(88, 29);
            this.cancelButton.DialogResult = DialogResult.Cancel;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(833, 542);
            this.Controls.AddRange(new Control[] {
                this.titleLabel, this.titleInput,
                this.categoryLabel, this.categoryInput,
                this.ownerLabel, this.ownerInput,
                this.taskLabel, this.taskInput,
                this.probabilityLabel, this.probabilityInput,
                this.impactLabel, this.impactInput,
                this.statusLabel, this.statusInput,
                this.dueLabel, this.dueInput,
                this.descriptionLabel, this.descriptionInput,
                this.mitigationLabel, this.mitigationInput,
                this.contingencyLabel, this.contingencyInput,
                this.scoreLabel, this.errorLabel, this.saveButton, this.cancelButton });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "PmsRiskEditForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Edit risk";
            this.AcceptButton = this.saveButton;
            this.CancelButton = this.cancelButton;
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label titleLabel;
        private RadTextBox titleInput;
        private Label categoryLabel;
        private RadTextBox categoryInput;
        private Label ownerLabel;
        private RadDropDownList ownerInput;
        private Label taskLabel;
        private RadDropDownList taskInput;
        private Label probabilityLabel;
        private RadSpinEditor probabilityInput;
        private Label impactLabel;
        private RadSpinEditor impactInput;
        private Label statusLabel;
        private RadDropDownList statusInput;
        private Label dueLabel;
        private RadDateTimePicker dueInput;
        private Label descriptionLabel;
        private RadTextBox descriptionInput;
        private Label mitigationLabel;
        private RadTextBox mitigationInput;
        private Label contingencyLabel;
        private RadTextBox contingencyInput;
        private Label scoreLabel;
        private Label errorLabel;
        private RadButton saveButton;
        private RadButton cancelButton;
    }
}
