using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsScheduleMoveForm
    {
        private void InitializeComponent()
        {
            this.taskLabel = new Label();
            this.startLabel = new Label();
            this.dueLabel = new Label();
            this.status = new Label();
            this.task = new RadDropDownList();
            this.start = new RadDateTimePicker();
            this.due = new RadDateTimePicker();
            this.preview = new RadButton();
            this.current = new RadButton();
            this.close = new RadButton();
            this.SuspendLayout();
            this.taskLabel.Text = "Task to move";
            this.taskLabel.Location = new Point(14, 13);
            this.taskLabel.Size = new Size(372, 24);
            this.task.Name = "task";
            this.task.Location = new Point(14, 41);
            this.task.Size = new Size(511, 28);
            this.task.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.task.SelectedIndexChanged += this.TaskChanged;
            this.startLabel.Text = "Proposed start";
            this.startLabel.Location = new Point(14, 82);
            this.startLabel.Size = new Size(247, 25);
            this.start.Name = "start";
            this.start.Location = new Point(14, 110);
            this.start.Size = new Size(247, 26);
            this.start.Format = DateTimePickerFormat.Short;
            this.start.ShowCheckBox = true;
            this.start.Checked = false;
            this.dueLabel.Text = "Proposed due";
            this.dueLabel.Location = new Point(278, 82);
            this.dueLabel.Size = new Size(247, 25);
            this.due.Name = "due";
            this.due.Location = new Point(278, 110);
            this.due.Size = new Size(247, 26);
            this.due.Format = DateTimePickerFormat.Short;
            this.due.ShowCheckBox = true;
            this.due.Checked = false;
            this.status.Location = new Point(14, 149);
            this.status.Size = new Size(511, 31);
            this.preview.Name = "preview";
            this.preview.Text = "Preview move";
            this.preview.Location = new Point(294, 190);
            this.preview.Size = new Size(130, 29);
            this.preview.Enabled = false;
            this.preview.Click += this.PreviewClicked;
            this.current.Name = "current";
            this.current.Text = "Use current task dates";
            this.current.Location = new Point(14, 190);
            this.current.Size = new Size(177, 29);
            this.current.DialogResult = DialogResult.Retry;
            this.close.Name = "close";
            this.close.Text = "Cancel";
            this.close.Location = new Point(435, 190);
            this.close.Size = new Size(90, 29);
            this.close.DialogResult = DialogResult.Cancel;
            this.Controls.AddRange(new Control[] {
                this.taskLabel, this.task, this.startLabel, this.start, this.dueLabel, this.due,
                this.status, this.preview, this.current, this.close });
            this.CancelButton = this.close;
            this.AcceptButton = this.preview;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(539, 236);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.Text = "Propose Task Move";
            this.ResumeLayout(false);
        }

        private Label taskLabel, startLabel, dueLabel, status;
        private RadDropDownList task;
        private RadDateTimePicker start, due;
        private RadButton preview, current, close;
    }
}
