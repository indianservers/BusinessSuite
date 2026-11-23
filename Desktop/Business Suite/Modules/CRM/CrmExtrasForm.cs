using System.ComponentModel;
using System.Text.Json;

namespace Business_Suite;

public sealed partial class CrmExtrasForm : Form
{
    private readonly bool company;
    private readonly BindingList<CrmTaxRegistration> taxRows;
    private readonly BindingList<CrmChannel> channelRows;
    private readonly string initialChannels;
    internal CrmExtras Result { get; }

    public CrmExtrasForm() : this(new CrmExtras(), CrmDirectoryKind.Companies, "", "", "") { }

    internal CrmExtrasForm(CrmExtras extras, CrmDirectoryKind kind, string email, string phone, string code)
    {
        InitializeComponent();
        company = kind == CrmDirectoryKind.Companies;
        Result = extras.Snapshot.Length == 0 ? new CrmExtras() : extras.Copy();
        taxRows = new BindingList<CrmTaxRegistration>(Result.Tax);
        channelRows = new BindingList<CrmChannel>(Result.Channels);
        if (!Result.ChannelsEdited)
        {
            AddLegacyChannel("email", email, null);
            AddLegacyChannel("phone", phone, code);
        }

        customGrid.DataSource = new BindingList<CrmCustomValue>(Result.Custom);
        taxGrid.DataSource = taxRows;
        channelCountryCodeColumn.DataSource = CrmPhone.CallingCodes.Select(code => new CallingCodeChoice(code)).ToArray();
        channelCountryCodeColumn.DisplayMember = nameof(CallingCodeChoice.Code);
        channelCountryCodeColumn.ValueMember = nameof(CallingCodeChoice.Code);
        channelGrid.DataSource = channelRows;
        gstBox.Text = Result.Gst ?? "";
        gstBox.Visible = gstLabel.Visible = !company;
        taxGrid.Visible = taxAddButton.Visible = taxRemoveButton.Visible = company;
        initialChannels = JsonSerializer.Serialize(Result.Channels, CrmExtrasStore.Json);
    }

    private sealed record CallingCodeChoice(string Code);

    private void AddLegacyChannel(string kind, string value, string? code)
    {
        if (!string.IsNullOrWhiteSpace(value) && !Result.Channels.Any(row => row.Kind == kind))
            channelRows.Add(new CrmChannel { Kind = kind, Label = "Primary", Value = value,
                CountryCode = code, Primary = true });
    }

    private void taxAddClicked(object sender, EventArgs e) => taxRows.Add(new CrmTaxRegistration());
    private void channelAddClicked(object sender, EventArgs e) => channelRows.Add(new CrmChannel());

    private void taxRemoveClicked(object sender, EventArgs e)
    {
        if (taxGrid.CurrentRow?.DataBoundItem is CrmTaxRegistration row)
            taxRows.Remove(row);
    }

    private void channelRemoveClicked(object sender, EventArgs e)
    {
        if (channelGrid.CurrentRow?.DataBoundItem is CrmChannel row)
            channelRows.Remove(row);
    }

    private void ApplyClicked(object sender, EventArgs e)
    {
        customGrid.EndEdit();
        taxGrid.EndEdit();
        channelGrid.EndEdit();
        try
        {
            CrmExtras original = Result.Snapshot.Length == 0 ? new CrmExtras()
                : CrmExtrasStore.Decode(Result.Snapshot, Result.Snapshot);
            Result.Gst = string.IsNullOrWhiteSpace(gstBox.Text) ? null : gstBox.Text.Trim();
            if (Result.Gst != original.Gst || JsonSerializer.Serialize(Result.Tax, CrmExtrasStore.Json)
                != JsonSerializer.Serialize(original.Tax, CrmExtrasStore.Json))
                CrmExtrasStore.ValidateTax(Result, company);
            Result.ChannelsEdited |= initialChannels != JsonSerializer.Serialize(Result.Channels, CrmExtrasStore.Json);
            if (Result.ChannelsEdited)
                CrmExtrasStore.NormalizeChannels(Result.Channels);
            else
                Result.Channels = original.Channels;
            DialogResult = DialogResult.OK;
            Close();
        }
        catch (ArgumentException error)
        {
            feedbackLabel.Text = error.Message;
        }
    }
}
