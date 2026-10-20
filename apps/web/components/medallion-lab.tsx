"use client";

import { useState } from "react";
import Link from "next/link";
import { runMedallionLab, SAMPLE_ORDERS, type PipelineResult } from "@/lib/medallion-lab";
import styles from "./medallion-lab.module.css";

const dollars = (cents: number) => `$${(cents / 100).toFixed(2)}`;

export function MedallionLab() {
  const [source, setSource] = useState(SAMPLE_ORDERS);
  const [report, setReport] = useState<PipelineResult>(() => runMedallionLab(SAMPLE_ORDERS));
  const [dirty, setDirty] = useState(false);
  const [stage, setStage] = useState<"bronze" | "silver" | "gold">("gold");
  const [attempts, setAttempts] = useState(0);
  const isReady = report.errors.length === 0 && report.quarantined.length === 0 && report.silver.length > 0;
  const evaluate = () => {
    setReport(runMedallionLab(source));
    setDirty(false);
    setAttempts((previous) => previous + 1);
  };
  const reset = () => {
    setSource(SAMPLE_ORDERS);
    setReport(runMedallionLab(SAMPLE_ORDERS));
    setStage("gold");
    setDirty(false);
    setAttempts(0);
  };

  return (
    <div className={styles.shell}>
      <header className={styles.hero}>
        <span className={styles.eyebrow}>DATA ENGINEERING / HANDS-ON LAB 01</span>
        <h1>From raw orders to a trustworthy Gold mart.</h1>
        <p>
          Edit an original synthetic order feed, run its medallion pipeline and inspect
          what gets cleaned, rejected, deduplicated and aggregated. This beginner lab
          runs entirely in your browser: no uploads, accounts, persistence or remote code execution.
        </p>
        <Link href="/question-bank?track=data-engineering" className={styles.link}>
          Continue to governed Data Engineering practice →
        </Link>
      </header>
      <div className={styles.layout}>
        <section className={styles.panel} aria-label="Order feed editor">
          <div className={styles.titleRow}>
            <h2>01 / Raw feed</h2>
            <span>CSV · up to 500 rows · 100 KB</span>
          </div>
          <p>Challenge: fix the negative quantity on the last line, then rerun until the quality gate passes. Duplicated deliveries are automatically deduplicated by event_id.</p>
          <label className={styles.label} htmlFor="lab-csv">Editable order events</label>
          <textarea id="lab-csv" spellCheck={false} value={source} onChange={(event) => { setSource(event.target.value); setDirty(true); }} className={styles.editor} />
          <div className={styles.buttons}>
            <button type="button" onClick={evaluate}>Run pipeline</button>
            <button type="button" onClick={reset} className={styles.secondary}>Reset sample</button>
          </div>
          {dirty && <p role="status" className={styles.notice}>Input changed. Run pipeline to refresh the results.</p>}
          <p className={styles.hint}>Expected columns: event_id, order_id, order_ts (UTC), sku, quantity, unit_price_usd. Duplicate events must have identical payloads.</p>
        </section>
        <section className={styles.panel} aria-label="Pipeline results">
          <div className={styles.titleRow}><h2>02 / Pipeline report</h2><span>{attempts === 0 ? "Sample run" : `${attempts} run${attempts === 1 ? "" : "s"}`}</span></div>
          <div className={styles.metrics}>
            <div><strong>{report.bronze.length}</strong><span>Bronze rows</span></div>
            <div><strong>{report.silver.length}</strong><span>Silver rows</span></div>
            <div><strong>{report.gold.length}</strong><span>Gold groups</span></div>
            <div><strong>{report.duplicates}</strong><span>Exact duplicates</span></div>
          </div>
          <p role="status" className={isReady ? styles.passed : styles.warning}>
            {report.errors.length > 0 ? "Input contract failed" : isReady ? "Quality gate passed: no quarantined rows" : `${report.quarantined.length} quarantined row(s): review your data`}
          </p>
          {report.errors.map((error) => <p role="alert" key={error} className={styles.error}>{error}</p>)}
          {report.quarantined.length > 0 && <div className={styles.quarantine}>
            <h3>Data quality quarantine</h3>
            <ul>{report.quarantined.map((row) => <li key={row.line}>Row {row.line}: {row.reason} {row.eventId ? `(event ${row.eventId})` : ""}</li>)}</ul>
          </div>}
          <div role="tablist" aria-label="Medallion stage" className={styles.tabs}>
            {(["bronze", "silver", "gold"] as const).map((name) => (
              <button type="button" role="tab" aria-selected={stage === name} key={name} onClick={() => setStage(name)}>{name}</button>
            ))}
          </div>
          <div role="tabpanel" className={styles.tableWrap}>
            {stage === "bronze" && <table><thead><tr><th>Line</th><th>Event</th><th>Order</th><th>SKU</th><th>Qty (raw)</th></tr></thead><tbody>
              {report.bronze.map((row) => <tr key={row.line}><td>{row.line}</td><td>{row.event_id}</td><td>{row.order_id}</td><td>{row.sku}</td><td>{row.quantity}</td></tr>)}
            </tbody></table>}
            {stage === "silver" && <table><thead><tr><th>Event</th><th>Day (UTC)</th><th>SKU</th><th>Qty</th><th>Amount</th></tr></thead><tbody>
              {report.silver.map((row) => <tr key={row.eventId}><td>{row.eventId}</td><td>{row.day}</td><td>{row.sku}</td><td>{row.quantity}</td><td>{dollars(row.totalCents)}</td></tr>)}
            </tbody></table>}
            {stage === "gold" && <table><thead><tr><th>Day (UTC)</th><th>SKU</th><th>Orders</th><th>Units</th><th>Revenue</th></tr></thead><tbody>
              {report.gold.map((row) => <tr key={`${row.day}/${row.sku}`}><td>{row.day}</td><td>{row.sku}</td><td>{row.orders}</td><td>{row.units}</td><td>{dollars(row.revenueCents)}</td></tr>)}
            </tbody></table>}
            {report[stage].length === 0 && <p className={styles.hint}>No rows in this stage.</p>}
          </div>
        </section>
      </div>
      <section className={styles.disclaimer}>
        <h2>Practice boundary</h2>
        <p>This is a deterministic browser exercise, not a Spark, Iceberg, Airflow or SQL execution service. No candidate score, certification, shared workspace or server-side run is created. Production-grade distributed labs require separate runtime, cost and isolation gates.</p>
      </section>
    </div>
  );
}