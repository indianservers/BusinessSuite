using System.Text.Json;
using System.Text.RegularExpressions;
using PhoneNumbers;

namespace Business_Suite;

internal sealed record CrmPhoneNumber(string CallingCode, string National, string International);

internal static class CrmPhone
{
    private static readonly Lazy<(string[] Codes, string DefaultCode)> Contract = new(LoadContract);
    public static string[] CallingCodes => Contract.Value.Codes;
    public static string DefaultCallingCode => Contract.Value.DefaultCode;

    private static (string[], string) LoadContract()
    {
        using var stream = typeof(CrmPhone).Assembly.GetManifestResourceStream("BusinessSuite.ValidationContract.json")
            ?? throw new InvalidOperationException("The shared CRM validation contract is missing.");
        using var json = JsonDocument.Parse(stream);
        return (json.RootElement.GetProperty("countries").EnumerateArray()
                .Select(country => country.GetProperty("code").GetString()!)
                .Distinct(StringComparer.Ordinal).ToArray(),
            json.RootElement.GetProperty("default_calling_code").GetString()!);
    }

    public static CrmPhoneNumber Normalize(string phone, string? code)
    {
        if (code is null || !CallingCodes.Contains(code, StringComparer.Ordinal))
            throw new ArgumentException("Select a supported country calling code.");
        if (Regex.IsMatch(phone, @"[^0-9+ ().-]"))
            throw new ArgumentException("Enter a valid phone number.");

        string national = Regex.Replace(phone.Trim(), @"[ ().-]", "");
        if (national.StartsWith("+", StringComparison.Ordinal))
        {
            if (!national.StartsWith(code, StringComparison.Ordinal))
                throw new ArgumentException("Phone number does not match its country code.");
            national = national.Substring(code.Length);
        }
        if (!Regex.IsMatch(national, @"\A[0-9]{4,15}\z"))
            throw new ArgumentException("Enter a national phone number using digits only.");
        if (code == "+91" && national.Length != 10)
            throw new ArgumentException("Indian phone numbers require 10 national digits.");

        var utility = PhoneNumberUtil.GetInstance();
        try
        {
            PhoneNumber parsed = utility.Parse(code + national, null);
            if (!parsed.HasExtension && utility.IsValidNumber(parsed))
                return new(code, utility.GetNationalSignificantNumber(parsed), utility.Format(parsed, PhoneNumberFormat.E164));
        }
        catch (NumberParseException) { }
        throw new ArgumentException("Enter a valid phone number for the selected country.");
    }
}
