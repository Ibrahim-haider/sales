
import { UploadCloud } from "lucide-react";

export default function UploadPanel({ onUpload, loading }) {
  const handleChange = (event) => {
    const file = event.target.files?.[0];
    if (file) onUpload(file);
  };

  return (
    <div className="upload-card">
      <UploadCloud size={42} />
      <h2>Upload structured data</h2>
      <p>Excel and CSV are supported. Multiple-sheet Excel workbooks are detected automatically.</p>
      <label className="primary-button">
        {loading ? "Uploading..." : "Choose file"}
        <input
          type="file"
          accept=".xlsx,.xls,.csv"
          onChange={handleChange}
          disabled={loading}
          hidden
        />
      </label>
    </div>
  );
}
