# Browser TensorFlow.js planning brain

The operator now uses TensorFlow.js for generative inference as well as the
existing command classifier. There is no Ollama service or WebLLM dependency.
The classifier remains the cheapest route for supported basic PMS commands.
Other requests can use the explicitly loaded browser model, followed by the
selected configured Gemini, OpenAI or Claude provider on local failure.

## Model and files

Source: [HuggingFaceTB/SmolLM2-135M-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct),
Apache-2.0, pinned revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`.
This is a small instruction-tuned language model, not a classifier and not a
frontier reasoning model. Complex or invalid plans will need fallback. No PMS
fine-tuning or planning-quality benchmark is claimed.

From `frontend`, prepare the pretrained assets before building/deploying:

```powershell
python -m pip install numpy
npm run prepare:operator-llm
npm run build
```

Generated assets live in `frontend/public/models/operator-llm/`:

- `model.json`: pinned architecture, TF.js weight manifest, precision and SHA-256 checksums.
- `weights-0001.bin`, etc.: standard TF.js named tensor weight shards.
- `tokenizer.json`, `tokenizer_config.json`: matching pretrained tokenizer.
- `config.json`, `README.md`, `LICENSE.txt`: upstream configuration/model card and license.

These large generated assets are Git-ignored. Deploy the generated directory
with the frontend. Downloaded source safetensors are cached under
`.local/operator-llm-source/`, outside public hosting. Source hash is verified
against the pinned upstream LFS checksum. Float32 export preserves the original
BF16 values and uses approximately 540 MB. Optional `--precision uint8` reduces
asset size, but requires separate quality evaluation; it still dequantizes to
float32 at runtime and does not reduce runtime tensor memory.

`model.json` is a named-tensor bundle consumed by our `TfjsLlama` decoder; it is
not a generic Layers/GraphModel file for `loadLayersModel`/`loadGraphModel`.
The decoder implements the upstream Llama architecture with TF.js operations:
RMSNorm, rotary position embeddings, grouped-query causal attention, gated
SiLU feed-forward layers, tied embeddings and per-request KV caches.

## Runtime behavior

Open `/pms/operator`, choose a project, then press **Load TensorFlow.js model**.
Loading is explicit and uses same-origin model files. No command or memory is
sent to a model host. A dedicated worker tries WebGL, then TensorFlow.js WASM,
then plain JavaScript CPU. WASM binaries are bundled and served from the PMS
frontend. Inference uses JSON assistant prefill and stops at a complete reply;
decoding is greedy, capped at 768 output tokens and a 4096-token
working context. Load has a five-minute deadline; inference has a two-minute
deadline. Cancel/unload terminates the worker and discards KV caches.

Use the local brain message box for an ongoing conversation. The normal command
box and its editable voice transcript also route unsupported commands into the
loaded brain. Pending brain questions take precedence over the basic parser
for the next command-box answer. Generative revisions retain frozen targets,
parent hashes and the existing run revision flow; their prompts include the
pending parent plan and execution receipts.

Private, owner/project-scoped server memory retains up to 24 turns with revision
checks and idempotent request keys. The first retained turn and five recent turns enter the local prompt;
current authorized PMS data and actual run receipts are fetched for each turn.
Drafts are explicitly distinguished from executed effects. Clear private memory
removes retained turns, increments its revision, and affects the next prompt.

The model may ask a follow-up, answer from context, declare unsupported, or
propose a task/project setup plan. It cannot execute arbitrary code or call
arbitrary URLs. Existing plan schemas, permissions, selection limits and
canonical PMS execution APIs validate drafts. Task mutations, creation,
subtasks, assignments, dependencies, milestones and dates use the existing
review/hash-bound approval flow. Model output alone never approves work.

One repair attempt follows a domain-invalid local draft. Unavailable runtime,
oversized context, malformed/incomplete output, timeout or unsupported output
can use the selected enabled provider if cloud fallback is allowed. Local-only
mode or an unchecked fallback prevents provider calls. Provider keys remain in
admin settings; fallback requests reuse existing redaction, consent, rate limits,
API usage/cost logs and analytics (`purpose=brain_fallback`). Local turns record
model/runtime metadata in the AI audit log without invented provider tokens.
Cloud fallback shares bounded private conversation context with that provider.

## Verification

- `backend/tests/test_ai_operator_brain.py`: owner isolation, follow-ups,
  optimistic memory revisions, replay, clear, local plan validation, no cloud
  calls on local turns, and usage logs for all three fallback providers.
- `playwright/pms-tfjs-brain.spec.ts`: independent NumPy reference logits,
  incremental/chunked KV-cache equivalence, tensor cleanup, and mocked inference
  testing local follow-ups and fallback routing.
- An opt-in real-weight smoke test can run with `PMS_LLM_SMOKE=1` after preparing
  assets. Browser/device performance and PMS planning quality must be assessed
  separately from numerical decoder compatibility.

The exported float32 weights were also checked against the upstream Transformers
Llama implementation: top-ten next-token IDs matched, with maximum checked-logit
error below `0.00001` against an independent NumPy calculation. Early smoke
experiments exposed weak arithmetic and unreliable unconstrained prose/JSON
instruction following in the 135M checkpoint. JSON prefill and short-format
instructions improve the contract, but schema validation does not establish
semantic correctness. Human review remains necessary; do not present this model
as a highly capable autonomous reasoner.
