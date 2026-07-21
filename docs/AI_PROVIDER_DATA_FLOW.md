# AI Provider Data-flow Assessment

Private code, resumes, interview audio, transcripts, and design documents are denied external processing by default. A user or organization must grant purpose-specific consent. Before a call, the gateway classifies data, redacts supported identifiers, verifies tenant/provider policy and regional configuration, selects a versioned prompt and model capability record, and applies token/cost limits.

After a call, the gateway validates structure, scans output, records provider/model/prompt metadata and usage, and stores only policy-allowed traces. Provider retention/training terms and regional availability are versioned configuration with effective dates; unknown capabilities remain unknown.

