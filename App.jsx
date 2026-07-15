
import { useMemo, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import { Download, FileSpreadsheet, Filter, Table2, BarChart3, Calculator, Map } from "lucide-react";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

import { api, API_BASE } from "./api";
import UploadPanel from "./components/UploadPanel";
import MappingPanel from "./components/MappingPanel";
import FilterBuilder from "./components/FilterBuilder";
import CalculatedColumn from "./components/CalculatedColumn";
import AnalysisBuilder from "./components/AnalysisBuilder";

const TABS = [
  ["data", "Data", Table2],
  ["mapping", "Mapping", Map],
  ["filters", "Filters", Filter],
  ["formula", "Calculated Columns", Calculator],
  ["analysis", "Analysis", BarChart3],
];

export default function App() {
  const [sessionId, setSessionId] = useState("");
  const [filename, setFilename] = useState("");
  const [sheets, setSheets] = useState([]);
  const [activeSheet, setActiveSheet] = useState("");
  const [columns, setColumns] = useState([]);
  const [records, setRecords] = useState([]);
  const [mapping, setMapping] = useState({});
  const [filters, setFilters] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [activeTab, setActiveTab] = useState("data");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const columnDefs = useMemo(() => columns.map((field) => ({
    field,
    filter: true,
    sortable: true,
    resizable: true,
    editable: false,
    minWidth: 140,
  })), [columns]);

  const upload = async (file) => {
    setLoading(true);
    setMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post("/upload", form);
      setSessionId(data.session_id);
      setFilename(data.filename);
      setSheets(data.sheets);
      setActiveSheet(data.active_sheet);
      setColumns(data.columns);
      setRecords(data.preview);
      setTotalRows(data.rows);
      setMapping(data.suggested_mapping || {});
    } catch (error) {
      setMessage(error.response?.data?.detail || error.message);
    } finally {
      setLoading(false);
    }
  };

  const switchSheet = async (sheet) => {
    const { data } = await api.get(`/sheet/${sessionId}/${encodeURIComponent(sheet)}`);
    setActiveSheet(sheet);
    setColumns(data.columns);
    setRecords(data.preview);
    setTotalRows(data.rows);
    setMapping(data.suggested_mapping || {});
  };

  const applyFilters = async () => {
    const { data } = await api.post("/data", {
      session_id: sessionId,
      filters,
      page: 1,
      page_size: 1000,
    });
    setRecords(data.records);
    setColumns(data.columns);
    setTotalRows(data.total_rows);
    setActiveTab("data");
  };

  const saveMapping = async () => {
    await api.post("/mapping", { session_id: sessionId, mapping });
    setMessage("Mapping saved.");
  };

  const createCalculatedColumn = async (name, expression) => {
    try {
      const { data } = await api.post("/calculated-column", {
        session_id: sessionId,
        name,
        expression,
      });
      setColumns(data.columns);
      setRecords(data.preview);
      setMessage(`Calculated column "${name}" created.`);
    } catch (error) {
      setMessage(error.response?.data?.detail || error.message);
    }
  };

  const aggregate = async (groupBy, metrics) => {
    const { data } = await api.post("/aggregate", {
      session_id: sessionId,
      group_by: groupBy,
      metrics,
      filters,
    });
    return data;
  };

  const exportFile = async (format) => {
    const response = await fetch(`${API_BASE}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, filters, format }),
    });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `filtered_data.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!sessionId) {
    return (
      <main className="landing">
        <div className="brand">
          <FileSpreadsheet size={30} />
          <span>Universal Excel Analytics</span>
        </div>
        <UploadPanel onUpload={upload} loading={loading} />
        {message && <div className="message error">{message}</div>}
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand compact">
          <FileSpreadsheet size={24}/>
          <span>UEA</span>
        </div>

        <nav>
          {TABS.map(([key, label, Icon]) => (
            <button key={key} className={activeTab === key ? "active" : ""} onClick={() => setActiveTab(key)}>
              <Icon size={18}/><span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>{filename}</h1>
            <p>{totalRows.toLocaleString()} rows · {columns.length} columns · Sheet: {activeSheet}</p>
          </div>
          <div className="inline-actions">
            <select value={activeSheet} onChange={(e) => switchSheet(e.target.value)}>
              {sheets.map((sheet) => <option key={sheet}>{sheet}</option>)}
            </select>
            <button className="secondary-button" onClick={() => exportFile("csv")}><Download size={16}/> CSV</button>
            <button className="primary-button" onClick={() => exportFile("xlsx")}><Download size={16}/> Excel</button>
          </div>
        </header>

        {message && <div className="message">{message}</div>}

        <div className="content">
          {activeTab === "data" && (
            <div className="panel grid-panel">
              <div className="panel-header">
                <div>
                  <h3>Data workspace</h3>
                  <p>Sort, resize, pin, hide and filter columns directly from the table headers.</p>
                </div>
              </div>
              <div className="ag-theme-quartz data-grid">
                <AgGridReact
                  rowData={records}
                  columnDefs={columnDefs}
                  pagination
                  paginationPageSize={50}
                  sideBar
                  defaultColDef={{ floatingFilter: true }}
                />
              </div>
            </div>
          )}

          {activeTab === "mapping" && (
            <MappingPanel columns={columns} mapping={mapping} setMapping={setMapping} onSave={saveMapping}/>
          )}

          {activeTab === "filters" && (
            <FilterBuilder columns={columns} filters={filters} setFilters={setFilters} onApply={applyFilters}/>
          )}

          {activeTab === "formula" && (
            <CalculatedColumn onCreate={createCalculatedColumn}/>
          )}

          {activeTab === "analysis" && (
            <AnalysisBuilder columns={columns} records={records} onAggregate={aggregate}/>
          )}
        </div>
      </section>
    </div>
  );
}
