# Task 2 — LLM Inference Essay (Draft)

> This draft is written to be *directly* pasteable into a submission (Markdown).  
> It is intentionally opinionated and focuses on what matters in real, self-hosted production deployments.

---

## Q1) What LLM(s) would you use for local deployment today, and why?

I’d split “best model” into **best model *per job***, because local deployments fail more often due to *operational mismatch* (VRAM, latency, concurrency, tooling, licensing, safety) than due to raw benchmark deltas.

### A. General-purpose assistant (text + some vision)

**Meta Llama 4 Scout Instruct** is a strong default for on-prem deployments where you want *one* model that covers:
- **high-quality general chat**, 
- **long-context workflows**, and
- **image + text** (important in clinical workflows even if you don’t process full DICOM volumes yet).

Scout is a **Mixture-of-Experts** model with **109B total parameters, 17B active per token, and 16 experts**, and it’s positioned as a “fit on a single server-grade GPU via on-the-fly 4-bit or 8-bit quantization” style model. It’s also explicitly multimodal. citeturn3view0turn24view0

If you need a more permissive license and very strong multilingual performance, I’d also seriously consider **Qwen3.5** variants (e.g., **Qwen3.5-35B-A3B** for efficiency or **Qwen3.5-122B-A10B** if you can afford the VRAM). Qwen’s published lineup includes multiple sizes and MoE variants, and the code/weights are distributed under **Apache 2.0** (generally friendly for enterprise self-hosting). citeturn6view0

### B. “Reasoning-first” assistant (hard problems, planning, math)

If the workload is dominated by deep reasoning (multi-step analysis, longer planning, tool-use), I’d run a reasoning-specialized model such as **DeepSeek-R1** (open weights), and then optionally route “simple” queries to a cheaper model.

DeepSeek-R1 is released as an open-weights model (model card indicates **685B parameters**). citeturn9view0turn8view0  
In practice, for many on-prem settings you’d host a distilled or smaller reasoning model (or do multi-stage routing), because the full 600B+ class models typically require multi-GPU systems.

### C. Code generation / agentic coding

For coding agents, I’d deploy a model explicitly trained for coding and long-context repo navigation. A concrete pick is:

- **Qwen3-Coder-Next** (MoE): model card lists **80B total parameters, ~3B active**, and **256k context**. citeturn7view0

That “few active params” MoE design is attractive for local deployment because you get high throughput per GPU while still benefitting from large total capacity.

### D. What makes a model good for self-hosting (beyond benchmarks)?

Benchmarks don’t tell you whether the model *stays usable* under real constraints. For self-hosted systems, the differentiators are:

- **Licensing & redistribution constraints** (can you run it in a hospital network; can you fine-tune; can you ship it in a product?).  
- **Quantization friendliness** (FP8 / NVFP4 / INT8 / 4-bit with minimal quality loss), and whether the model remains stable under quantization.
- **Inference ecosystem support** (vLLM, TensorRT-LLM, TGI, SGLang) and “known-good” configs. A model that is 3% better but a nightmare to serve is a net loss.
- **Tool / function calling reliability** (structured JSON, stable schemas, low hallucination in tool args).
- **KV-cache behavior at long context**: can you run the context lengths you claim, or will memory explode?
- **Safety controllability**: availability of guardrails, refusal behavior tuning, and the ability to audit outputs.
- **Operational cost**: tokens/sec per GPU at your context lengths and batch sizes; not headline throughput.

---

## Q2) Best-quality model on a single NVIDIA H200 (141GB HBM3e, ~4.8 TB/s)

Given a *single* H200, I would choose:

### **Meta Llama 4 Scout Instruct (served with FP8 or NVFP4)**

Why:

1. **Quality + breadth:** Scout is positioned as a high-end open model that covers general chat and **image+text** use cases, which matters in radiology or other clinical workflows where you might want to condition on images, screenshots, or extracted measurements. citeturn3view0turn24view0  
2. **Memory fit strategy:** H200 provides **141GB VRAM and 4.8 TB/s bandwidth**. citeturn22view0  
   Scout’s **109B parameters** can fit on a single large GPU when using FP8/4-bit style inference (and Scout is explicitly discussed in the ecosystem as something you can run with quantization). citeturn3view0turn23search10  
3. **Throughput expectations:** Because Scout uses ~**17B active params** per token, its decode step “feels” closer to a ~17B-class dense model than a 109B dense model—helpful for latency and tokens/sec. citeturn3view0turn24view0  
4. **Future-proofing:** It gives you a path to multimodal + longer-context experiments without swapping the model family.

If the workload is strictly text-only and you want maximum robustness with minimal serving complexity, a dense 70B-class model can also be a reasonable choice on an H200—but Scout is the more “clinical-multimodal-ready” pick.

---

## Q3) Expected tokens/sec for a single user + how to speed it up

### A. What tokens/sec should you expect?

Tokens/sec depends heavily on:
- input length (prefill),
- output length (decode),
- max context/KV cache,
- and whether you’re optimizing for single-user latency vs batch throughput.

As a sanity check from NVIDIA’s own benchmarking docs:  
- **Llama-3.1-8B** on **1× H200** shows throughput on the order of **~228 tokens/s** at a short 200-in/200-out setting. citeturn10view0  
- **Llama-3.3-70B** on **2× H200** shows **~57 tokens/s** at a larger 5000-in/500-out setting. citeturn10view0  

Scout (17B active) should land between these in practice. For a *single user* with moderate context (e.g., a few thousand tokens) and FP8/NVFP4 inference, I’d expect roughly:

