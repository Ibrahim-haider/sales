
import { useState } from "react";

export default function CalculatedColumn({ onCreate }) {
  const [name, setName] = useState("");
  const [expression, setExpression] = useState("");

  const submit = () => {
    if (!name || !expression) return;
    onCreate(name, expression);
  };

  return (
    <div className="panel">
      <h3>Calculated column</h3>
      <p>Use numeric column names directly, for example: <code>Sales - Cost</code></p>
      <div className="formula-row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New column name" />
        <input value={expression} onChange={(e) => setExpression(e.target.value)} placeholder="Expression" />
        <button className="primary-button" onClick={submit}>Create</button>
      </div>
    </div>
  );
}
