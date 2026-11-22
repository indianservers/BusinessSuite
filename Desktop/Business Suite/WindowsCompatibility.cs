using System.Net;
using System.Net.Http;
using System.Runtime.InteropServices;

namespace Business_Suite;

internal sealed class ApiResponseException(string message, HttpStatusCode statusCode)
    : HttpRequestException(message)
{
    public HttpStatusCode StatusCode { get; } = statusCode;
}

internal static class WindowsCompatibility
{
    public static void ReplaceFile(string source, string destination)
    {
        if (File.Exists(destination))
            File.Replace(source, destination, null);
        else
            File.Move(source, destination);
    }
}

internal sealed class CueTextBox : TextBox
{
    private const int SetCueBanner = 0x1501;
    private string placeholderText = "";

    public string PlaceholderText
    {
        get => placeholderText;
        set
        {
            placeholderText = value;
            if (IsHandleCreated)
                SendMessage(Handle, SetCueBanner, IntPtr.Zero, placeholderText);
        }
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        SendMessage(Handle, SetCueBanner, IntPtr.Zero, placeholderText);
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr SendMessage(IntPtr handle, int message, IntPtr wParam, string text);
}
