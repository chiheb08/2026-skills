# FP32 vs FP16 vs BF16 (and INT8/INT4) — An Easy, Detailed Guide for Junior LLM Engineers

## Introduction (super easy): bits, bytes, then FP32/FP16/BF16

### Step 0 — Bit and Byte (the very basics)

- A **bit** is the smallest piece of storage: it is either **0** or **1**.
- A **byte** is **8 bits**.

This is the basic unit of storage used everywhere in computers (files, RAM, GPU memory).
Reference: Stanford CS101 — [Bits and Bytes](https://web.stanford.edu/class/cs101/bits-bytes.html).


### Step 0.5 — KB/MB/GB conversions (super practical)

First, remember:

- **1 byte = 8 bits**

Now there are **two common ways** people use KB/MB/GB:

#### A) Decimal (SI) — common in networking, marketing

- **1 KB = 1,000 bytes**
- **1 MB = 1,000,000 bytes**
- **1 GB = 1,000,000,000 bytes**
- **1 TB = 1,000,000,000,000 bytes**

**Example:**

- **1 GB = 1,000,000,000 bytes**

#### B) Binary (GiB) — common in OS memory reporting

- **1 KiB = 1,024 bytes**
- **1 MiB = 1,024 KiB = 1,048,576 bytes**
- **1 GiB = 1,024 MiB = 1,073,741,824 bytes**

**Example:**

- **1 GiB = 1,073,741,824 bytes**

#### Quick cheat table

| Unit | Decimal bytes | Binary bytes |
|---|---:|---:|
| KB / KiB | 1,000 | 1,024 |
| MB / MiB | 1,000,000 | 1,048,576 |
| GB / GiB | 1,000,000,000 | 1,073,741,824 |

> When you see “GPU has 24 GB VRAM”, that is usually **decimal GB**.
> When your OS shows “24 GiB”, that is the **binary** version.

### Step 1 — What is inside an LLM? (not words)

Inside the GPU, an LLM is mostly **big tables of numbers** (called tensors).
Those numbers look like: `0.12`, `-1.7`, `3.14`.

Important: your **dataset text** (sentences, PDFs) is not stored as FP32 in the model.
Text becomes **token IDs** (integers), and the model uses **floats** to do math.

### Step 2 — What are FP32 / FP16 / BF16?

They are just different ways to store **one number** using a certain number of **bits**:
- **FP32** stores one number using **32 bits = 4 bytes**
- **FP16** stores one number using **16 bits = 2 bytes**
- **BF16** stores one number using **16 bits = 2 bytes** (same size as FP16)

So the difference is: **how much space each number takes**, and **how much rounding happens**.

### What do these floats store exactly? (real examples)

- **Weights**: the model’s learned memory (billions of float numbers).
- **Embeddings**: float vectors looked up for each token ID.
- **Activations**: temporary float results while the model runs.
- **Logits**: float scores used to pick the next token.

### Picture 1 — bits/bytes and storage (like your example)

![Bits, bytes, and model storage](assets/bits-bytes-storage.png)

### Picture 2 — FP32 vs FP16 vs BF16 (comparison)

![FP32 vs FP16 vs BF16 comparison](assets/fp32-fp16-bf16-comparison.png)

### Picture 3 — where precision is used (training vs inference)

![Training vs inference precision](assets/training-vs-inference-precision.png)

---

## INT4 on CPU: “save bytes, spend decode” (super simple)

Start from this sentence:

> **Ultra-low-bit formats like 4-bit often require extra decoding steps. On CPUs, that decoding can become a bottleneck. You save memory bandwidth but spend more cycles unpacking values.**

### What this means in plain words

- **INT4 (4-bit)** makes weights **smaller**, so the CPU reads fewer bytes from RAM (good).
- But the CPU usually can’t do math directly on “half-a-byte numbers”. So it must **unpack/convert** them first (extra work).

### Why “decoding/unpacking” is needed

A CPU reads memory in chunks like bytes/words. With INT4, weights are stored **packed**:

```text
One byte (8 bits) can store two INT4 values:
  [aaaa bbbb]
   ^^^^ ^^^^
   w1   w2

To use them, the CPU must:
  1) extract aaaa and bbbb
  2) turn them into bigger numbers (int8/float)
  3) apply a scale (and sometimes a zero-point)
```

### The tradeoff (one picture)

![INT4 decode overhead on CPU](assets/int4-decoding-cpu-bottleneck.png)

### “Architecture” view (where the time goes)

```mermaid
flowchart LR
  RAM["RAM / Cache
weights stored"] --> FP16["FP16/BF16 path
use directly"]
  RAM --> INT4["INT4 path
packed values"]
  INT4 --> DEC["Decode/unpack
+ scale"]
  FP16 --> MM1["MatMul"]
  DEC --> MM2["MatMul"]
  MM1 --> OUT1["Output"]
  MM2 --> OUT2["Output"]
```

### When INT4 helps vs hurts (easy rule)

- **Helps** when you are **memory-bandwidth bound** (weights are huge, RAM/cache is the slow part).
- **Hurts** when decoding is slow and becomes the new limit (CPU spends time unpacking instead of doing matmul).

---

## llama.cpp: how it relates to INT4 decoding (simple architecture)

**Yes, `llama.cpp` is related** because it is commonly used to run **quantized models** (often INT8/INT4) on **CPU**.

When the model is INT4, the CPU saves time reading fewer bytes… but it must spend extra work **decoding/unpacking** those 4-bit values so it can do math.

### Very simple architecture

```mermaid
flowchart LR
  F["Quantized model file
(e.g., GGUF INT4)"] --> L["llama.cpp runtime"]
  L --> C["CPU cache/RAM
read packed INT4 weights"]
  C --> D["Decode / dequantize
unpack 4-bit -> int8/float
+ apply scale"]
  D --> M["MatMul / Attention
(main math)"]
  M --> O["Next token
(output)"]

  style D fill:#ffe6b3,stroke:#555,stroke-width:2px
  style M fill:#e6f2ff,stroke:#555,stroke-width:2px
```

### Where the bottleneck can be (one line)

- If **Decode/Dequantize** is slower than the matmul, then decoding becomes the bottleneck on CPU.

### Easy intuition

```text
FP16 path:  read -> matmul
INT4 path:  read -> decode/unpack -> matmul
                   ^ extra step (sometimes expensive on CPU)
```

---

## Training (learning) — where the precisions show up

Training has 3 big steps:

1) **Forward pass** (compute activations + logits)
2) **Backward pass** (compute gradients)
3) **Optimizer step** (update weights)

