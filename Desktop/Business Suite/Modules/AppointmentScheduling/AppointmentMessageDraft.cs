using System.Globalization;
using System.Text.RegularExpressions;

namespace Business_Suite;

internal static class AppointmentMessageDraft
{
    internal static string Generate(AppointmentConfirmation booking) =>
        $"{booking.Customer}: {booking.Service} with {booking.Provider}, {booking.LocalStart:g} ({booking.Zone}). " +
        $"Reference #{booking.Reference}. Status: {booking.Status}." +
        (string.IsNullOrWhiteSpace(booking.CustomerNotes) ? "" : Environment.NewLine + booking.CustomerNotes);

    internal static string InternationalPhone(string value, string country = "")
    {
        string number = Regex.Replace(value, "[ ()-]", "");
        string prefix = Regex.Replace(country, "[^0-9]", "");
        return number.Length == 0 || number.StartsWith("+", StringComparison.Ordinal) || prefix.Length == 0
            ? number : "+" + prefix + (number.StartsWith("0", StringComparison.Ordinal) ? number.Substring(1) : number);
    }

    internal static string? Link(bool sms, string recipient, string reference, string message)
    {
        string address = sms ? InternationalPhone(recipient) : recipient.Trim();
        if (message.Length > 8000 || string.IsNullOrWhiteSpace(message) ||
            !Regex.IsMatch(address, sms ? @"\A\+[1-9][0-9]{7,14}\z" : @"\A[^@\s\p{C}]+@[^@\s\p{C}]+\.[^@\s\p{C}]+\z"))
            return null;
        string destination = Uri.EscapeDataString(address);
        string body = Uri.EscapeDataString(message);
        return sms ? $"sms:{destination}?body={body}"
            : $"mailto:{destination}?subject={Uri.EscapeDataString("Booking #" + reference)}&body={body}";
    }

    internal static string SmsEstimate(string text)
    {
        const string basic = "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà";
        const string extended = "^{}\\[~]|€";
        int units = 0;
        foreach (char character in text)
        {
            if (basic.IndexOf(character) >= 0)
                units++;
            else if (extended.IndexOf(character) >= 0)
                units += 2;
            else
                return Description(text.Length, 70, 67, "Unicode");
        }
        return Description(units, 160, 153, "GSM-7");
    }

    private static string Description(int units, int single, int multiple, string encoding)
    {
        int segments = units <= single ? Math.Min(1, units) : (units + multiple - 1) / multiple;
        return $"Estimated {segments.ToString(CultureInfo.CurrentCulture)} SMS segment(s), {encoding}";
    }
}
