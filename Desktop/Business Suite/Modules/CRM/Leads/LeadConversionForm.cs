using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class LeadConversionForm : Form
{
    private readonly DataRow? lead;
    private readonly CancellationTokenSource lifetime = new();
    private bool converting;
    internal LeadConversionResult? Result { get; private set; }

    public LeadConversionForm() : this(null) { }

    internal LeadConversionForm(DataRow? lead)
    {
        this.lead = lead;
        InitializeComponent();
        if (lead is not null)
        {
            string company = LeadStore.Text(lead, "company_name");
            customerTypeBox.SelectedIndex = company.Length == 0 ? 0 : 1;
            nameField(company.Length == 0 ? LeadStore.Text(lead, "full_name") : company);
        }

        void nameField(string value) => dealBox.Text = (value.Length > 168 ? value.Substring(0,168) : value) + " opportunity";
    }

    private async void ConversionShown(object sender, EventArgs e)
    {
        if (lead is null)
            return;
        CancellationToken cancellation = lifetime.Token;
        try
        {
            LeadConversionChoices choices = await LeadStore.ReadConversionChoices(lead, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            companyBox.DisplayMember = nameof(CrmLookup.Name);
            companyBox.DataSource = choices.Companies;
            contactBox.DisplayMember = nameof(CrmLookup.Name);
            contactBox.DataSource = choices.Contacts;
            int selected = choices.Contacts.FindIndex(contact => contact.Id == choices.LinkedContact);
            if (choices.LinkedContact.HasValue && selected < 0)
            {
                feedback.Text = "The lead's linked contact is archived. Restore it before converting.";
                return;
            }
            contactBox.SelectedIndex = Math.Max(0, selected);
            contactBox.Enabled = !choices.LinkedContact.HasValue;
            convertButton.Enabled = true;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (error is NpgsqlException or InvalidOperationException or ArgumentException or IOException or UnauthorizedAccessException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text = "Could not load contact and company choices from PostgreSQL.";
        }
    }

    private void DealChanged(object sender, EventArgs e) => dealBox.Enabled = dealCheck.Checked;

    private async void ConvertClicked(object sender, EventArgs e)
    {
        if (lead is null || converting || !convertButton.Enabled)
            return;
        converting = true;
        convertButton.Enabled = cancelButton.Enabled = false;
        feedback.Text = "Converting lead…";
        try
        {
            Result = await LeadStore.ConvertAsync(LeadStore.Key(lead),
                new((contactBox.SelectedItem as CrmLookup)?.Id, (companyBox.SelectedItem as CrmLookup)?.Id,
                    customerTypeBox.SelectedIndex == 0, dealCheck.Checked, dealBox.Text.Trim()), lifetime.Token);
            converting = false;
            DialogResult = DialogResult.OK;
            Close();
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException)
        {
            feedback.Text = error.Message;
        }
        catch (Exception error) when (error is NpgsqlException or JsonException or IOException or UnauthorizedAccessException)
        {
            feedback.Text = "Could not convert the lead. Refresh the directory and check local PostgreSQL.";
        }
        finally
        {
            converting = false;
            if (!IsDisposed)
                convertButton.Enabled = cancelButton.Enabled = true;
        }
    }

    private void ConversionClosing(object sender, FormClosingEventArgs e) => e.Cancel = converting;
    private void ConversionClosed(object sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
