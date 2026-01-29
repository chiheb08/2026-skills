# Filter Representation in Vectorized Query Execution — explained for someone new to IT

If you don’t know IT or databases yet, this is the right version.

## The one-sentence meaning

A **filter representation** is just a way for a database to remember:

> “In this small group of rows, which ones should I keep using, and which ones should I ignore?”

The big reason it exists is to avoid expensive copying of data again and again.

---

## 1) Real-life story (no database words)

Imagine a factory line:

- A **box** contains **1,000 items**.
- The box goes through several **stations**.
- Each station does something to the items.

Now imagine one station checks quality:
- some items are **good**
- some items are **bad**

Question: When the box goes to the next station, how do we handle the bad items?

Two choices:

### Choice A: Copy only the good items into a new box
- You take good items out and build a new box.
- This is simple… but it’s a lot of physical work (copying/moving items).

### Choice B: Keep the same box, but add a “keep/ignore list”
- You don’t move the items.
- You attach a small note that says “these positions are good.”

That small note is the **filter representation**.

---

## 2) Same idea inside a database

A database often processes data in small chunks (a **batch**):
- Instead of working with 1 row, it works with a small group like 1,000 rows.

Why? Because doing work in groups is usually faster for the computer.

In this document:
- **row** = one record (like one order)
- **batch** = a small group of rows processed together
- **operator** = a “station” in the pipeline (filter, compute a new column, group/sum, etc.)

### Diagram: the pipeline

![](filter-representation-assets/vectorized_pipeline.png)

---

## 3) Tiny example with numbers (8 rows)

We have 8 orders with an `amount` value:

Positions: `0 1 2 3 4 5 6 7`

`amount`:   `20 150 5 130 200 10 90 180`

We apply a simple rule:

> Keep only orders where amount > 100

So the “good” positions are: **1, 3, 4, 7**

### Diagram: what changes after the filter

![](filter-representation-assets/batch_example_step.png)

---

## 4) Two ways to write the “keep/ignore note”

Both ways mean the SAME thing (“keep 1,3,4,7”), they are just written differently.

### A) Selection Vector (SV) = a list of good positions

Example:
- `SV = [1, 3, 4, 7]`

How to read it:
- “Only look at rows number 1, then 3, then 4, then 7.”

Real-life analogy:
- A list of seat numbers of people who passed security.

### B) Bitmap (BM) = a row of 0/1 flags

Example:
- `BM = 0 1 0 1 1 0 0 1`

How to read it:
- “At each position: 1 means keep it, 0 means ignore it.”

Real-life analogy:
- Light switches: ON = keep, OFF = ignore.

---

## 5) Why do we care which one we use?

Because the next station might do more work.

Example: compute a new value

> new_amount = amount * 1.2

There are two styles:

### Style 1: Work only on the good rows
Using SV `[1,3,4,7]`, you compute only 4 multiplications.

This is great when:
- very few rows survived

### Style 2: Work on every row, then ignore the bad ones
You compute 8 multiplications, then you only keep results where BM=1.

This can be great when:
- most rows survived
- the work is simple math
- the computer can do simple math very fast in a tight loop

---

## 6) The paper’s main message (in beginner language)

The paper compares SV vs BM and basically says:

- Sometimes it’s faster to use a **list of good positions** (SV).
- Sometimes it’s faster to use **0/1 flags** (BM).

Which one is faster depends on:

- **How many rows survive**
  - if only a few survive → SV is often good
  - if most survive → BM can be good

- **What kind of work you do next**
  - simple number work (add/multiply/compare) often works nicely with BM
  - complicated work (like strings / lots of “if” logic) often benefits from SV

### Beginner cheat-sheet

| If… | Usually choose… | Why |
|---|---|---|
| Only a few rows survive | SV | You touch only the survivors |
| Most rows survive and work is simple math | BM | Scanning everything can be very efficient |
| Work is complicated/irregular | SV | Less overhead than dealing with many flags |

---

## 7) Super simple glossary (no IT assumption)

- **Row**: one item/record (example: one order).
- **Batch**: a small group of rows processed together.
- **Pipeline**: multiple stations in a row (scan → filter → compute → sum).
- **Filter**: a rule that keeps some rows and rejects others.
- **Filter representation**: the “note” that says which rows are still valid.
- **Selection Vector (SV)**: a list of the positions that are valid.
- **Bitmap (BM)**: 0/1 flags for each position (1 = valid, 0 = invalid).
- **Position / index**: the row number inside the batch (0,1,2,3…).

---

## 8) 15-second recap

- Databases often process data in small groups.
- After a filter, some rows are rejected.
- Instead of copying data, the DB keeps the data and carries a small “keep/ignore” note.
- That note can be written as a **list (SV)** or **0/1 flags (BM)**.
