using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsResourceCapacityForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.status = new Label();
            this.available = new Label();
            this.personLabel = new Label();
            this.weekLabel = new Label();
            this.hoursLabel = new Label();
            this.person = new RadDropDownList();
            this.week = new RadDateTimePicker();
            this.hours = new RadTextBox();
            this.grid = new RadGridView();
            this.dateColumn = new GridViewTextBoxColumn();
            this.hoursColumn = new GridViewTextBoxColumn();
            this.reasonColumn = new GridViewTextBoxColumn();
            this.preview = new RadButton();
            this.save = new RadButton();
            this.close = new RadButton();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            this.heading.Name = "heading";
            this.heading.Location = new Point(13, 13);
            this.heading.Size = new Size(671, 27);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);
            this.personLabel.Text = "Person";
            this.personLabel.Location = new Point(13, 44);
            this.personLabel.Size = new Size(240, 24);
            this.person.Name = "person";
            this.person.Location = new Point(13, 69);
            this.person.Size = new Size(267, 26);
            this.person.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.person.TextChanged += this.InputsChanged;
            this.weekLabel.Text = "Week starting Monday";
            this.weekLabel.Location = new Point(293, 44);
            this.weekLabel.Size = new Size(156, 24);
            this.week.Name = "week";
            this.week.Location = new Point(293, 69);
            this.week.Size = new Size(155, 26);
            this.week.Format = DateTimePickerFormat.Short;
            this.week.ValueChanged += this.InputsChanged;
            this.hoursLabel.Text = "Baseline hours";
            this.hoursLabel.Location = new Point(461, 44);
            this.hoursLabel.Size = new Size(93, 24);
            this.hours.Name = "hours";
            this.hours.Location = new Point(461, 69);
            this.hours.Size = new Size(93, 26);
            this.hours.Enabled = false;
            this.preview.Name = "preview";
            this.preview.Text = "Preview availability";
            this.preview.Location = new Point(568, 66);
            this.preview.Size = new Size(143, 29);
            this.preview.Enabled = false;
            this.preview.Click += this.PreviewClicked;
            this.grid.Name = "grid";
            this.grid.Location = new Point(13, 109);
            this.grid.Size = new Size(699, 257);
            this.grid.ReadOnly = true;
            this.grid.AutoGenerateColumns = false;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.ShowRowHeaderColumn = false;
            this.dateColumn.Name = "dateColumn";
            this.dateColumn.FieldName = "date";
            this.dateColumn.HeaderText = "Date";
            this.dateColumn.Width = 165;
            this.dateColumn.FormatString = "{0:ddd, d MMM yyyy}";
            this.hoursColumn.Name = "hoursColumn";
            this.hoursColumn.FieldName = "hours";
            this.hoursColumn.HeaderText = "Available hours";
            this.hoursColumn.Width = 135;
            this.hoursColumn.FormatString = "{0:N2}";
            this.reasonColumn.Name = "reasonColumn";
            this.reasonColumn.FieldName = "reason";
            this.reasonColumn.HeaderText = "Availability";
            this.reasonColumn.Width = 393;
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.dateColumn, this.hoursColumn, this.reasonColumn });
            this.available.Location = new Point(13, 375);
            this.available.Size = new Size(444, 24);
            this.status.Location = new Point(13, 404);
            this.status.Size = new Size(433, 45);
            this.save.Name = "save";
            this.save.Text = "Save dated capacity";
            this.save.Location = new Point(460, 408);
            this.save.Size = new Size(140, 29);
            this.save.Enabled = false;
            this.save.Click += this.SaveClicked;
            this.close.Name = "close";
            this.close.Text = "Close";
            this.close.Location = new Point(612, 408);
            this.close.Size = new Size(99, 29);
            this.close.DialogResult = DialogResult.Cancel;
            this.Controls.AddRange(new Control[] { this.heading, this.status, this.available,
                this.personLabel, this.person, this.weekLabel, this.week, this.hoursLabel, this.hours,
                this.grid, this.preview, this.save, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(724, 462);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.Text = "Resource Capacity";
            this.Load += this.CapacityLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
        }

        private Label heading, status, available, personLabel, weekLabel, hoursLabel;
        private RadDropDownList person;
        private RadDateTimePicker week;
        private RadTextBox hours;
        private RadGridView grid;
        private GridViewTextBoxColumn dateColumn, hoursColumn, reasonColumn;
        private RadButton preview, save, close;
    }
}
