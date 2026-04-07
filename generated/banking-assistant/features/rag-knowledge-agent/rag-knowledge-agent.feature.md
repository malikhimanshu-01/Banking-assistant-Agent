# Feature Spec: RAG Knowledge Agent

| Field          | Value                                          |
|----------------|------------------------------------------------|
| **Feature ID** | FEAT-001                                       |
| **Name**       | rag-knowledge-agent                            |
| **Status**     | Draft                                          |
| **Priority**   | Must-Have                                      |
| **Created**    | 2026-03-25                                     |
| **Owner**      | [TBD — requires stakeholder input]             |

---

## 1. Feature Overview

Enable the banking assistant to answer retail customer questions about product terms, fees, and policies by grounding responses in an indexed internal knowledge corpus. This feature covers the full end-to-end pipeline: document ingestion from Azure Blob Storage into Azure AI Search, ongoing index maintenance via an event-driven pipeline, and a dedicated RAG specialist agent that retrieves relevant document chunks and always cites the source document in its response.

---

## 2. Problem Statement

Today, the banking assistant agents (`account_agent`, `payment_agent`, `transaction_agent`) have no access to internal knowledge documents such as FAQs, product policies, or terms and conditions. When customers ask policy or product questions, agents either hallucinate answers or fail to respond accurately. This erodes customer trust and increases escalation rates.

---

## 3. Goals & Non-Goals

### Goals
- Allow retail banking customers to get accurate, document-grounded answers to policy and product questions via the chat widget.
- Build and maintain an Azure AI Search index from a banking knowledge corpus stored in Azure Blob Storage.
- Provide an event-driven ingestion pipeline that keeps the index current whenever new documents are uploaded.
- Integrate a new `rag_knowledge_agent` into the existing `handoff_orchestrator` following the same specialist-agent pattern.
- Always surface the source document reference alongside the answer.
- Respond gracefully when no relevant content is found.

### Non-Goals
- This feature does NOT cover an admin UI for uploading or managing documents.
- This feature does NOT enforce per-customer or per-role access control on documents (all documents are non-sensitive / public-facing).
- This feature does NOT replace the existing `account_agent`, `payment_agent`, or `transaction_agent` for transactional queries.

---

## 4. Target Users & Personas

| Persona                  | Description                                                                                   | Interaction Surface |
|--------------------------|-----------------------------------------------------------------------------------------------|---------------------|
| **Retail Banking Customer** | Individual customer seeking information about product fees, policies, terms, or onboarding requirements. Not a technical user. | Banking web chat widget |
| **Bank Operations Team** | Internal staff responsible for uploading and maintaining knowledge documents in Azure Blob Storage. | Azure Portal / Blob Storage |

---

## 5. User Scenarios

| # | Scenario | User Goal |
|---|----------|-----------|
| 1 | "What are the fees for international transfers?" | Understand the cost before making a transfer |
| 2 | "What is the interest rate on my savings account?" | Verify current product terms |
| 3 | "What are the terms and conditions for my credit card?" | Review contractual obligations |
| 4 | "How do I dispute a transaction?" | Understand the dispute process |
| 5 | "What documents do I need to open a new account?" | Prepare for account onboarding |

---

## 6. Functional Requirements

### FR-001 — Knowledge Corpus Storage
- Banking knowledge documents (FAQs, policy docs, T&Cs, product guides) must be stored in **Azure Blob Storage**.
- Supported document formats: **PDF**.

### FR-002 — Document Ingestion Pipeline
- An ingestion pipeline must process PDF documents from the designated Azure Blob Storage container and populate an Azure AI Search index.
- The pipeline must chunk documents into retrievable segments with associated metadata (source document name, page/section reference where available).
- The pipeline must generate vector embeddings for each chunk to support semantic/vector search.
- The pipeline must be **event-driven**: triggered automatically when a new PDF is uploaded to the Blob Storage container (e.g., via Azure Blob Storage trigger → indexer re-run or custom ingestion function).
- The pipeline must also support **manual re-indexing** to allow a full index rebuild on demand.

### FR-003 — Search Index
- An **Azure AI Search** index must store chunked document content with vector embeddings and metadata.
- The index must support **semantic/vector search** to enable relevance-based retrieval.
- The index must reflect changes within a reasonable time after a new document is uploaded (target: within 10 minutes of upload). [TBD — confirm SLA with stakeholders]

### FR-004 — RAG Knowledge Agent
- A new specialist agent `rag_knowledge_agent` must be implemented in the backend.
- The agent must query the Azure AI Search index using the customer's question as the search query.
- The agent must retrieve the **top 5** most relevant document chunks per query.
- The agent must construct a grounded response using only the retrieved content — no fabrication of information not present in the retrieved chunks.

### FR-005 — Source Citation
- Every response that uses retrieved content **must include a citation** referencing the source document name and, where available, the section or page.
  - Example: *"According to our Credit Card Terms & Conditions (Section 4.2), the late payment fee is £12."*

