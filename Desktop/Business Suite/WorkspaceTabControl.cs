using System.ComponentModel;

namespace Business_Suite;

public sealed class WorkspaceTabControl : TabControl
{
    private const int AdjustTabDisplayRectangle = 0x1328; // TCM_ADJUSTRECT

    protected override void WndProc(ref Message message)
    {
        // Let the active page fill the control at runtime. The designer keeps the
        // native tab strip so each page can be selected and edited on the surface.
        if (message.Msg == AdjustTabDisplayRectangle && !DesignMode &&
            LicenseManager.UsageMode != LicenseUsageMode.Designtime)
        {
            message.Result = IntPtr.Zero;
            return;
        }

        base.WndProc(ref message);
    }
}
