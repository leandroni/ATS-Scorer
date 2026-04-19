import React, { useState } from "react";
import axios from "axios";

function App() {
  const [file, setFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setResult(null);
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setResult(null);
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("job_description", jobDescription);
    try {
      const res = await axios.post("/api/analyze", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Error analyzing resume");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 600, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>ATS Resume Checker</h1>
      <form onSubmit={handleSubmit} style={{ marginBottom: 24 }}>
        <div style={{ marginBottom: 12 }}>
          <label>
            <b>Upload PDF Resume:</b>
            <input type="file" accept="application/pdf" onChange={handleFileChange} required />
          </label>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>
            <b>Job Description (optional):</b>
            <textarea
              value={jobDescription}
              onChange={e => setJobDescription(e.target.value)}
              rows={4}
              style={{ width: "100%" }}
              placeholder="Paste job description here for keyword matching"
            />
          </label>
        </div>
        <button type="submit" disabled={loading || !file} style={{ padding: "8px 20px" }}>
          {loading ? "Analyzing..." : "Analyze Resume"}
        </button>
      </form>
      {error && <div style={{ color: "red", marginBottom: 16 }}>{error}</div>}
      {result && (
        <div style={{ background: "#f9f9f9", padding: 20, borderRadius: 8 }}>
          <h2>Overall Score: {result.overall_score.toFixed(0)}% [{result.grade}]</h2>
          <ul>
            <li><b>Contact Info:</b> {result.contact.score.toFixed(0)}%</li>
            <li><b>Section Headers:</b> {result.sections.score.toFixed(0)}%</li>
            <li><b>Formatting:</b> {result.formatting.score.toFixed(0)}%</li>
            <li><b>Keywords:</b> {result.keywords.score.toFixed(0)}%</li>
            <li><b>Length:</b> {result.length.score.toFixed(0)}%</li>
            <li><b>Date Formats:</b> {result.dates.score.toFixed(0)}%</li>
          </ul>
          <h3>Top Recommendations</h3>
          <ol>
            {result.all_issues.length === 0 && <li>No major issues detected!</li>}
            {result.all_issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ol>
          <h3>Action Verbs Found ({result.keywords.action_verbs.length}):</h3>
          <div>{result.keywords.action_verbs.join(", ") || <i>None</i>}</div>
          <h3>Quantified Achievements:</h3>
          <div>{result.keywords.metrics_count}</div>
          {result.keywords.jd_match_score !== null && (
            <>
              <h3>Job Description Match: {result.keywords.jd_match_score.toFixed(0)}%</h3>
              <div><b>Matched:</b> {result.keywords.jd_matched.join(", ")}</div>
              <div><b>Missing:</b> {result.keywords.jd_missing.join(", ")}</div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
