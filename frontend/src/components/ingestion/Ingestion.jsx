import React, { useState, useRef, useEffect } from 'react';
import { documentsApi, createDocumentEventSource } from '../../api/client';
import { IconUpload, IconFile, IconCheck, IconShield, IconAlert } from '../common/Icons';

export default function Ingestion({ onOpenWorkspace, showToast }) {
  // Form state
  const [file, setFile] = useState(null);
  const [district, setDistrict] = useState('');
  const [tehsil, setTehsil] = useState('');
  const [village, setVillage] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [formError, setFormError] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);

  // Stepper & Stream state
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingDoc, setStreamingDoc] = useState(null);
  const [currentStep, setCurrentStep] = useState('uploaded');
  const [completedSteps, setCompletedSteps] = useState([]);
  const [progressPercent, setProgressPercent] = useState(20);
  const [terminalLogs, setTerminalLogs] = useState([]);
  const [pipelineFinished, setPipelineFinished] = useState(false);
  const [pipelineStatus, setPipelineStatus] = useState('processing');

  const fileInputRef = useRef(null);
  const eventSourceRef = useRef(null);
  const terminalEndRef = useRef(null);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [terminalLogs]);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const validateFile = (selectedFile) => {
    setFormError('');
    if (!selectedFile) return false;

    const validExtensions = /\.(pdf|png|jpg|jpeg|tiff|webp)$/i;
    if (!validExtensions.test(selectedFile.name)) {
      setFormError('Invalid file format. Please upload a PDF, PNG, JPG, JPEG, TIFF, or WEBP deed file.');
      return false;
    }

    const maxSizeBytes = 25 * 1024 * 1024;
    if (selectedFile.size > maxSizeBytes) {
      setFormError(`File size (${(selectedFile.size / 1024 / 1024).toFixed(2)} MB) exceeds 25 MB limit.`);
      return false;
    }

    setFile(selectedFile);
    return true;
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateFile(e.dataTransfer.files[0]);
    }
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setFormError('Please select a scanned land record document to upload.');
      return;
    }

    setFormError('');
    setIsUploading(true);

    const formData = new FormData();
    formData.append('file', file);
    if (district.trim()) formData.append('district', district.trim());
    if (tehsil.trim()) formData.append('tehsil', tehsil.trim());
    if (village.trim()) formData.append('village', village.trim());

    try {
      const res = await documentsApi.upload(formData);
      showToast?.(`Document #${res.id} ingested successfully. Connecting to real-time pipeline...`, 'success');

      // Switch to live SSE stepper
      setStreamingDoc(res);
      setIsStreaming(true);
      setPipelineFinished(false);
      setPipelineStatus('processing');
      setCurrentStep('uploaded');
      setCompletedSteps([]);
      setProgressPercent(20);
      setTerminalLogs([
        `[${new Date().toLocaleTimeString()}] Ingested file '${res.filename}' (SHA-256 generated)`,
        `[${new Date().toLocaleTimeString()}] Connecting to server-sent events for Record #${res.id}...`,
      ]);

      connectSSE(res.id);
    } catch (err) {
      setFormError(err.message || 'Upload failed. Please retry.');
    } finally {
      setIsUploading(false);
    }
  };

  const connectSSE = (docId) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = createDocumentEventSource(
      docId,
      (data) => {
        const time = new Date().toLocaleTimeString();
        const msg = data.message || `Step update: ${data.step}`;
        setTerminalLogs((prev) => [...prev, `[${time}] ${msg}`]);

        if (data.percent) {
          setProgressPercent(data.percent);
        }

        if (data.step === 'ocr' || data.step === 'ocr_processing') {
          setCurrentStep('ocr');
          setCompletedSteps((prev) => Array.from(new Set([...prev, 'uploaded'])));
        } else if (data.step === 'extraction' || data.step === 'field_extraction') {
          setCurrentStep('extraction');
          setCompletedSteps((prev) => Array.from(new Set([...prev, 'uploaded', 'ocr'])));
        } else if (data.step === 'validation') {
          setCurrentStep('validation');
          setCompletedSteps((prev) => Array.from(new Set([...prev, 'uploaded', 'ocr', 'extraction'])));
        } else if (data.event === 'complete' || data.step === 'complete') {
          setCurrentStep('complete');
          setCompletedSteps(['uploaded', 'ocr', 'extraction', 'validation', 'complete']);
          setProgressPercent(100);
          setPipelineFinished(true);
          setPipelineStatus(data.status || 'verified');
          showToast?.(`Pipeline complete for Document #${docId}! Ready for verification.`, 'success');
          if (eventSourceRef.current) {
            eventSourceRef.current.close();
          }
        }
      },
      () => {
        setTerminalLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] Pipeline completed or stream closed.`]);
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
        }
      }
    );

    eventSourceRef.current = es;
  };

  const handleResetForm = () => {
    setFile(null);
    setDistrict('');
    setTehsil('');
    setVillage('');
    setFormError('');
    setIsStreaming(false);
    setStreamingDoc(null);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
  };

  const steps = [
    { id: 'uploaded', num: 1, title: 'Ingest & SHA-256' },
    { id: 'ocr', num: 2, title: 'OCR Recognition' },
    { id: 'extraction', num: 3, title: 'Field Extraction' },
    { id: 'validation', num: 4, title: 'Validation & Fraud' },
    { id: 'complete', num: 5, title: 'Verification Ready' },
  ];

  return (
    <div style={{ maxWidth: 880, margin: '0 auto' }}>
      {!isStreaming ? (
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Ingest Land Record Document</h2>
              <div className="card-subtitle">
                Accepts scanned title deeds, revenue registers, and cadastral maps (PDF / Images $\le$ 25MB)
              </div>
            </div>
          </div>

          <div className="card-body">
            {formError && (
              <div className="gov-alert gov-alert-danger">
                <IconAlert size={16} />
                <div>{formError}</div>
              </div>
            )}

            <form onSubmit={handleUploadSubmit}>
              {/* Dropzone */}
              <div
                className={`upload-dropzone ${isDragOver ? 'dragover' : ''}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragOver(true);
                }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="upload-icon text-gov-navy-800">
                  <IconUpload size={36} />
                </div>
                <div style={{ fontWeight: 700, color: 'var(--gov-navy-900)', fontSize: 14 }}>
                  Click to select or drag & drop deed file
                </div>
                <div style={{ fontSize: 12, color: 'var(--slate-500)', marginTop: 4 }}>
                  Supported formats: PDF, PNG, JPG, JPEG, TIFF, WEBP (Max 25 MB)
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  style={{ display: 'none' }}
                  accept=".pdf,.png,.jpg,.jpeg,.tiff,.webp"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      validateFile(e.target.files[0]);
                    }
                  }}
                />

                {file && (
                  <div className="upload-file-preview" onClick={(e) => e.stopPropagation()}>
                    <IconFile size={16} className="text-gov-navy-700" />
                    <strong>{file.name}</strong>
                    <span className="font-mono text-slate-500 text-xs">
                      ({(file.size / 1024 / 1024).toFixed(2)} MB)
                    </span>
                  </div>
                )}
              </div>

              {/* Jurisdictional Metadata */}
              <div style={{ marginTop: 22 }}>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label" htmlFor="meta-district">
                      Revenue District
                    </label>
                    <input
                      id="meta-district"
                      type="text"
                      className="form-control"
                      placeholder="e.g. Jaipur"
                      value={district}
                      onChange={(e) => setDistrict(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="meta-tehsil">
                      Tehsil / Sub-District
                    </label>
                    <input
                      id="meta-tehsil"
                      type="text"
                      className="form-control"
                      placeholder="e.g. Sanganer"
                      value={tehsil}
                      onChange={(e) => setTehsil(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="meta-village">
                      Village / Mauza
                    </label>
                    <input
                      id="meta-village"
                      type="text"
                      className="form-control"
                      placeholder="e.g. Mansarovar"
                      value={village}
                      onChange={(e) => setVillage(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 18 }}>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={handleResetForm}
                  disabled={isUploading}
                >
                  Clear
                </button>
                <button type="submit" className="btn btn-primary" disabled={isUploading}>
                  <IconUpload size={14} />
                  {isUploading ? 'Ingesting Deed...' : 'Start Ingestion & OCR Pipeline'}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : (
        /* Live SSE Pipeline Stepper Card */
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Real-Time Pipeline Processing Stream</h2>
              <div className="card-subtitle">
                Record #{streamingDoc?.id}: {streamingDoc?.filename}
              </div>
            </div>
            <span
              className={`badge ${
                pipelineFinished
                  ? pipelineStatus === 'verified'
                    ? 'badge-verified'
                    : 'badge-needs_review'
                  : 'badge-processing'
              }`}
            >
              <span className={`status-dot status-dot-${pipelineFinished ? pipelineStatus : 'processing'}`} />
              {pipelineFinished ? pipelineStatus.replace('_', ' ') : 'Processing'}
            </span>
          </div>

          <div className="card-body">
            {/* Progress Bar */}
            <div className="stepper-progress-bar">
              <div
                className="stepper-progress-fill"
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            {/* Stepper Steps */}
            <div className="stepper-steps">
              {steps.map((step) => {
                const isCompleted = completedSteps.includes(step.id);
                const isActive = currentStep === step.id;
                let stepClass = 'stepper-step';
                if (isActive) stepClass += ' active';
                if (isCompleted) stepClass += ' completed';

                return (
                  <div key={step.id} className={stepClass}>
                    <div className="stepper-step-num">
                      {isCompleted ? <IconCheck size={13} className="text-emerald-700 inline" /> : step.num}
                    </div>
                    <div className="stepper-step-title">{step.title}</div>
                    <div className="stepper-step-status">
                      {isCompleted ? 'Completed' : isActive ? 'Processing' : 'Queued'}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Terminal Window */}
            <div className="terminal-window">
              <div className="terminal-titlebar">
                <div className="terminal-window-dots">
                  <span className="dot dot-red" />
                  <span className="dot dot-yellow" />
                  <span className="dot dot-green" />
                </div>
                <span className="terminal-title">live-stream :: /api/v1/documents/{streamingDoc?.id}/events</span>
                <span className="status-dot-pulse" style={{ width: 6, height: 6 }} />
              </div>
              <div className="terminal-body">
                {terminalLogs.map((log, i) => (
                  <div key={i} className="terminal-line">
                    <span className="terminal-prompt">&gt;</span> {log}
                  </div>
                ))}
                <div ref={terminalEndRef} />
              </div>
            </div>

            {/* Actions */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: 22,
              }}
            >
              <button className="btn btn-outline btn-sm" onClick={handleResetForm}>
                ← Ingest Another Deed
              </button>

              {pipelineFinished && (
                <button
                  className="btn btn-success"
                  onClick={() => onOpenWorkspace(streamingDoc?.id)}
                >
                  <IconShield size={14} />
                  Open in Verification Workspace →
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