In practice (common today):
- **Most math (forward/backward)** runs in **BF16** (or FP16) for speed.
- Some sensitive pieces use **FP32** (often accumulation, optimizer states).

### Training diagram

```mermaid
flowchart TB
  A[Batch of token IDs
integers] --> F[Forward pass
activations + logits
usually BF16 or FP16]
  F --> L[Loss
float]
  L --> B[Backward pass
gradients
usually BF16 or FP16]
  B --> O[Optimizer step
updates weights
often FP32 states]
  O --> W[Weights stored for next step
commonly BF16 weights + FP32 master/state]
```

### What is often FP32 during training (simple)

```text
Training uses extra memory compared to inference:
- weights (often BF16/FP16)
- gradients (BF16/FP16)
- optimizer states (often FP32)  <-- very common
- sometimes a FP32 master copy of weights (for stability)
```

---

## Inference (answering) — where the precisions show up

Inference is simpler: **forward pass only**.

In practice (common today):
- Weights are stored as **FP16/BF16** (or **INT8/INT4** if quantized).
- Activations are computed in **FP16/BF16**.
- There are **no gradients** and **no optimizer states**.

### Inference diagram

```mermaid
flowchart LR
  T[Token IDs
integers] --> E[Embedding lookup
weights: FP16/BF16 or INT8/INT4]
  E --> M[Transformer layers
matmul/attention
compute: FP16/BF16]
  M --> P[Logits
float scores]
  P --> S[Sampler
pick next token ID
integer]
```

### The one-line difference

```text
Training = forward + backward + optimizer (extra FP32 states)
Inference = forward only (often lower precision for speed)
```

---

## Explain it like you’re 5 (ELI5)

### The 10-second version

