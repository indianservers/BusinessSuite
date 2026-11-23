#nullable disable
using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class CrmDealCollaboratorsForm
{
    private RadGridView grid;
    private GridViewTextBoxColumn personColumn;
    private GridViewTextBoxColumn roleColumn;
    private GridViewCheckBoxColumn watchingColumn;
    private ComboBox personBox;
    private ComboBox roleBox;
    private CheckBox watchingBox;
    private Label personLabel;
    private Label roleLabel;
    private Label statusText;
    private Button saveButton;
    private Button removeButton;
    private Button refreshButton;
    private Button closeButton;

    private void InitializeComponent()
    {
        this.grid = new RadGridView();
        this.personColumn = new GridViewTextBoxColumn();
        this.roleColumn = new GridViewTextBoxColumn();
        this.watchingColumn = new GridViewCheckBoxColumn();
        this.personBox = new ComboBox();
        this.roleBox = new ComboBox();
        this.watchingBox = new CheckBox();
        this.personLabel = new Label();
        this.roleLabel = new Label();
        this.statusText = new Label();
        this.saveButton = new Button();
        this.removeButton = new Button();
        this.refreshButton = new Button();
        this.closeButton = new Button();
        this.SuspendLayout();

        this.grid.Name = "grid";
        this.grid.Location = new Point(16, 16);
        this.grid.Size = new Size(681, 279);
        this.grid.ReadOnly = true;
        this.grid.ShowGroupPanel = false;
        this.grid.MasterTemplate.AutoGenerateColumns = false;
        this.grid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.grid.MasterTemplate.AllowAddNewRow = false;
        this.grid.MasterTemplate.AllowDeleteRow = false;
        this.grid.SelectionChanged += this.SelectionChanged;
        this.personColumn.FieldName = "email";
        this.personColumn.Name = "personColumn";
        this.personColumn.HeaderText = "Collaborator";
        this.personColumn.Width = 280;
        this.roleColumn.FieldName = "role";
        this.roleColumn.Name = "roleColumn";
        this.roleColumn.HeaderText = "Role";
        this.roleColumn.Width = 180;
        this.watchingColumn.FieldName = "watching";
        this.watchingColumn.Name = "watchingColumn";
        this.watchingColumn.HeaderText = "In-app notifications";
        this.watchingColumn.Width = 150;
        this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.personColumn, this.roleColumn, this.watchingColumn });
        this.Controls.Add(this.grid);

        this.personLabel.Location = new Point(16, 313);
        this.personLabel.Size = new Size(265, 22);
        this.personLabel.Text = "Eligible person";
        this.Controls.Add(this.personLabel);
        this.personBox.Name = "personBox";
        this.personBox.Location = new Point(16, 339);
        this.personBox.Size = new Size(285, 28);
        this.personBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.personBox.DisplayMember = "Name";
        this.personBox.Enabled = false;
        this.personBox.SelectedIndexChanged += this.PickedPerson;
        this.Controls.Add(this.personBox);

        this.roleLabel.Location = new Point(313, 313);
        this.roleLabel.Size = new Size(176, 22);
        this.roleLabel.Text = "Collaboration role";
        this.Controls.Add(this.roleLabel);
        this.roleBox.Name = "roleBox";
        this.roleBox.Location = new Point(313, 339);
        this.roleBox.Size = new Size(176, 28);
        this.roleBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.roleBox.Items.AddRange(new object[] { "Collaborator", "Secondary Owner", "Lead Originator", "Watcher" });
        this.roleBox.Enabled = false;
        this.roleBox.SelectedIndexChanged += this.SelectionChanged;
        this.Controls.Add(this.roleBox);

        this.watchingBox.Name = "watchingBox";
        this.watchingBox.Location = new Point(499, 339);
        this.watchingBox.Size = new Size(198, 28);
        this.watchingBox.Text = "Send in-app notifications";
        this.watchingBox.Enabled = false;
        this.Controls.Add(this.watchingBox);

        this.statusText.Location = new Point(16, 379);
        this.statusText.Size = new Size(681, 42);
        this.statusText.Text = "Loading collaborators…";
        this.Controls.Add(this.statusText);

        this.refreshButton.Location = new Point(16, 431);
        this.refreshButton.Size = new Size(90, 33);
        this.refreshButton.Text = "Refresh";
        this.refreshButton.Click += this.RefreshClicked;
        this.Controls.Add(this.refreshButton);
        this.removeButton.Location = new Point(329, 431);
        this.removeButton.Size = new Size(141, 33);
        this.removeButton.Text = "Remove selected";
        this.removeButton.Enabled = false;
        this.removeButton.Click += this.RemoveClicked;
        this.Controls.Add(this.removeButton);
        this.saveButton.Location = new Point(482, 431);
        this.saveButton.Size = new Size(119, 33);
        this.saveButton.Text = "Save";
        this.saveButton.Enabled = false;
        this.saveButton.Click += this.SaveClicked;
        this.Controls.Add(this.saveButton);
        this.closeButton.Location = new Point(613, 431);
        this.closeButton.Size = new Size(84, 33);
        this.closeButton.Text = "Close";
        this.closeButton.DialogResult = DialogResult.Cancel;
        this.Controls.Add(this.closeButton);

        this.Name = "CrmDealCollaboratorsForm";
        this.Text = "Deal collaborators and watchers";
        this.ClientSize = new Size(714, 480);
        this.Font = new Font("Segoe UI", 10F);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.StartPosition = FormStartPosition.CenterParent;
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.CancelButton = this.closeButton;
        this.Shown += this.FormShown;
        this.FormClosed += this.FormClosedHandler;
        this.ResumeLayout(false);
        this.PerformLayout();
    }
}
