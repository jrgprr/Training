import { useState, ChangeEvent, FormEvent } from 'react';
import { api } from '../../services/api';
import { ImportUploadResponse } from '../../types/api';

export function ImportPage() {
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [result, setResult] = useState<ImportUploadResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setSelectedFiles(event.target.files);
    setResult(null);
    setError(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setResult(null);

    if (!selectedFiles || selectedFiles.length === 0) {
      setError('Please choose at least one Garmin file to upload.');
      return;
    }

    const formData = new FormData();
    Array.from(selectedFiles).forEach((file) => formData.append('files', file));

    setLoading(true);
    try {
      const response = await api.uploadImport(formData);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="import-page">
      <h1>Garmin Import</h1>
      <p>Upload Garmin export files to begin the first data ingestion flow.</p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="garmin-files">Choose Garmin files</label>
        <input
          id="garmin-files"
          type="file"
          accept=".fit,.gpx,.tcx,application/octet-stream,text/xml"
          multiple
          onChange={handleFileChange}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Uploading...' : 'Upload Files'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {result && (
        <section className="import-result">
          <h2>Import Summary</h2>
          <p>
            Batch <strong>{result.importBatchId}</strong> uploaded with{' '}
            <strong>{result.filesCount}</strong> files.
          </p>
          <p>Status: {result.status}</p>
          <ul>
            {result.files.map((file) => (
              <li key={file.fileHash ?? file.originalFilename}>
                <strong>{file.originalFilename}</strong> ({file.fileType || 'unknown'}) -{' '}
                {file.status}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
