using System.Drawing;
using System.Drawing.Drawing2D;

namespace Business_Suite;

public sealed class WorkspaceHeader : Panel
{
    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        var bounds = ClientRectangle;
        if (bounds.Width < 2)
            return;

        var graphics = e.Graphics;
        graphics.SmoothingMode = SmoothingMode.AntiAlias;
        float width = bounds.Width;
        using var wave = new GraphicsPath();
        wave.AddBezier(width * .35f, 0, width * .75f, -65, width * .68f, 145, width * .88f, 54);
        wave.AddBezier(width * .88f, 54, width * .94f, 24, width * .97f, 13, width, 18);
        wave.AddLine(width, 18, width, 0);
        wave.CloseFigure();
        using var brush = new LinearGradientBrush(bounds, BackColor, Color.FromArgb(204, 196, 253), 0f);
        graphics.FillPath(brush, wave);
    }
}
