# Router Report Addendum — Tail Slayer Validates the Cross-Domain Transfer Claim

*Added to the main router report (April 2026) as a case study.*

## The claim we made, revisited

The router report's cross-domain synthesis argued that hedged requests transferred from classical networking into LLM inference, with this caveat:

> "Hedged / tied requests (Dean & Barroso, *The Tail at Scale*, CACM 2013) → fire duplicate to different replica after p95 elapses; at Google, BigTable tails went from 1800ms → 74ms p99.9 with ~2% extra load. Immediately applicable to LLM inference tails, but only for idempotent calls (reads, generation, retrieval — not state-mutating tool calls)."

That transfer claim was written at the millisecond scale. It is now confirmed across six orders of magnitude, down to the nanosecond scale, by independent work.

## The evidence

LaurieWired's **Tail Slayer** (published October 2025) implements hedged reads on DRAM refresh stalls. Same primitive, different substrate:

| Layer | Dean & Barroso 2013 | LaurieWired 2025 |
|---|---|---|
| Scale | ~1–1000 ms | ~80–400 ns |
| Stall mechanism | GC / scheduling / network tail | DDR4/DDR5 refresh cycle (TRFC) |
| Independence axis | Replica / machine / AZ | Memory channel |
| Implementation | Fire second RPC after p95 | Fire second read on second core |
| Winner selection | First response, cancel loser | First to commit in ROB, drop loser's cargo |
| Result (P99.9 / P99.99) | 1800ms → 74ms | 631ns → 281ns (consumer), 9–15× at server scale |
| Resource cost | ~2% extra load (tied requests) | Extra core + duplicated data |

The pattern holds. The numbers match the theory.

## What Tail Slayer teaches the LLM-routing side

Three findings that tighten the router report's recommendations:

### 1. The ROB-stall trap generalizes

LaurieWired's central empirical discovery: two independent reads on one core do *not* hedge because the reorder buffer retires in order. The faster read can't commit until the slower read does; the ROB fills; the core stalls; the hedging gain vanishes.

This is the head-of-line blocking phenomenon from classical networking, reappearing at CPU microarchitecture scale. It reappears in agent routing too. If an agent framework fires two parallel tool calls but accumulates results into a single-threaded reasoning loop that waits for "first response," hedging works. If it waits for "all responses" or serializes on a shared state store, the hedge gain vanishes and you paid for two calls for nothing.

**Router design implication:** the *merge point* matters as much as the *fork point*. A router that hedges well at dispatch but serializes at commit is worse than not hedging at all (you paid 2× for no benefit).

### 2. Synchronization overhead scales inversely with operation cost

LaurieWired explicitly documented this: she tried using a shared atomic to coordinate the two hedged reads, and the cache-line bouncing between cores cost more than the refresh stall she was dodging. At ns-scale, synchronization is a first-order concern.

At ms-scale HTTP hedging, this trap is rare — a mutex costs microseconds, the operation costs milliseconds. At LLM-inference scale (100ms–30s), synchronization overhead is almost free relative to the hedge.

**Router design implication:** hedging gets *easier* at larger operation scales. The router report's enthusiasm for hedging in LLM-inference routing is correct; the caveat about synchronization can be relaxed at that scale but must be preserved in any system that hedges within a single request.

### 3. Prediction fails whenever the scheduler can borrow against the future

LaurieWired's initial instinct was to *predict* refresh cycles and schedule around them. It failed because the memory controller uses opportunistic refresh scheduling — up to 8 refreshes can be postponed and caught up later. The rhythm is observable after the fact but not reliably predictable.

This is a general principle with wide applicability to LLM routing:

- Rate limiters with burst budgets borrow against future seconds → can't predict when you'll be throttled
- LLM provider queuing reorders based on priority tier → can't predict which call will tail
- Garbage collectors defer under memory pressure → can't predict when GC-induced tail hits

**Router design implication:** wherever a downstream system has "borrow against the future" semantics, prediction-based routing fails and *dodging* (hedging) is the only robust strategy. Add this to the decision framework: if your downstream population has deferrable work, don't try to schedule around it, race past it.

## Updated decision framework row

Add to the decision framework table in the main report:

| Dimension | Low (1) | High (5) | Architectural implication |
|---|---|---|---|
| Downstream scheduler has "borrow against future" semantics | No (pure FIFO, strict deadlines) | Yes (GC, burst-budget rate limit, opportunistic refresh, priority reordering) | High → hedging across independent failure domains, not prediction. **Dodge, don't schedule.** |

## Citation update

Add to the references section:

> LaurieWired, *Tail Slayer* (October 2025). Ports Dean & Barroso's hedged-request pattern to DRAM refresh stalls at nanosecond scale. Validates the cross-domain transfer claim at 10⁶× smaller scale than the original paper. Key contributions: (1) identification of the ROB head-of-line blocking trap at CPU microarchitecture scale, (2) the synchronization-overhead trap that scales inversely with operation cost, (3) reverse-engineering black-box channel XOR-hashing via tail-latency signal (self-bootstrapping reverse engineering). Available as a public video and GitHub repository.

## The generalized claim

