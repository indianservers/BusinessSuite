namespace Business_Suite;

internal sealed partial class VerificationForm : Form
{
    public VerificationForm()
    {
        InitializeComponent();
    }

    internal string Code => code.Text.Trim();
    internal string Method => recovery.Checked ? "recovery" : "totp";
}
