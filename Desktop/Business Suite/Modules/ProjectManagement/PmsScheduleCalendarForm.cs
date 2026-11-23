using System.Globalization;

namespace Business_Suite;

internal sealed partial class PmsScheduleCalendarForm : Form
{
    public PmsScheduleCalendarForm() => InitializeComponent();

    internal PmsScheduleCalendarForm(PmsCalendarDraft draft) : this()
    {
        var weekdays = WeekdayInputs();
        for (int i = 0; i < weekdays.Length; i++)
            weekdays[i].Checked = draft.Weekdays.Contains(i);
        holidays.Text = string.Join(Environment.NewLine, draft.Holidays.Select(day => day.ToString("yyyy-MM-dd",
            CultureInfo.InvariantCulture)));
    }

    internal PmsCalendarDraft? Calendar { get; private set; }

    private CheckBox[] WeekdayInputs() => new[] { monday, tuesday, wednesday, thursday, friday, saturday, sunday };

    private void PreviewClicked(object? sender, EventArgs e)
    {
        int[] weekdays = WeekdayInputs().Select((input, day) => (input, day)).Where(entry => entry.input.Checked)
            .Select(entry => entry.day).ToArray();
        if (weekdays.Length == 0)
        {
            status.Text = "Select at least one working day.";
            return;
        }
        var dates = new List<DateTime>();
        foreach (string token in holidays.Text.Split(new[] { '\t', '\r', '\n', ' ', ',' }, StringSplitOptions.RemoveEmptyEntries))
        {
            if (!DateTime.TryParseExact(token, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var date))
            {
                status.Text = "Enter holiday dates in YYYY-MM-DD format.";
                return;
            }
            dates.Add(date);
        }

        if (dates.Count > 365)
        {
            status.Text = "Enter up to 365 holiday dates.";
            return;
        }
        Calendar = new PmsCalendarDraft(weekdays, dates.ToArray());
        DialogResult = DialogResult.OK;
    }
}
