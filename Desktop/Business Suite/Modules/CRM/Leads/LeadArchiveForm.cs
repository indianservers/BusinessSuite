namespace Business_Suite;

public sealed partial class LeadArchiveForm : Form
{
    public LeadArchiveForm()
    {
        InitializeComponent();
    }

    internal LeadArchiveForm(string name) : this() => nameLabel.Text = $"Archive {name}";
    internal string Reason => reasonBox.Text.Trim();
    private void ReasonChanged(object sender, EventArgs e) => archiveButton.Enabled = Reason.Length != 0;
}
