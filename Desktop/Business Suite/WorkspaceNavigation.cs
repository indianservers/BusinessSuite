namespace Business_Suite;

internal static class WorkspaceNavigation
{
    internal static void OpenPage(IWin32Window owner, string path)
    {
        MessageBox.Show(owner, "This screen is still being built for the desktop app.", "Business Suite",
            MessageBoxButtons.OK, MessageBoxIcon.Information);
    }
}
