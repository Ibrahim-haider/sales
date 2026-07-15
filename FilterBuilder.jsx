
import { Plus, Trash2 } from "lucide-react";

const OPERATORS = [
  ["equals", "Equals"],
  ["not_equals", "Does not equal"],
  ["contains", "Contains"],
  ["not_contains", "Does not contain"],
  ["gt", "Greater than"],
  ["gte", "Greater than or equal"],
  ["lt", "Less than"],
  ["lte", "Less than or equal"],
  ["between", "Between"],
  ["is_blank", "Is blank"],
  ["is_not_blank", "Is not blank"],
];

export default function FilterBuilder({ columns, filters, setFilters, onApply }) {
  const add = () => setFilters([...filters, { column: columns[0] || "", operator: "equals", value: "" }]);
  const update = (idx, key, value) => {
    setFilters(filters.map((f, i) => (i === idx ? { ...f, [key]: value } : f)));
  };
  const remove = (idx) => setFilters(filters.filter((_, i) => i !== idx));

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h3>Filters</h3>
          <p>Create Excel-like filter rules.</p>
        </div>
        <div className="inline-actions">
          <button className="secondary-button" onClick={add}><Plus size={16}/> Add filter</button>
          <button className="primary-button" onClick={onApply}>Apply</button>
        </div>
      </div>

      <div className="filter-list">
        {filters.length === 0 && <div className="empty-row">No filters applied.</div>}
        {filters.map((filter, idx) => (
          <div className="filter-row" key={idx}>
            <select value={filter.column} onChange={(e) => update(idx, "column", e.target.value)}>
              {columns.map((col) => <option key={col} value={col}>{col}</option>)}
            </select>
            <select value={filter.operator} onChange={(e) => update(idx, "operator", e.target.value)}>
              {OPERATORS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            {!["is_blank", "is_not_blank"].includes(filter.operator) && (
              <input
                value={filter.value ?? ""}
                onChange={(e) => update(idx, "value", e.target.value)}
                placeholder="Value"
              />
            )}
            {filter.operator === "between" && (
              <input
                value={filter.value2 ?? ""}
                onChange={(e) => update(idx, "value2", e.target.value)}
                placeholder="Second value"
              />
            )}
            <button className="icon-button danger" onClick={() => remove(idx)}><Trash2 size={17}/></button>
          </div>
        ))}
      </div>
    </div>
  );
}
