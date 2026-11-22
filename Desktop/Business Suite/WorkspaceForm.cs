using System.ComponentModel;
using System.Diagnostics;

namespace Business_Suite;

public class WorkspaceForm : Form
{
    private readonly FlowLayoutPanel links = new() { Dock = DockStyle.Fill, AutoScroll = true };

    public WorkspaceForm() : this("Workspace", "") { }

    protected WorkspaceForm(string title, string description)
    {
        Text = $"Business Suite | {title}";
        StartPosition = FormStartPosition.CenterParent;
        ClientSize = new Size(600, 350);
        Font = new Font("Segoe UI", 10);
        BackColor = Color.FromArgb(243, 246, 251);
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(24), ColumnCount = 1, RowCount = 3 };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 53));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.Controls.Add(new Label { Text = title, Dock = DockStyle.Fill, Font = new Font("Segoe UI Semibold", 21) }, 0, 0);
        layout.Controls.Add(new Label { Text = description, Dock = DockStyle.Fill }, 0, 1);
        layout.Controls.Add(links, 0, 2);
        Controls.Add(layout);
    }

    protected void AddPage(string label, string path)
    {
        var button = new Button { Text = label, Size = new Size(240, 42), FlatStyle = FlatStyle.Flat, BackColor = Color.White };
        button.Click += (_, _) => OpenPage(this, path);
        links.Controls.Add(button);
    }

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