The router report argued that five primitives generalize across all router types (hierarchical dispatch, policy-ordered selection, consistent-hash stickiness, outlier-ejected fallback, observable decisions). **Hedging for tail-latency reduction should be added as a sixth**, with the supporting evidence that it works from nanoseconds to milliseconds, provided the implementer navigates the three independence traps (correlated failure domains, synchronization overhead, head-of-line blocking at commit).

The practical test for any router design: can you name the *independence axis*, the *merge point*, and the *commit point*? If yes, hedging will help. If any one is vague, hedging will burn resources without moving tail latency.

---

## GIC architecture reference for Tail Slayer on ARM

This section covers the ARM Generic Interrupt Controller (GICv3+) considerations specific to implementing hedged reads at the hardware interrupt layer. Amended with corrections from review (April 2026).

### Named principle: Fan-Out Only

**Use the GIC as a fan-out primitive, never as a fan-in primitive.**

Fan-out (trigger both cores from one event) preserves independence. Fan-in (both cores converge to signal completion through any shared structure) destroys it. This is a sharper formulation of the trap list's "synchronization must actually not serialize" — operationally, it means:

- **Allowed:** GIC delivers separate IRQs to separate cores simultaneously (fan-out). Each core runs its handler, writes its result to a core-local buffer, and the winner is selected without cross-core synchronization.
- **Forbidden:** Both cores signal completion through a shared atomic, a shared completion queue, or any structure that causes cache-line bouncing. The GIC got you to both cores fast; a shared fan-in point destroys that advantage.

### Interrupt routing: targeted, not 1-of-N

GICv3 has two routing modes for SPIs:

| Mode | `Interrupt_Routing_Mode` | Behavior |
|---|---|---|
| Targeted | `0` | IRQ delivered to a specific CPU interface (affinity-pinned) |
| 1-of-N | `1` | GIC picks any one eligible core to deliver to |

**Tail Slayer requires `Interrupt_Routing_Mode=0` (targeted routing) on both hedge IRQs, each pinned to its own core.**

1-of-N (`Interrupt_Routing_Mode=1`) is the **wrong** choice because the GIC picks which core handles the IRQ — this eliminates the deterministic pinning that the entire architecture depends on. You lose control of which core runs which hedge path.

There is **no "N-to-N routing"** mode in GICv3 for a single interrupt. A single SPI or LPI is delivered to exactly one CPU interface. To deliver the same event to two cores simultaneously, you need **two distinct IRQs** (two MSI-X vectors, or the FPGA mechanism below), not one IRQ with a multi-target mode.

**Exception — SGIs for software triggers:** Software-Generated Interrupts (SGIs) *do* support broadcasting to a target list in a single instruction (`ICC_SGI1R_EL1` with `TargetList` bits). This is useful if core A needs to wake core B on a hedged read trigger, but it is not applicable to the NIC→cores delivery path.

### GIC priority uniformity across hedge IRQs

If hedge IRQ A has priority `0x80` and hedge IRQ B has priority `0xA0` (numerically higher = lower priority on ARM GIC), the GIC will preempt B in favor of A when both fire simultaneously on the same core. Across different cores this creates a subtler problem: any *other* higher-priority interrupt landing on core B — a timer tick, a device IRQ that slipped past `nohz_full`, an IPI — can delay B's handler while A runs unimpeded on core A.

The two hedges started symmetric and finished asymmetric. You've injected a timing-correlated failure at the interrupt layer.

**Rule: All hedge IRQs must have identical GIC priority, and no other interrupt on either hedge core should have equal or higher priority.**

This means:
- Set both hedge IRQs to the same priority value (e.g., `0x80`)
- Ensure `nohz_full` is active on both hedge cores to suppress timer ticks
- Migrate all other device IRQs off the hedge cores via `/proc/irq/*/smp_affinity`
- Audit IPI sources — performance monitoring interrupts, TLB shootdowns, and scheduler IPIs can all break symmetry

### FPGA-side interrupt duplication: the ideal delivery path

The lowest-latency, highest-independence delivery mechanism for hedged reads is FPGA-side interrupt duplication. The correct description of this path (applicable to NICs like the Exanic X25 or Solarflare X2522):

```
FPGA logic detects incoming packet/event
  → FPGA raises N distinct MSI-X vectors in parallel (hardware-level, pre-DMA)
    → PCIe MSI-X → ITS (Interrupt Translation Service) translates each vector to a distinct LPI
      → Each LPI routed to its pinned core's GIC Redistributor
        → Each core's handler fires independently
```

The hedged paths are independent **from the moment of electrical signal**, before Linux has a single instruction of say in the matter. This is not "program the NIC to replicate packets to multiple queues" (software-observable duplication at the DMA layer) — it's hardware-level fan-out at the interrupt signal itself.

Key distinction: at the DMA layer, the NIC copies packet data to multiple ring buffers. At the interrupt layer, the FPGA raises multiple MSI-X vectors. The interrupt path is faster because the GIC Redistributor can wake a sleeping core in ~20-50ns, while DMA completion + software poll adds microseconds of latency.

### Graviton caveat

It is not confirmed how strictly AWS Graviton 3/4 honors `Interrupt_Routing_Mode=0` with targeted affinity vs. AWS's firmware making its own routing decisions underneath. This would require either an AWS-internal document or empirical testing on a `c7g.metal` instance. Any claim that "targeted routing is preserved end-to-end on Graviton" should be treated as unverified until tested.