- LLMs do **lots of math**.
- Numbers can be stored as **big careful numbers** (slower, bigger) or **small quick numbers** (faster, smaller).
- If numbers are too small/rough, the model can **make more mistakes**.

Imagine an LLM is a **huge kitchen** that cooks soup using numbers.

### Numbers are stored in “cups”

Computers don’t store “perfect” numbers. They store numbers using a cup that has two important parts:
- **How big the cup can be** (range)
- **How many little marks are on the cup** (precision)

```
Big cup = can hold very big / very small amounts without spilling
More marks = can measure more precisely
```

### FP32, FP16, BF16 (kid version)

- **FP32**: **big cup + many marks**
  - Very safe, very accurate
  - But heavier to carry (uses more memory)

- **FP16**: **small cup + some marks**
  - Lighter and faster
  - But it spills easily (numbers can become too big → `inf`) or disappears (too small → 0)

- **BF16**: **big cup + fewer marks**
  - Almost as safe as FP32 for “not spilling” (good range)
  - Not as precise as FP16, but usually good enough to cook the soup correctly

### Why LLMs care

- When **training** (learning), the kitchen mixes lots of ingredients and the amounts can change a lot.
  - If the cup is too small (FP16), things spill/vanish → training can break.
  - BF16 is popular because the cup is big enough to avoid many spills.

- When **inference** (just serving answers), you mostly want speed.
  - FP16/BF16 are often used because they’re faster and use less memory than FP32.

### INT8 / INT4 (super small cups)

INT8/INT4 are like using **tiny measuring spoons** instead of cups:
- very small storage (cheap!)
- can be fast
- but you lose detail, so you must be careful or the taste (quality) changes

### Quantization (ELI5)

**Quantization** means: instead of storing “smooth” numbers with millions of possible values, we store “chunky” numbers with fewer possible values.

Kid example:
- If you can only count using **0, 1, 2, 3, 4**, you can’t represent **2.7** exactly.
- So you pick the closest: **3**.

That is quantization: **rounding to fewer choices**.

Why people do it for LLMs:
- the model becomes **smaller** (cheaper to store)
- it can run **faster** (less memory to read)

Why it can hurt:
- rounding changes numbers a bit, so answers can change a bit too

### Where FP32 lives vs where text lives (ELI5 diagram)

```mermaid
flowchart TB
  A["Your dataset real data<br/>Text: I love pizza"] --> B["Tokenizer<br/>turns text into IDs"]
  B --> C["Token IDs are integers<br/>Example: 40, 1842, 11690"]
  C --> D["Embedding table<br/>a big grid of numbers"]
  D --> E["Embedding vectors are floats<br/>Example: 0.12, -0.03, 1.80"]
  E --> F["Neural net layers<br/>attention and MLP math"]
  F --> G["Activations are floats<br/>intermediate numbers"]
  G --> H["Logits are floats<br/>scores for next token"]
  H --> I["Sampler picks next token ID<br/>integer"]
  I --> J["Detokenizer<br/>output text"]

  subgraph Precision["Where FP32 or BF16 or FP16 or INT8 can apply"]
    D
    E
    F
    G
    H
  end

  subgraph NotFP["Usually not FP32"]
    A
    B
    C
    I
    J
  end
```

```text
TEXT (dataset) -> tokenizer -> TOKEN IDs (integers)
                      |
                      v
        MODEL NUMBERS (floats) = weights, activations, logits
        Those floats may be stored as FP32 or BF16 or FP16
```


---

## Why this matters (the LLM reality)

Large Language Models are basically **giant math machines**:
- They multiply big matrices (very many times).
- They move huge tensors from memory to GPU cores and back.

So two things dominate your life:
- **How much memory you need** (and memory bandwidth).
- **How fast the GPU can do the math**.

**Numeric precision** (FP32, FP16, BF16, INT8, INT4…) directly affects:
- speed
- memory usage
- stability (will training diverge? will outputs degrade?)

---

## The core concept: numbers are stored with limited “space”

Computers don’t store real numbers perfectly. They store an **approximation** using a fixed number of bits.

### Floating point (FP) in one picture

A floating-point number stores:
- **sign** (positive/negative)
- **exponent** (rough magnitude / scale)
- **mantissa / fraction** (precision / detail)

