
const LABELS = {
  branch: "Branch",
  zone: "Zone",
  target: "Target",
  sales: "Sales",
  cash_sales: "Cash sales",
  installment_sales: "Installment sales",
  ytd_sales: "YTD sales",
  ytd_target: "YTD target",
  date: "Date",
  quantity: "Quantity",
  category: "Category",
  product: "Product",
};

export default function MappingPanel({ columns, mapping, setMapping, onSave }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h3>Column mapping</h3>
          <p>Confirm how uploaded columns map to standard business fields.</p>
        </div>
        <button className="secondary-button" onClick={onSave}>Save mapping</button>
      </div>
      <div className="mapping-grid">
        {Object.keys(LABELS).map((key) => (
          <label key={key}>
            <span>{LABELS[key]}</span>
            <select
              value={mapping[key] || ""}
              onChange={(e) => setMapping((prev) => ({ ...prev, [key]: e.target.value || null }))}
            >
              <option value="">Not mapped</option>
              {columns.map((col) => (
                <option key={col} value={col}>{col}</option>
              ))}
            </select>
          </label>
        ))}
      </div>
    </div>
  );
}
