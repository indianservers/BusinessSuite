#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeLifecycleForm
    {
        private void InitializeComponent()
        {
            this.employeeLabel = new Label();
            this.historyGrid = new RadGridView();
            this.reasonLabel = new Label();
            this.reasonInput = new RadTextBox();
            this.applyButton = new RadButton();
            this.accessButton = new RadButton();
            this.transfersButton = new RadButton();
            this.onboardingButton = new RadButton();
            this.exitButton = new RadButton();
            this.closeButton = new RadButton();
            this.statusLabel = new Label();
            this.eventColumn = new GridViewTextBoxColumn();
            this.dateColumn = new GridViewTextBoxColumn();
            this.fromColumn = new GridViewTextBoxColumn();
            this.toColumn = new GridViewTextBoxColumn();
            this.reasonColumn = new GridViewTextBoxColumn();
            ((System.ComponentModel.ISupportInitialize)this.historyGrid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.historyGrid.MasterTemplate).BeginInit();
            this.SuspendLayout();

            this.employeeLabel.Name = "employeeLabel";
            this.employeeLabel.Location = new Point(13, 13);
            this.employeeLabel.Size = new Size(576, 27);
            this.employeeLabel.Font = new Font("Segoe UI Semibold", 11F);

            this.eventColumn.Name = "eventColumn";
            this.eventColumn.FieldName = "event_type";
            this.eventColumn.HeaderText = "Event";
            this.eventColumn.Width = 160;

            this.dateColumn.Name = "dateColumn";
            this.dateColumn.FieldName = "event_date";
            this.dateColumn.HeaderText = "Date";
            this.dateColumn.Width = 105;
            this.dateColumn.FormatString = "{0:d}";

            this.fromColumn.Name = "fromColumn";
            this.fromColumn.FieldName = "from_status";
            this.fromColumn.HeaderText = "Previous";
            this.fromColumn.Width = 100;

            this.toColumn.Name = "toColumn";
            this.toColumn.FieldName = "to_status";
            this.toColumn.HeaderText = "New status";
            this.toColumn.Width = 100;

            this.reasonColumn.Name = "reasonColumn";
            this.reasonColumn.FieldName = "reason";
            this.reasonColumn.HeaderText = "Reason";
            this.reasonColumn.Width = 255;

            this.historyGrid.Name = "historyGrid";
            this.historyGrid.Location = new Point(13, 49);
            this.historyGrid.Size = new Size(740, 251);
            this.historyGrid.AutoGenerateColumns = false;
            this.historyGrid.ReadOnly = true;
            this.historyGrid.MasterTemplate.AllowAddNewRow = false;
            this.historyGrid.MasterTemplate.AllowDeleteRow = false;
            this.historyGrid.MasterTemplate.AllowEditRow = false;
            this.historyGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.eventColumn, this.dateColumn, this.fromColumn, this.toColumn, this.reasonColumn });

            this.reasonLabel.Name = "reasonLabel";
            this.reasonLabel.Location = new Point(16, 313);
            this.reasonLabel.Size = new Size(200, 22);
            this.reasonLabel.Text = "Reason";

            this.reasonInput.Name = "reasonInput";
            this.reasonInput.Location = new Point(15, 337);
            this.reasonInput.Size = new Size(738, 62);
            this.reasonInput.MaxLength = 1000;
            this.reasonInput.Multiline = true;
            this.reasonInput.ScrollBars = ScrollBars.Vertical;
            this.reasonInput.TextChanged += this.ReasonChanged;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Location = new Point(15, 415);
            this.statusLabel.Size = new Size(730, 33);

            this.applyButton.Name = "applyButton";
            this.applyButton.Location = new Point(461, 455);
            this.applyButton.Size = new Size(171, 29);
            this.applyButton.Enabled = false;
            this.applyButton.Click += this.ApplyClicked;

            this.accessButton.Name = "accessButton";
            this.accessButton.Location = new Point(285, 455);
            this.accessButton.Size = new Size(165, 29);
            this.accessButton.Text = "Suspend login";
            this.accessButton.Enabled = false;
            this.accessButton.Click += this.AccessClicked;
            this.transfersButton.Name = "transfersButton";
            this.transfersButton.Text = "Transfers";
            this.transfersButton.Location = new Point(15, 455);
            this.transfersButton.Size = new Size(109, 29);
            this.transfersButton.Click += this.TransfersClicked;
            this.onboardingButton.Name = "onboardingButton";
            this.onboardingButton.Text = "Onboarding";
            this.onboardingButton.Location = new Point(134, 455);
            this.onboardingButton.Size = new Size(140, 29);
            this.onboardingButton.Click += this.OnboardingClicked;
            this.exitButton.Name = "exitButton";
            this.exitButton.Text = "Exit clearance";
            this.exitButton.Location = new Point(610, 11);
            this.exitButton.Size = new Size(143, 29);
            this.exitButton.Click += this.ExitClicked;

            this.closeButton.Name = "closeButton";
            this.closeButton.Location = new Point(649, 455);
            this.closeButton.Size = new Size(104, 29);
            this.closeButton.Text = "Close";
            this.closeButton.DialogResult = DialogResult.Cancel;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(767, 501);
            this.Controls.AddRange(new Control[] {
                this.employeeLabel, this.historyGrid, this.reasonLabel, this.reasonInput,
                this.statusLabel, this.applyButton, this.accessButton, this.transfersButton, this.onboardingButton, this.exitButton, this.closeButton });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "EmployeeLifecycleForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Employee Lifecycle";
            this.CancelButton = this.closeButton;
            this.Load += this.LifecycleLoaded;
            ((System.ComponentModel.ISupportInitialize)this.historyGrid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.historyGrid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label employeeLabel;
        private RadGridView historyGrid;
        private GridViewTextBoxColumn eventColumn;
        private GridViewTextBoxColumn dateColumn;
        private GridViewTextBoxColumn fromColumn;
        private GridViewTextBoxColumn toColumn;
        private GridViewTextBoxColumn reasonColumn;
        private Label reasonLabel;
        private RadTextBox reasonInput;
        private RadButton applyButton;
        private RadButton accessButton;
        private RadButton transfersButton;
        private RadButton onboardingButton;
        private RadButton exitButton;
        private RadButton closeButton;
        private Label statusLabel;
    }
}