ASCII diagram:

```
| sign | exponent | mantissa (fraction) |
```

**Intuition**:
- Exponent decides “how big can it get?” (dynamic range)
- Mantissa decides “how finely can it represent values?” (precision)

### Two types of numeric problems

- **Overflow**: number too big → becomes `inf`.
- **Underflow**: number too small → becomes 0 (or a “subnormal”).
- **Rounding error**: value gets rounded because mantissa can’t represent all digits.

---

## FP32 (float32): the safe default

### What it is
FP32 is the classic IEEE-754 32-bit float:

```
sign:     1 bit
exponent: 8 bits
mantissa: 23 bits
```

### What it means
- **Large dynamic range** (thanks to 8 exponent bits)
- **Good precision** (23 mantissa bits)

### In LLM terms
- Training in pure FP32 is **stable**, but expensive.
- Memory cost is high: **4 bytes per number**.

Example:
- A 7B-parameter model in FP32 weights alone is roughly:
  - 7e9 params × 4 bytes ≈ **28 GB** (just weights)

---

## FP16 (float16): faster + smaller, but smaller range

### What it is
IEEE-754 half precision:

```
sign:     1 bit
exponent: 5 bits
mantissa: 10 bits
```

### What it means
- **Much less dynamic range** than FP32 (only 5 exponent bits)
- Less precision (10 mantissa bits)
- Memory: **2 bytes per number** (half of FP32)

### Why FP16 can break training
FP16’s smaller exponent range makes it easier to overflow/underflow.

In training, gradients and activations can vary a lot in magnitude.
- Some values become too small → underflow → gradients become 0
- Some values become too big → overflow → `inf` → loss becomes `nan`

### The classic fix: Mixed Precision + Loss Scaling
Most modern training is **mixed precision**:
- store many tensors in **FP16/BF16** for speed and memory
- do some critical math (often accumulation) in **FP32**

**Loss scaling** idea (simple):
- multiply the loss by a large scale `S`
- gradients become bigger (less underflow)
- after backprop, divide gradients by `S`

Mermaid sketch:

```mermaid
flowchart TB
  L[Loss] --> M[Multiply by scale S]
  M --> BP[Backprop gradients]
  BP --> D[Divide gradients by S]
  D --> OPT[Optimizer step]
```

### Where FP16 shines
- Inference on GPUs that support fast FP16 (Tensor Cores)
- Training when you use mixed precision carefully

---

## BF16 (bfloat16): FP16’s “range” with less precision

BF16 is popular for training because it changes the bit split:

```
sign:     1 bit
exponent: 8 bits
mantissa: 7 bits
```

### The key point
BF16 keeps the **same exponent bits as FP32 (8)**.
- So it has **similar dynamic range** to FP32.
- But it has **less precision** than FP16 (7 vs 10 mantissa bits).

### Why BF16 is great for training
Training stability often depends more on **range** than on ultra-fine precision.
So BF16 tends to:
- avoid many FP16 overflow/underflow issues
- reduce need for aggressive loss scaling

### Tradeoff
- BF16 has coarser precision (more rounding)
- But for many deep learning workloads, it’s “good enough” and stable

---

## FP16 vs BF16: the simplest comparison

Think of it like this:

- **FP16**: more precision detail, but smaller safe range
- **BF16**: larger safe range, but less detail

### Practical LLM rule of thumb
- **Training**: BF16 is often preferred (if hardware supports it)
- **Inference**: FP16 is common (and INT8/INT4 for compression)

Table:

| Format | Bits | Exponent bits | Mantissa bits | Range (rough) | Precision (rough) | Typical use |
|---|---:|---:|---:|---|---|---|
| FP32 | 32 | 8 | 23 | high | high | baseline, sensitive ops |
| FP16 | 16 | 5 | 10 | lower | medium | inference + mixed training |
| BF16 | 16 | 8 | 7  | high | lower | training (stable) |

---

## What actually runs on GPUs: multiply vs accumulate

In neural nets, you do a lot of:

\[
C = A \times B
\]

But internally this is many multiply-adds:

\[
\text{sum} = \sum_i a_i \cdot b_i
\]

