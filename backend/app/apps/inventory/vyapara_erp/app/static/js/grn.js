document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("form.panel");
  if (!form) return;
  const labels = {"received_qty[]":"Received quantity", "batch_no[]":"Batch number", "manufacture_date[]":"Manufacture date", "expiry_date[]":"Expiry date", "serial_numbers[]":"Serial numbers"};
  const prepare = row => {
    for (const [name, label] of Object.entries(labels)) row.querySelector(`[name="${name}"]`)?.setAttribute("aria-label", label);
    if (!row.querySelector('[name="po_item_id[]"]')?.value) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-sm btn-outline-primary";
    button.textContent = "Split batch";
    button.addEventListener("click", () => {
      const copy = row.cloneNode(true);
      copy.querySelectorAll("button").forEach(element => element.remove());
      copy.querySelectorAll('[name="batch_no[]"], [name="manufacture_date[]"], [name="expiry_date[]"], [name="serial_numbers[]"]').forEach(element => { element.value = ""; });
      copy.querySelector('[name="received_qty[]"]').value = "0";
      row.after(copy);
      prepare(copy);
      copy.querySelector('[name="received_qty[]"]').focus();
    });
    row.cells[0].append(button);
  };
  form.querySelectorAll("tbody tr").forEach(prepare);
});
