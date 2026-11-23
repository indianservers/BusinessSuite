using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsScheduleCalendarForm
    {
        private void InitializeComponent()
        {
            this.weekdaysLabel = new Label();
            this.holidaysLabel = new Label();
            this.status = new Label();
            this.holidays = new RadTextBox();
            this.preview = new RadButton();
            this.close = new RadButton();
            this.monday = new CheckBox();
            this.tuesday = new CheckBox();
            this.wednesday = new CheckBox();
            this.thursday = new CheckBox();
            this.friday = new CheckBox();
            this.saturday = new CheckBox();
            this.sunday = new CheckBox();
            this.SuspendLayout();
            this.weekdaysLabel.Text = "Working days";
            this.weekdaysLabel.Location = new Point(15, 14);
            this.weekdaysLabel.Size = new Size(260, 24);
            this.holidaysLabel.Text = "Project holidays (YYYY-MM-DD, one per line)";
            this.holidaysLabel.Location = new Point(15, 83);
            this.holidaysLabel.Size = new Size(473, 24);
            this.holidays.Name = "holidays";
            this.holidays.Location = new Point(15, 111);
            this.holidays.Size = new Size(501, 137);
            this.holidays.Multiline = true;
            this.holidays.ScrollBars = ScrollBars.Vertical;
            this.status.Location = new Point(15, 258);
            this.status.Size = new Size(501, 32);
            this.preview.Name = "preview";
            this.preview.Text = "Preview calendar";
            this.preview.Location = new Point(267, 298);
            this.preview.Size = new Size(139, 29);
            this.preview.Click += this.PreviewClicked;
            this.close.Name = "close";
            this.close.Text = "Cancel";
            this.close.Location = new Point(417, 298);
            this.close.Size = new Size(99, 29);
            this.close.DialogResult = DialogResult.Cancel;
            this.monday.Name = "monday";
            this.monday.Text = "Mon";
            this.monday.Location = new Point(15, 42);
            this.monday.Size = new Size(67, 27);
            this.tuesday.Name = "tuesday";
            this.tuesday.Text = "Tue";
            this.tuesday.Location = new Point(86, 42);
            this.tuesday.Size = new Size(67, 27);
            this.wednesday.Name = "wednesday";
            this.wednesday.Text = "Wed";
            this.wednesday.Location = new Point(157, 42);
            this.wednesday.Size = new Size(67, 27);
            this.thursday.Name = "thursday";
            this.thursday.Text = "Thu";
            this.thursday.Location = new Point(228, 42);
            this.thursday.Size = new Size(67, 27);
            this.friday.Name = "friday";
            this.friday.Text = "Fri";
            this.friday.Location = new Point(299, 42);
            this.friday.Size = new Size(67, 27);
            this.saturday.Name = "saturday";
            this.saturday.Text = "Sat";
            this.saturday.Location = new Point(370, 42);
            this.saturday.Size = new Size(67, 27);
            this.sunday.Name = "sunday";
            this.sunday.Text = "Sun";
            this.sunday.Location = new Point(441, 42);
            this.sunday.Size = new Size(67, 27);
            this.Controls.AddRange(new Control[] { this.weekdaysLabel, this.monday, this.tuesday, this.wednesday,
                this.thursday, this.friday, this.saturday, this.sunday, this.holidaysLabel, this.holidays,
                this.status, this.preview, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(531, 343);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.Text = "Project Work Calendar";
            this.ResumeLayout(false);
        }

        private Label weekdaysLabel, holidaysLabel, status;
        private RadTextBox holidays;
        private RadButton preview, close;
        private CheckBox monday, tuesday, wednesday, thursday, friday, saturday, sunday;
    }
}
