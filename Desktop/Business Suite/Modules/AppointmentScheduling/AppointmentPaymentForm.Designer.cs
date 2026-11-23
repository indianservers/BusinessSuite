using Telerik.WinControls.UI;

namespace Business_Suite;

partial class AppointmentPaymentForm
{
    private void InitializeComponent()
    {
        this.heading = new Label();
        this.balance = new Label();
        this.amountLabel = new Label();
        this.amount = new RadSpinEditor();
        this.methodLabel = new Label();
        this.method = new RadDropDownList();
        this.referenceLabel = new Label();
        this.reference = new RadTextBox();
        this.context = new Label();
        this.save = new RadButton();
        this.close = new RadButton();
        this.status = new Label();
        this.SuspendLayout();
        this.heading.Name = "heading";
        this.heading.Location = new Point(14, 12);
        this.heading.Size = new Size(516, 28);
        this.heading.Text = "Record payment received";
        this.balance.Name = "balance";
        this.balance.Location = new Point(14, 46);
        this.balance.Size = new Size(516, 31);
        this.amountLabel.Name = "amountLabel";
        this.amountLabel.Location = new Point(14, 87);
        this.amountLabel.Size = new Size(129, 23);
        this.amountLabel.Text = "Amount";
        this.amount.Name = "amount";
        this.amount.Location = new Point(149, 83);
        this.amount.Size = new Size(381, 30);
        this.methodLabel.Name = "methodLabel";
        this.methodLabel.Location = new Point(14, 129);
        this.methodLabel.Size = new Size(129, 23);
        this.methodLabel.Text = "Payment method";
        this.method.Name = "method";
        this.method.Location = new Point(149, 125);
        this.method.Size = new Size(381, 30);
        this.referenceLabel.Name = "referenceLabel";
        this.referenceLabel.Location = new Point(14, 171);
        this.referenceLabel.Size = new Size(129, 23);
        this.referenceLabel.Text = "Reference";
        this.reference.Name = "reference";
        this.reference.Location = new Point(149, 167);
        this.reference.Size = new Size(381, 30);
        this.context.Name = "context";
        this.context.Location = new Point(14, 211);
        this.context.Size = new Size(516, 40);
        this.context.Text = "Record money already received. No charge or transfer will be initiated.";
        this.save.Name = "save";
        this.save.Location = new Point(183, 259);
        this.save.Size = new Size(218, 33);
        this.save.Text = "Record payment";
        this.save.Click += this.SaveClicked;
        this.close.Name = "close";
        this.close.Location = new Point(412, 259);
        this.close.Size = new Size(118, 33);
        this.close.Text = "Close";
        this.close.Click += this.CloseClicked;
        this.status.Name = "status";
        this.status.Location = new Point(14, 306);
        this.status.Size = new Size(516, 44);
        this.heading.Font = new Font("Segoe UI Semibold",14F);
        this.amount.DecimalPlaces = 2;
        this.amount.Minimum = 0.01m;
        this.amount.Maximum = 999999999999.99m;
        this.amount.Value = 0.01m;
        this.method.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.method.Items.AddRange(new RadListDataItem[] { new RadListDataItem("Cash"), new RadListDataItem("UPI"),
            new RadListDataItem("Card"), new RadListDataItem("Bank transfer"), new RadListDataItem("Cheque"), new RadListDataItem("Other") });
        this.method.SelectedIndex = 0;
        this.reference.MaxLength = 120;
        this.save.Enabled = false;
        this.Controls.AddRange(new Control[] { this.heading, this.balance, this.amountLabel, this.amount, this.methodLabel, this.method, this.referenceLabel, this.reference, this.context, this.save, this.close, this.status });
        this.ClientSize = new Size(547,363);
        this.StartPosition = FormStartPosition.CenterParent;
        this.Text = "Record payment received";
        this.Load += this.PaymentLoaded;
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label heading = null!;
    private Label balance = null!;
    private Label amountLabel = null!;
    private RadSpinEditor amount = null!;
    private Label methodLabel = null!;
    private RadDropDownList method = null!;
    private Label referenceLabel = null!;
    private RadTextBox reference = null!;
    private Label context = null!;
    private RadButton save = null!;
    private RadButton close = null!;
    private Label status = null!;
}