- **~80–180 tokens/s** for decoding (streaming output),  
- with time-to-first-token (TTFT) typically dominated by prefill and can vary from **sub-second to multiple seconds** depending on input length.

Those are “engineering planning” numbers, not guarantees. Real throughput falls as you push context length up, because KV-cache traffic becomes the bottleneck.

### B. Where are the bottlenecks?

- **Prefill (TTFT) is usually more compute-bound** (large GEMMs over the prompt). citeturn23search1  
- **Decode (per-token generation) becomes memory-bandwidth and KV-cache bound**, especially at long context. H200’s 4.8 TB/s HBM3e is exactly why it improves inference for LLMs. citeturn22view0  

### C. Concrete ways to speed it up

**1) Use the right serving engine**
- **TensorRT-LLM** (kernel fusion, optimized attention, quantization paths, streaming)  
- **vLLM** (continuous batching + paged attention)  

Both are “industry standard” for squeezing performance out of NVIDIA hardware.

**2) Use FP8 / NVFP4 quantization (carefully)**
vLLM explicitly documents running Scout with **FP8 and NVFP4** quantization on Hopper/Blackwell-class GPUs. citeturn23search10  
Start with FP8 (often minimal quality loss) and consider NVFP4 if you need more headroom (more concurrency / longer context).

**3) Enable paged attention / KV cache management**
Paged attention avoids allocating KV cache as one giant contiguous block, improving utilization and enabling higher concurrency under long contexts (vLLM’s big win).

**4) Continuous batching + request scheduling**
For an interactive app, you want:
- micro-batching for GPU utilization,
- latency caps per request,
- and separate queues for long-running jobs.

**5) Speculative decoding (if your workload tolerates it)**
A small “draft” model proposes tokens; the big model verifies. This can substantially increase TPS/user for chat-style workloads (especially when answers are fairly predictable).

**6) Reduce the “effective context”**
Even if the model supports huge context windows, in production you often get bigger wins by:
- summarizing conversation history,
- retrieving only relevant documents (RAG),
- and caching prefixes.

---

## Q4) Ideal production inference stack

For an on-prem clinical environment (audit, privacy, uptime), I’d structure the stack like this:

1. **Model artifacts**
   - versioned weights + tokenizer
   - quantization config (FP8/NVFP4) + reproducible build hashes

2. **Inference runtime**
   - vLLM or TensorRT-LLM in a container
   - GPU scheduling (Kubernetes + device plugin, or Slurm for research clusters)
   - optional tensor parallelism for bigger models

3. **Routing + API layer**
   - OpenAI-compatible REST API (so clients can swap providers)
   - request router (model selection: small vs large vs reasoning vs code)
   - auth (OIDC/SAML), rate limits, quotas

4. **Safety + compliance**
   - PHI/PII filters (input/output)
   - policy guardrails, refusal logic, “medical disclaimer” insertion where needed
   - immutable audit logs (who asked what, which model version responded)

5. **Observability**
   - per-request metrics: TTFT, tokens/sec, context length, errors
   - GPU metrics (utilization, HBM use, PCIe/NVLink counters)
   - tracing (OpenTelemetry) across router → inference → retrieval

6. **Retrieval stack (if using RAG)**
   - embedding model (often smaller)
   - vector DB (on-prem: pgvector, Milvus, etc.)
   - document ingestion pipelines with provenance tracking

7. **Frontend / workflow integration**
   - clinician UI (feedback capture, side-by-side comparisons)
   - integrations with PACS/RIS via secure gateways (often read-only at first)

---

## Q5) Dream hardware: B300 servers with 2.1 TB VRAM — what would you host and how to serve a whole radiology department?

A DGX B300-class node (8 GPUs) is described with **2.1 TB total GPU memory** and **14.4 TB/s NVLink bandwidth**. citeturn21view0turn19search14  
That moves you from “what can I cram on one GPU?” to “what large model portfolio can I run as a shared service?”

### A. What I would host

1. **One flagship multimodal model for radiology-style tasks**
   - A Llama 4-class multimodal model for report drafting, protocol suggestions, QA of findings, and image+text workflows. citeturn3view0turn24view0  

2. **One heavy reasoning model**
   - A 600B+ reasoning model (e.g., DeepSeek-R1 class) becomes feasible with multi-GPU tensor parallelism / pipeline parallelism. citeturn9view0  
   Use it only when needed (triage, complex differential reasoning, guideline synthesis), because it is expensive.

3. **Specialist “small” models**
   - embeddings for RAG,
   - structured extraction (ICD codes, key measurements),
   - safety classifiers / hallucination detectors.

### B. How to serve a whole radiology department (scaling plan)

The operational trick is **routing + QoS**, not just raw throughput:

- **Tiered routing:** default to a medium model; escalate to reasoning model when confidence is low or the user explicitly requests deeper analysis.
- **Hard latency budgets:** interactive chat gets priority; long summarization jobs go to a batch queue.
- **Concurrency strategy:** continuous batching + paged attention; cap max output tokens for interactive endpoints.
- **Multi-tenancy:** isolate workloads (departments / services) via separate deployments or GPU partitions (where appropriate).
- **High availability:** at least N+1 nodes (or node-level failover) because a single 8-GPU node is a big blast radius.
- **Data governance:** keep RAG indexes on-prem; log provenance and model versions for every generated report snippet.

A nice detail: with B300-class interconnect, model-parallel inference is no longer “PCIe painful”—the node is designed to behave like a tight multi-GPU system. citeturn21view0turn19search14  

---

*End of draft.*
