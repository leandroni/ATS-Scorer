import React, { useState } from "react";
import axios from "axios";

const CATEGORY_DESCRIPTIONS = {
  contact: "Checks for presence of email, phone, LinkedIn, and GitHub contact info.",
  sections: "Detects standard resume sections (experience, education, skills, etc.).",
  formatting: "Flags multi-column layouts, image-based text, and non-standard characters.",
  keywords: "Counts action verbs, quantified achievements, and job description keyword overlap.",
  length: "Evaluates resume length (pages and word count).",
  dates: "Checks for date ranges in work history.",
};

const CATEGORY_LABELS = {
  contact: "Contact Info",
  sections: "Section Headers",
  formatting: "Formatting",
  keywords: "Keywords",
  length: "Length",
  dates: "Date Formats",
};

const CATEGORY_ORDER = [
  "contact",
  "sections",
  "formatting",
  "keywords",
  "length",
  "dates",
];

function ScoreBar({ score, label }) {
  const color =
    score >= 80 ? "bg-green-500" : score >= 60 ? "bg-yellow-400" : "bg-red-500";
  return (
    <div className="mb-2">
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium">{label}</span>
        <span className="font-mono">{score.toFixed(0)}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded h-3">
        <div
          className={`h-3 rounded ${color}`}
          style={{ width: `${score}%`, transition: "width 0.5s" }}
        ></div>
      </div>
    </div>
  );
}

function CategoryChart({ result }) {
  return (
    <div className="bg-white rounded-lg shadow p-6 mb-8">
      <h3 className="text-lg font-semibold mb-4">Category Scores</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {CATEGORY_ORDER.map((cat) => (
          <div key={cat}>
            <ScoreBar score={result[cat].score} label={CATEGORY_LABELS[cat]} />
            <p className="text-xs text-gray-500 mb-2">{CATEGORY_DESCRIPTIONS[cat]}</p>
            {result[cat].issues && result[cat].issues.length > 0 && (
              <ul className="text-xs text-red-600 list-disc ml-5 mb-2">
                {result[cat].issues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function OverallScore({ score, grade }) {
  const color =
    score >= 80 ? "text-green-600" : score >= 60 ? "text-yellow-500" : "text-red-600";
  return (
    <div className="flex flex-col items-center mb-8">
      <div className={`text-5xl font-bold mb-2 ${color}`}>{score.toFixed(0)}%</div>
      <div className={`text-2xl font-semibold ${color}`}>{grade}</div>
      <div className="text-gray-500 text-sm mt-1">Overall ATS Compatibility Score</div>
    </div>
  );
}

function Recommendations({ issues }) {
  return (
    <div className="bg-white rounded-lg shadow p-6 mb-8">
      <h3 className="text-lg font-semibold mb-2">Top Recommendations</h3>
      {issues.length === 0 ? (
        <div className="text-green-600">No major issues detected!</div>
      ) : (
        <ol className="list-decimal ml-6 text-sm text-gray-700">
          {issues.map((issue, i) => (
            <li key={i}>{issue}</li>
          ))}
        </ol>
      )}
    </div>
  );
}

function KeywordDetails({ keywords }) {
  return (
    <div className="bg-white rounded-lg shadow p-6 mb-8">
      <h3 className="text-lg font-semibold mb-2">Keyword & Action Verb Analysis</h3>
      <div className="mb-2">
        <span className="font-medium">Action Verbs Found ({keywords.action_verbs.length}): </span>
        <span className="text-gray-700">{keywords.action_verbs.join(", ") || <i>None</i>}</span>
      </div>
      <div className="mb-2">
        <span className="font-medium">Quantified Achievements:</span> {keywords.metrics_count}
      </div>
      {keywords.jd_match_score !== null && (
        <div className="mb-2">
          <span className="font-medium">Job Description Match:</span> {keywords.jd_match_score.toFixed(0)}%
          <div className="text-xs text-gray-500 mt-1">
            <b>Matched:</b> {keywords.jd_matched.join(", ")}
            <br />
            <b>Missing:</b> {keywords.jd_missing.join(", ")}
          </div>
        </div>
      )}
    </div>
  );
}

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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-100 py-10 px-2">
      <div className="max-w-3xl mx-auto">
        <div className="bg-white rounded-lg shadow p-8 mb-8">
          <h1 className="text-3xl font-bold mb-2 text-blue-700">ATS Resume Checker</h1>
          <p className="text-gray-600 mb-6">
            Upload your PDF resume and (optionally) a job description to receive a detailed ATS compatibility report. Each category is scored and explained below.
          </p>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block font-medium mb-1">Upload PDF Resume:</label>
              <input
                type="file"
                accept="application/pdf"
                onChange={handleFileChange}
                required
                className="block w-full text-sm text-gray-700 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </div>
            <div>
              <label className="block font-medium mb-1">Job Description (optional):</label>
              <textarea
                value={jobDescription}
                onChange={e => setJobDescription(e.target.value)}
                rows={4}
                className="block w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                placeholder="Paste job description here for keyword matching"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !file}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-2 rounded shadow disabled:opacity-50"
            >
              {loading ? "Analyzing..." : "Analyze Resume"}
            </button>
          </form>
          {error && <div className="text-red-600 mt-4">{error}</div>}
        </div>
        {result && (
          <>
            <OverallScore score={result.overall_score} grade={result.grade} />
            <CategoryChart result={result} />
            <Recommendations issues={result.all_issues} />
            <KeywordDetails keywords={result.keywords} />
          </>
        )}
      </div>
      <footer className="text-center text-xs text-gray-400 mt-10">
        &copy; {new Date().getFullYear()} ATS Resume Checker. Powered by FastAPI & React.
      </footer>
    </div>
  );
}

export default App;