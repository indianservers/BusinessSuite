using System.ComponentModel;
using Telerik.WinControls;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class PosCashCheckoutForm
{
    private void InitializeComponent()
    {
        this.headingLabel = new Label();
        this.customerLabel = new Label();
        this.methodLabel = new Label();
        this.methodPicker = new RadDropDownList();
        this.referenceLabel = new Label();
        this.referenceBox = new RadTextBox();
        this.totalLabel = new Label();
        this.instructionsLabel = new Label();
        this.confirmButton = new RadButton();
        this.cancelButton = new RadButton();
        ((ISupportInitialize)this.confirmButton).BeginInit();
        ((ISupportInitialize)this.methodPicker).BeginInit();
        ((ISupportInitialize)this.referenceBox).BeginInit();
        ((ISupportInitialize)this.cancelButton).BeginInit();
        this.SuspendLayout();

        this.headingLabel.Name = "headingLabel";
        this.headingLabel.Text = "Complete checkout";
        this.headingLabel.Font = new Font("Segoe UI Semibold", 17F);
        this.headingLabel.Location = new Point(24, 16);
        this.headingLabel.Size = new Size(367, 34);
        this.customerLabel.Name = "customerLabel";
        this.customerLabel.Location = new Point(24, 61);
        this.customerLabel.Size = new Size(367, 23);
        this.totalLabel.Name = "totalLabel";
        this.totalLabel.Font = new Font("Segoe UI Semibold", 21F);
        this.totalLabel.Location = new Point(24, 92);
        this.totalLabel.Size = new Size(367, 48);
        this.instructionsLabel.Name = "instructionsLabel";
        this.instructionsLabel.Text = "Confirm the store has already received this payment. Card, UPI and bank transfers are recorded here after they are received.";
        this.instructionsLabel.Location = new Point(24, 151);
        this.instructionsLabel.Size = new Size(367, 49);

        this.methodLabel.Name = "methodLabel";
        this.methodLabel.Text = "Payment method";
        this.methodLabel.Location = new Point(24, 204);
        this.methodLabel.Size = new Size(125, 25);
        this.methodPicker.Name = "methodPicker";
        this.methodPicker.AccessibleName = "Payment method";
        this.methodPicker.DropDownStyle = RadDropDownStyle.DropDownList;
        this.methodPicker.Location = new Point(153, 202);
        this.methodPicker.Size = new Size(238, 27);
        this.methodPicker.SelectedValueChanged += this.TenderChanged;

        this.referenceLabel.Name = "referenceLabel";
        this.referenceLabel.Text = "Payment reference";
        this.referenceLabel.Location = new Point(24, 239);
        this.referenceLabel.Size = new Size(125, 25);
        this.referenceBox.Name = "referenceBox";
        this.referenceBox.AccessibleName = "Payment reference";
        this.referenceBox.Location = new Point(153, 237);
        this.referenceBox.Size = new Size(238, 27);
        this.referenceBox.MaxLength = 120;

        this.confirmButton.Name = "confirmButton";
        this.confirmButton.Text = "Confirm payment received";
        this.confirmButton.Location = new Point(105, 281);
        this.confirmButton.Size = new Size(183, 30);
        this.confirmButton.DialogResult = DialogResult.OK;
        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Text = "Back";
        this.cancelButton.Location = new Point(297, 281);
        this.cancelButton.Size = new Size(94, 30);
        this.cancelButton.DialogResult = DialogResult.Cancel;

        this.AutoScaleDimensions = new SizeF(7F, 15F);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(415, 333);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.StartPosition = FormStartPosition.CenterParent;
        this.CancelButton = this.cancelButton;
        this.Name = "PosCashCheckoutForm";
        this.Text = "Complete checkout";
        this.Controls.Add(this.headingLabel);
        this.Controls.Add(this.customerLabel);
        this.Controls.Add(this.methodLabel);
        this.Controls.Add(this.methodPicker);
        this.Controls.Add(this.referenceLabel);
        this.Controls.Add(this.referenceBox);
        this.Controls.Add(this.totalLabel);
        this.Controls.Add(this.instructionsLabel);
        this.Controls.Add(this.confirmButton);
        this.Controls.Add(this.cancelButton);
        ((ISupportInitialize)this.confirmButton).EndInit();
        ((ISupportInitialize)this.methodPicker).EndInit();
        ((ISupportInitialize)this.referenceBox).EndInit();
        ((ISupportInitialize)this.cancelButton).EndInit();
        this.ResumeLayout(false);
    }

    private Label headingLabel;
    private Label customerLabel;
    private Label methodLabel;
    private RadDropDownList methodPicker;
    private Label referenceLabel;
    private RadTextBox referenceBox;
    private Label totalLabel;
    private Label instructionsLabel;
    private RadButton confirmButton;
    private RadButton cancelButton;
}
