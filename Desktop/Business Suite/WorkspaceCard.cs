using System.ComponentModel;
using System.Drawing;
using System.Drawing.Drawing2D;

namespace Business_Suite;

public sealed class WorkspaceCard : Button
{
    private Color accentColor = Color.DodgerBlue;
    private bool hovered;

    [Category("Appearance")]
    [DefaultValue(typeof(Color), "DodgerBlue")]
    public Color AccentColor
    {
        get => accentColor;
        set
        {
            accentColor = value;
            Invalidate();
        }
    }

    public WorkspaceCard()
    {
        SetStyle(ControlStyles.OptimizedDoubleBuffer, true);
    }

    protected override void OnMouseEnter(EventArgs e)
    {
        base.OnMouseEnter(e);
        hovered = true;
        Invalidate();
    }

    protected override void OnMouseLeave(EventArgs e)
    {
        base.OnMouseLeave(e);
        hovered = false;
        Invalidate();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var graphics = e.Graphics;
        graphics.SmoothingMode = SmoothingMode.AntiAlias;
        graphics.Clear(BackColor);
        var face = new Rectangle(1, 1, Width - 3, Height - 5);
        if (face.Width < 36 || face.Height < 36)
            return;

        using var outline = RoundedRectangle(face, 16);
        var focusColor = Color.FromArgb(124, 176, 240);
        using var fill = new LinearGradientBrush(face, Color.White,
            hovered || Focused ? Color.FromArgb(218, 234, 255) : Color.FromArgb(231, 239, 252), 90f);
        graphics.FillPath(fill, outline);
        var state = graphics.Save();
        graphics.SetClip(outline);
        using (var accentBrush = new SolidBrush(AccentColor))
            graphics.FillRectangle(accentBrush, face.Left, face.Bottom - 5, face.Width, 5);
        graphics.Restore(state);
        using var border = new Pen(hovered || Focused ? focusColor : Color.FromArgb(208, 222, 242));
        graphics.DrawPath(border, outline);

        int imageSize = Height >= 200 ? 88 : 57;
        int imageTop = Height >= 200 ? 20 : 10;
        if (Image != null)
            graphics.DrawImage(Image, (Width - imageSize) / 2, imageTop, imageSize, imageSize);
        const TextFormatFlags centered = TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter |
            TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix;
        int titleY = imageTop + imageSize + 3;
        TextRenderer.DrawText(graphics, Text, Font, new Rectangle(9, titleY, Width - 18, 48), ForeColor, centered);
        using var descriptionFont = new Font("Segoe UI", 9.5f);
        int descriptionY = titleY + 46;
        TextRenderer.DrawText(graphics, AccessibleDescription ?? string.Empty, descriptionFont,
            new Rectangle(12, descriptionY, Width - 24, face.Bottom - descriptionY - 8), Color.FromArgb(61, 82, 113), centered);
        if (Focused && ShowFocusCues)
            ControlPaint.DrawFocusRectangle(graphics, Rectangle.Inflate(face, -7, -7));
    }

    private static GraphicsPath RoundedRectangle(Rectangle rectangle, int radius)
    {
        int diameter = radius * 2;
        var path = new GraphicsPath();
        path.AddArc(rectangle.Left, rectangle.Top, diameter, diameter, 180, 90);
        path.AddArc(rectangle.Right - diameter, rectangle.Top, diameter, diameter, 270, 90);
        path.AddArc(rectangle.Right - diameter, rectangle.Bottom - diameter, diameter, diameter, 0, 90);
        path.AddArc(rectangle.Left, rectangle.Bottom - diameter, diameter, diameter, 90, 90);
        path.CloseFigure();
        return path;
    }
}
