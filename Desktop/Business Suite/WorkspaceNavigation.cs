using System.ComponentModel;
using System.Diagnostics;

namespace Business_Suite;

internal static class WorkspaceNavigation
{
    internal static void OpenPage(IWin32Window owner, string path)
    {
        string origin = File.Exists(Path.Combine(AppContext.BaseDirectory, "Start Local Workspace.cmd"))
            ? "http://127.0.0.1:15434/" : "http://localhost:5173/";
        var destination = new Uri(new Uri(origin), path);
        try
        {
            Process.Start(new ProcessStartInfo(destination.AbsoluteUri) { UseShellExecute = true })?.Dispose();
        }
        catch (Win32Exception)
        {
            MessageBox.Show(owner, "Could not open the local web workspace.", "Business Suite",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
