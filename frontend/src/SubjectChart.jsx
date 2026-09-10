import React, { useState } from "react";

export default function SubjectChart({ subjects = [] }) {
  const [metric, setMetric] = useState(
    subjects.some((s) => s.marks_out_of_100 != null)
      ? "marks_out_of_100"
      : "progress_percent",
  );
  const [active, setActive] = useState(null);
  const marks = metric === "marks_out_of_100";
  const width = Math.max(640, subjects.length * 78 + 70);
  const x = (i) => 48 + (i * (width - 88)) / Math.max(subjects.length - 1, 1);
  const y = (value) => 200 - value * 1.6;
  let path = "",
    connected = false;
  subjects.forEach((subject, i) => {
    if (subject[metric] == null) {
      connected = false;
      return;
    }
    path += `${connected ? "L" : "M"}${x(i)},${y(subject[metric])} `;
    connected = true;
  });
  const selected = subjects.find((s) => s.subject === active);
  return (
    <article className="panel subject-chart">
      <div className="panel-head">
        <div>
          <h2>Subjects at a glance</h2>
          <p className="muted">
            {marks
              ? "Recorded marks, normalized to a 100-point scale."
              : "Average course progress by subject, from recorded activity."}
          </p>
        </div>
        <div className="chart-tabs" aria-label="Chart measure">
          <button
            aria-pressed={marks}
            onClick={() => {
              setMetric("marks_out_of_100");
              setActive(null);
            }}
          >
            Marks / 100
          </button>
          <button
            aria-pressed={!marks}
            onClick={() => {
              setMetric("progress_percent");
              setActive(null);
            }}
          >
            Progress %
          </button>
        </div>
      </div>
      {subjects.length ? (
        <>
          <div
            className="chart-scroll"
            tabIndex={0}
            aria-label="Subject comparison chart; scroll horizontally for all subjects"
          >
            <svg
              width={width}
              height="250"
              role="img"
              aria-label={`${marks ? "Marks out of 100" : "Progress percentage"} by subject. Missing values are gaps. Exact values are in the table below.`}
            >
              {[0, 25, 50, 75, 100].map((n) => (
                <g key={n}>
                  <line
                    x1="40"
                    x2={width - 20}
                    y1={y(n)}
                    y2={y(n)}
                    stroke="#eaeaea"
                    strokeDasharray="3 4"
                  />
                  <text
                    x="28"
                    y={y(n) + 4}
                    textAnchor="end"
                    fill="#777"
                    fontSize="10"
                  >
                    {n}
                  </text>
                </g>
              ))}
              <path
                d={path}
                fill="none"
                stroke={marks ? "#353535" : "#43836d"}
                strokeWidth="2"
              />
              {subjects.map((s, i) => (
                <g key={s.subject}>
                  {s[metric] != null && (
                    <circle
                      cx={x(i)}
                      cy={y(s[metric])}
                      r={active === s.subject ? 6 : 4}
                      fill={marks ? "#353535" : "#43836d"}
                      tabIndex={0}
                      role="button"
                      aria-label={`${s.subject}: ${s[metric]} ${marks ? "out of 100" : "percent progress"}`}
                      onMouseEnter={() => setActive(s.subject)}
                      onFocus={() => setActive(s.subject)}
                      onClick={() => setActive(s.subject)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setActive(s.subject);
                        }
                      }}
                    >
                      <title>
                        {s.subject}: {s[metric]}
                      </title>
                    </circle>
                  )}
                  <text
                    x={x(i)}
                    y="222"
                    textAnchor="middle"
                    fill="#777"
                    fontSize="10"
                  >
                    {s.subject.length > 11
                      ? s.subject.slice(0, 10) + "…"
                      : s.subject}
                  </text>
                </g>
              ))}
            </svg>
          </div>
          <p className="chart-detail" role="status">
            {selected ? (
              <>
                <strong>{selected.subject}</strong> · {selected[metric]}
                {marks ? " / 100" : "%"} ·{" "}
                {marks ? selected.score_source : "Demo engagement proxy"}
              </>
            ) : (
              "Hover or focus a point for details. Subjects are categories, not a timeline; gaps mean no recorded data."
            )}
          </p>
          {!subjects.some((s) => s[metric] != null) && (
            <p className="notice">
              No {marks ? "marks" : "course progress"} recorded for this
              student. Try the other chart view.
            </p>
          )}
          <details className="subject-data">
            <summary>All subject marks and progress</summary>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Marks / 100</th>
                    <th>Recorded marks</th>
                    <th>Progress</th>
                    <th>Score source</th>
                  </tr>
                </thead>
                <tbody>
                  {subjects.map((s) => (
                    <tr key={s.subject}>
                      <th scope="row">{s.subject}</th>
                      <td>{s.marks_out_of_100 ?? "Not recorded"}</td>
                      <td>
                        {s.maximum != null
                          ? `${s.obtained} / ${s.maximum}`
                          : "—"}
                      </td>
                      <td>
                        {s.progress_percent != null
                          ? `${s.progress_percent}%`
                          : "Not recorded"}
                      </td>
                      <td>{s.score_source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <p className="fine">
            100 is the display scale, not an invented exam total. Marks use
            obtained ÷ full marks × 100; supplied full marks are preserved.
            Hackathon marks take priority where available. Progress is separate
            from marks.
          </p>
        </>
      ) : (
        <p className="empty">
          No subject records are available for this student.
        </p>
      )}
    </article>
  );
}