### Why accumulation precision matters
Even if each multiply uses FP16/BF16, the **sum** can grow and needs stability.

Common practice:
- multiply in FP16/BF16
- accumulate in FP32

This is one reason mixed precision works so well.

---

## TF32 (you’ll see it on NVIDIA)

TF32 is a Tensor Core mode that behaves like:
- FP32 range (8-bit exponent)
- reduced mantissa precision (roughly 10-bit mantissa behavior)

It’s mainly about speeding up FP32-like training while keeping range.

(You may see this when training with “FP32” settings but getting Tensor Core speedups.)

---

## INT8 and INT4: quantization for inference

Floating point is flexible, but **integers are smaller and faster**.
Quantization stores weights/activations using fewer bits.

### INT8 (8-bit)
- good quality for many models
- widely supported by inference runtimes

### INT4 (4-bit)
- much smaller models
- can be tricky: needs careful quantization methods to keep quality

### What quantization really does
Instead of storing a float weight `w`, you store an integer `q` plus a scale:

\[
 w \approx s \cdot q
\]

Where:
- `q` is INT8 or INT4
- `s` is a float scale (per-tensor, per-channel, etc.)

Mermaid sketch:

```mermaid
flowchart LR
  W[FP weights] --> Q[Quantize<br/>to INT8/INT4]
  Q --> S[Store scale(s)]
  Q --> DQ[Dequantize on the fly]
  S --> DQ
  DQ --> MM[Matmul]
```

### Why this speeds up inference
- weights are smaller → fit in GPU memory better
- less memory bandwidth → often the real bottleneck

### Common LLM inference “precision ladder”
- FP16/BF16: high quality, faster than FP32
- INT8: big speed/memory wins, usually good quality
- INT4: maximum compression, quality depends on method and model

---

## How precision impacts LLM training (what you feel day-to-day)

### 1) Memory footprint
Training uses memory for:
- weights
- gradients
- optimizer states (often 2×–8× weights depending on optimizer)
- activations (can dominate)

Reducing precision can be the difference between:
- “fits on 1 GPU” vs “needs multiple GPUs”

### 2) Speed (Tensor Cores)
Modern GPUs have special hardware for low-precision matrix multiply.
So FP16/BF16 can be **much faster** than FP32.

### 3) Stability
Lower precision increases risk of:
- `nan` loss
- gradient underflow
- training divergence

That’s why BF16 is popular (good range) and why accumulation often stays FP32.

---

## How precision impacts LLM inference (what you care about)

### 1) Latency and throughput
- smaller precision → faster matmuls + less memory traffic

### 2) Cost
- smaller models → more concurrent users per GPU

### 3) Output quality
Quantization can slightly change outputs.
For a blog demo, you can show:
- perplexity difference
- or a small evaluation set comparison

---

## A junior-friendly decision guide

### If you are training from scratch
- Prefer **BF16 mixed precision** if your GPU supports it.
- Keep **optimizer states** in FP32 (common).

### If you are fine-tuning
- BF16 is a strong default.
- If you see instability in FP16, switch to BF16 or add loss scaling.

### If you are deploying inference
- Start with **FP16/BF16**.
- If you need cheaper serving, try **INT8**.
- If you need maximum compression, try **INT4** (validate quality!).

---

## Mini glossary

- **Dynamic range**: how big/small numbers can be before overflow/underflow.
- **Precision**: how many distinct values you can represent between two numbers.
- **Mixed precision**: use low precision for speed/memory, higher precision for stability-critical parts.
- **Loss scaling**: multiply loss to avoid gradient underflow in FP16.
- **Quantization**: represent floats using ints + scale(s) to reduce size and speed up inference.

---

## Quick mental picture (range vs precision)

```
More exponent bits  => bigger safe range (fewer inf/0 issues)
More mantissa bits  => finer precision (less rounding error)

FP16:  exponent small, mantissa bigger
BF16:  exponent big,   mantissa smaller
FP32:  exponent big,   mantissa big
```

---

## Source note

This article is a simplified educational write-up. If you want, tell me what GPU you use (A10, T4, A100, H100, etc.) and what you’re doing (training vs inference), and I can add a small “recommended settings” section tailored to your setup.