### FR-006 — No-Match Response
- When no relevant content is found in the index (below confidence threshold [TBD]), the agent must respond with a clear, friendly message:
  - *"I couldn't find information on that in our knowledge base. Please contact our support team for further assistance."*
- The agent must NOT attempt a best-effort or hallucinated answer when no match is found.

### FR-007 — Orchestrator Integration
- The `handoff_orchestrator` must be updated to detect knowledge/policy-type questions and hand off to `rag_knowledge_agent`.
- The integration must follow the existing handoff pattern used for `account_agent`, `payment_agent`, and `transaction_agent`.
- Both `azure_chat` and `foundry_v2` agent implementation variants must be supported.

---

## 7. Non-Functional Requirements

### NFR-001 — Performance
- End-to-end response time (retrieval + generation) must not exceed **5 seconds** under normal load.
- Streaming responses are acceptable — the user may see text as it is generated.

### NFR-002 — Security & Compliance
- All knowledge documents are **non-sensitive and public-facing**; no per-customer or per-role access control is required on the search index.
- Azure Managed Identity must be used for service-to-service authentication (Blob Storage → AI Search → Backend), consistent with existing project security patterns.

### NFR-003 — Reliability
- [TBD — availability SLA, error rate threshold]

### NFR-004 — Observability
- Retrieval queries, retrieved chunk counts, and citation metadata must be captured in Application Insights telemetry, consistent with existing OpenTelemetry setup.

---

## 8. Assumptions & Open Questions

| # | Assumption / Question | Owner | Status |
|---|-----------------------|-------|--------|
| A1 | Documents are non-sensitive; no access control needed on the search index. | Confirmed by user | Closed |
| A2 | Streaming responses are acceptable for the frontend chat widget. | Confirmed by user | Closed |
| A3 | The knowledge corpus already exists or will be provided by the business team. | [TBD] | Open |
| Q1 | What document formats must be supported beyond PDF? | Confirmed by user | Closed — PDF only |
| Q2 | How many top-N chunks should be retrieved per query? | Confirmed by user | Closed — 5 chunks |
| Q3 | What confidence threshold triggers the no-match response? | [TBD — implementation decision] | Open |
| Q4 | How is the search index kept up to date when new documents are added? (manual / scheduled / event-driven pipeline) | Confirmed by user | Closed — event-driven pipeline |
| Q5 | Should the no-match response offer a handoff to a human agent? | [TBD — requires stakeholder input] | Open |

---

## 9. Out of Scope

- Admin UI for uploading or managing knowledge documents
- Per-customer document access control
- Fine-tuning or retraining of the LLM on the knowledge corpus
- Multi-language document support
- Document versioning and rollback
- Support for document formats other than PDF

---

## 10. Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| Azure Blob Storage | Infrastructure | Already provisioned in project (`app/backend/config/`) — requires a dedicated container for knowledge documents |
| Azure AI Search | Infrastructure | New service — must be provisioned via Bicep |
| Azure OpenAI (GPT-4.1) | Infrastructure | Already provisioned — used for embedding generation and response generation |
| Ingestion Pipeline | Code | New component — event-driven function triggered by Blob Storage uploads |
| `handoff_orchestrator` | Code | Must be extended to add RAG agent handoff |
| Banking knowledge corpus (PDF files) | Content | Must be provided by the business/operations team |

---

## 11. User Stories

> User stories will be added here once decomposition is complete.

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| [TBD] | [TBD — pending story decomposition] | [TBD] | Not Started |

---

## 12. Acceptance Criteria (Feature-Level)

| # | Criterion |
|---|-----------|
| AC-001 | When a PDF is uploaded to the designated Blob Storage container, the ingestion pipeline automatically triggers and the document is findable in the Azure AI Search index within 10 minutes. |
| AC-002 | A manual re-index operation can be triggered on demand and successfully rebuilds the full index. |
| AC-003 | A retail customer can ask a policy or product question in the chat widget and receive a response grounded in an indexed knowledge document. |
| AC-004 | Every grounded response includes a citation identifying the source document. |
| AC-005 | When no relevant document is found, the agent responds with the defined no-match message and does not hallucinate an answer. |
| AC-006 | The `handoff_orchestrator` correctly routes policy/product questions to the `rag_knowledge_agent`. |
| AC-007 | End-to-end response time does not exceed 5 seconds under normal load. |
| AC-008 | All retrieval operations and ingestion pipeline events are observable in Application Insights. |

---

## 13. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-03-25 | GitHub Copilot (Product Owner Agent) | Initial draft created from stakeholder interview |
| 2026-03-25 | GitHub Copilot (Product Owner Agent) | Closed Q1 (PDF only), Q2 (top 5 chunks), Q4 (event-driven pipeline) |
| 2026-03-25 | GitHub Copilot (Product Owner Agent) | Expanded scope to include document ingestion pipeline; updated goals, FRs, ACs, dependencies, and personas accordingly |
