
import { useMemo, useState } from "react";
import {
  BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend
} from "recharts";

export default function AnalysisBuilder({ columns, records, onAggregate }) {
  const [groupBy, setGroupBy] = useState("");
  const [metricColumn, setMetricColumn] = useState("");
  const [operation, setOperation] = useState("sum");
  const [chartType, setChartType] = useState("bar");
  const [result, setResult] = useState([]);

  const run = async () => {
    const data = await onAggregate(
      groupBy ? [groupBy] : [],
      [{ column: metricColumn, operation, alias: `${operation}_${metricColumn}` }]
    );
    setResult(data.records || []);
  };

  const valueKey = useMemo(() => metricColumn ? `${operation}_${metricColumn}` : "", [metricColumn, operation]);

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h3>Analysis & charts</h3>
          <p>Build a quick group-by analysis and visualize the result.</p>
        </div>
        <button className="primary-button" onClick={run} disabled={!metricColumn}>Run analysis</button>
      </div>

      <div className="analysis-controls">
        <label>
          Group by
          <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            <option value="">No grouping</option>
            {columns.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label>
          Metric
          <select value={metricColumn} onChange={(e) => setMetricColumn(e.target.value)}>
            <option value="">Select column</option>
            {columns.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label>
          Operation
          <select value={operation} onChange={(e) => setOperation(e.target.value)}>
            {["sum", "mean", "count", "min", "max", "median", "nunique"].map((op) => <option key={op}>{op}</option>)}
          </select>
        </label>
        <label>
          Chart
          <select value={chartType} onChange={(e) => setChartType(e.target.value)}>
            <option value="bar">Bar</option>
            <option value="line">Line</option>
            <option value="pie">Pie</option>
          </select>
        </label>
      </div>

      {result.length > 0 && groupBy && (
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={360}>
            {chartType === "bar" ? (
              <BarChart data={result}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={groupBy} />
                <YAxis />
                <Tooltip />
                <Bar dataKey={valueKey} fill="#2563eb" radius={[6, 6, 0, 0]} />
              </BarChart>
            ) : chartType === "line" ? (
              <LineChart data={result}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={groupBy} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey={valueKey} stroke="#2563eb" strokeWidth={3} />
              </LineChart>
            ) : (
              <PieChart>
                <Tooltip />
                <Pie data={result} dataKey={valueKey} nameKey={groupBy} outerRadius={130} label>
                  {result.map((_, idx) => <Cell key={idx} fill={`hsl(${idx * 47}, 68%, 52%)`} />)}
                </Pie>
              </PieChart>
            )}
          </ResponsiveContainer>
        </div>
      )}

      {result.length > 0 && (
        <div className="result-table">
          <table>
            <thead><tr>{Object.keys(result[0]).map((k) => <th key={k}>{k}</th>)}</tr></thead>
            <tbody>
              {result.map((row, idx) => (
                <tr key={idx}>{Object.values(row).map((v, i) => <td key={i}>{String(v ?? "")}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
