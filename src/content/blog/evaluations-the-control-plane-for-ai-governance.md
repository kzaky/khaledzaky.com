---
title: "Evaluations: The control plane for AI governance"
date: 2026-03-21
author: "Khaled Zaky"
categories: ["tech"]
description: "Observability tells you what your agents did. Evaluations tell you whether what they did was acceptable, and whether it will remain acceptable tomorrow. That distinction matters for building institutional trust."

---

**TL;DR:** Observability tells you what your agents did. Evaluations tell you whether what they did was acceptable, and whether it will remain acceptable tomorrow. For those of us building agentic platforms in regulated environments, that distinction matters a lot — it's the difference between a system that earns institutional trust and one that doesn't.

---

## You cannot evaluate what you cannot observe

The dependency is pretty direct: you can't really evaluate what you haven't instrumented. Observability has become table stakes for teams running agents in production. Evaluation is still the gap most teams haven't closed.

From what I see working on agentic platforms, the teams that struggle most with governance aren't the ones without dashboards. They're the ones that conflate "we can see what the agent did" with "we know whether what it did was acceptable."

The way I think about it, the relationship between the two layers is structural, not just sequential. Observability captures the raw material: traces, tool invocations, decision trajectories, token usage, latency. Evaluation systems consume that material and render a judgment.

[OpenTelemetry's GenAI semantic conventions](https://opentelemetry.io/blog/2024/otel-generative-ai/) (currently experimental, targeting a stable release) define standardized attributes that attach evaluation results directly to production traces. This creates a vendor-agnostic data layer where you instrument once and evaluate everywhere. Frameworks like Pydantic AI, smolagents, and Strands Agents emit OpenTelemetry-native traces, and platforms like [Langfuse](https://langfuse.com/blog/2024-07-ai-agent-observability-with-langfuse) natively ingest them.

The practical implication: production traces become evaluation datasets. When an agent fails in production, that failure's trace becomes a test case. When an LLM-as-judge scores a production interaction, that score attaches to the trace span.

The observability layer feeds the evaluation layer, which feeds governance reporting, which feeds audit evidence. [Microsoft's Azure AI Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/generally-available-evaluations-monitoring-and-tracing-in-microsoft-foundry/4502760) exemplifies this pattern by integrating evaluation results, traces, latency, and quality metrics into Azure Monitor, enabling cross-stack correlation: when your groundedness score drops, is it a model update, a retrieval pipeline issue, or an infrastructure problem?

If you haven't read my earlier post on [agent observability](https://khaledzaky.com/blog/agent-observability-the-missing-layer-in-agentic-ai-platforms/), that's the prerequisite for this one. This post picks up where observability ends.

![Observability-to-Evaluation Pipeline](/postimages/charts/evaluations-the-control-plane-for-ai-governance-diagram-1.svg)

---

## Build-time and runtime evaluations serve fundamentally different purposes

**Build-time** (pre-deployment) evaluations establish baselines, catch regressions, and validate safety before real users encounter the system. They test adversarial prompts, jailbreak resistance, bias and fairness, tool invocation correctness, scenario completion, and policy adherence.

[DeepEval](https://deepeval.com/guides/guides-ai-agent-evaluation) provides dedicated metrics like `ToolCorrectnessMetric` and `ArgumentCorrectnessMetric` specifically for agentic systems.

Anthropic publishes some of the most detailed build-time evaluation methodology available. Their [engineering post on demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) defines core terminology (task, trial, grader, transcript, outcome) and recommends three grader types: code-based (fast, deterministic, for objective checks), model-based (flexible, for subjective quality), and human (gold standard, expensive). They recommend starting with 20 to 50 tasks drawn from real production failures, not synthetic test cases.

**Runtime** evaluations address what build-time cannot. Foundation model updates ship continuously, shifting output style and reasoning patterns. User inputs in production are more diverse and adversarial than any test suite. Data drift and concept drift erode model alignment over time.

The [Ada Lovelace Institute](https://www.adalovelaceinstitute.org/blog/post-deployment-monitoring-of-ai/) makes the systemic argument clearly: pre-deployment evaluations of capabilities cannot assess the potential for society-level harms, and ongoing testing and monitoring is necessary as a structural requirement, not a nice-to-have.

Runtime evaluation in practice means continuous monitoring of quality metrics at sampled rates, scheduled evaluation against benchmark datasets to detect drift, escalation rate tracking, guardrail activation logging, and periodic red teaming. [Microsoft's Azure AI Foundry documentation](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/generally-available-evaluations-monitoring-and-tracing-in-microsoft-foundry/4502760) covers this pattern in detail, noting that production agent behavior is a function of many things that change independently of your code.

The feedback loop between build-time and runtime is where the real value compounds. Production failures become test cases. Human feedback calibrates LLM judges. Traces from novel edge cases expand scenario coverage.

This isn't a one-way pipeline. It's a continuous cycle that makes both layers stronger over time.

![Build-Time vs. Runtime Evaluation](/postimages/charts/evaluations-the-control-plane-for-ai-governance-diagram-2.svg)

---

## Model evaluations and agent evaluations are different things

This is something I keep running into. Benchmarks designed for single-turn text generation — the kind that score factual recall or language fluency — don't capture how agents fail in practice.

Agents plan, call tools, maintain state, and adapt across multiple turns. Evaluating them with model-level benchmarks is like evaluating a distributed system by unit-testing one microservice in isolation.

**Model-level evaluations** test raw capabilities: accuracy on benchmarks like MMLU (a broad academic test covering science, law, medicine, and dozens of other subjects — essentially "how much does the model know"), hallucination rates on factual queries, safety testing against toxic content generation. These are necessary but insufficient.

**Agent-level evaluations** test the entire system operating in context: task completion end-to-end, tool selection and argument correctness, multi-step reasoning coherence, delegation behavior in multi-agent systems, error recovery, and policy compliance across extended interactions.

The [2025 AI Agent Index](https://arxiv.org/html/2602.17753), which analyzed 30 deployed agent systems, found that only 4 had agent-specific system cards, and 25 of 30 agents disclosed no internal safety results for the agentic setup, only for base model components. That gap between model-level disclosure and agent-level disclosure is exactly the kind of thing that creates audit exposure in a regulated environment.

![Model vs. Agent Evaluation](/postimages/charts/evaluations-the-control-plane-for-ai-governance-diagram-3.svg)

[DeepEval's framework](https://deepeval.com/guides/guides-ai-agent-evaluation) makes the layered architecture explicit, distinguishing end-to-end metrics (`PlanQualityMetric`, `TaskCompletionMetric`, `StepEfficiencyMetric`) from component-level metrics (`ToolCorrectnessMetric`, `ArgumentCorrectnessMetric`, `ToolSelectionMetric`).

You need both layers. The end-to-end metrics tell you whether the agent is working. The component-level metrics tell you why it isn't.

---

## The compounding error problem makes agent evaluation non-optional

There's a compounding math problem here that I find genuinely uncomfortable to sit with. Agent success roughly follows P(success) = (per-step accuracy)^n — a pattern sometimes called Lusser's Law.

At 95% per-step accuracy (which sounds excellent), a 10-step workflow succeeds roughly 60% of the time. A 20-step workflow drops to around 36%. At 90% per-step accuracy over 10 steps, end-to-end success falls to around 35%.

A [Towards Data Science analysis](https://towardsdatascience.com/the-math-thats-killing-your-ai-agent/) examining AI agent performance found that success rates decline exponentially with task duration, and that Claude 3.7 Sonnet showed meaningful performance degradation on longer-horizon tasks. The SWE-bench gap illustrates the same dynamic: top agents achieve strong results on the verified subset, but performance on more realistic commercial task complexity is substantially lower.

[DeepMind's Demis Hassabis has warned publicly](https://www.computerweekly.com/news/366620886/Deepmind-founder-warns-of-compounding-ai-agent-errors): "If your AI model has a 1% error rate and you plan over 5,000 steps, that 1% compounds like compound interest."

In a regulated environment, these don't feel like engineering curiosities to me — they feel like actual risk numbers. A 20-step loan processing agent at 95% per-step accuracy fails on a substantial fraction of cases. That's not a model quality problem. That's a system design and evaluation problem.

This is why agent-level evaluation (testing the complete trajectory rather than individual model calls) is essential. I covered the broader governance implications of this in [Governing Autonomous Agents is a Platform Problem](https://khaledzaky.com/blog/governing-autonomous-agents-is-a-platform-problem/), but the evaluation layer is where that governance becomes operational.

---

## Trajectory evaluation is replacing output-only evaluation

Evaluating only the final output misses critical failure modes. The [TRACE framework](https://arxiv.org/html/2602.21230v1) identifies what it calls a "high-score illusion": metrics like Pass@1 reward correct final answers regardless of reasoning process.

An agent can achieve a high score through inefficient, circuitous, or even unsound trajectories that rely on hallucinated evidence. The answer is right. The path was wrong. In a regulated context, the path matters.

Production tools have adopted trajectory evaluation as a first-class concern. [LangChain's AgentEvals](https://docs.langchain.com/langsmith/trajectory-evals) provides trajectory matching evaluators with both strict mode (identical messages, same order, same tool calls) and LLM-judge mode (qualitative validation against a rubric).

[Arize Phoenix](https://arize.com/docs/ax/evaluate/evaluators/trace-and-session-evals/trace-level-evaluations/agent-trajectory-evaluations) measures the entire sequence of tool calls an agent takes to solve a task. [IBM's Agent Trajectory Explorer](https://research.ibm.com/publications/agent-trajectory-explorer-visualizing-and-providing-feedback-on-agent-trajectories), presented at AAAI 2025, provides visualization and annotation tooling for agent behavior analysis.

[Anthropic's guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) adds a useful nuance here: grade what the agent produced, not the path it took, because agents find valid approaches that designers didn't anticipate.

The resolution is to evaluate outcomes (final environment state) while using trajectory analysis for debugging and improvement, not as the primary success criterion. Trajectory analysis is a diagnostic tool. Outcome evaluation is the governance gate.

---

## What the major model providers are publishing

I spent a chunk of this past weekend reading through what the major labs are actually publishing on evaluation. The short version: they've all moved beyond model-level benchmarks into agent-specific evaluation, though at different paces and with different angles.

[Anthropic's](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) engineering post on demystifying evals for AI agents is the most useful practitioner guide I found.

Their open-source [Bloom framework](https://www.anthropic.com/research/bloom) automates behavioral evaluation generation through a four-stage pipeline, and their [Petri tool](https://www.anthropic.com/research/petri-open-source-auditing) simulates realistic environments for multi-turn safety testing.

The [Anthropic-OpenAI joint alignment evaluation](https://alignment.anthropic.com/2025/openai-findings/) published in summer 2025 marked a significant moment: two frontier labs systematically evaluated each other's models using internal alignment evals and published results in parallel.

Anthropic found that OpenAI's o3 and o4-mini reasoning models were aligned as well as or better than their own models, while GPT-4o and GPT-4.1 showed more concerning behaviors when guardrails were loosened. Notably, [all models from both developers would at least sometimes attempt to blackmail their simulated human operator](https://www.ibtimes.co.uk/anthropic-openai-ai-safety-evaluation-1787117). That's worth sitting with for a moment.

[OpenAI](https://platform.openai.com/docs/guides/evals) provides the broadest evaluation tooling ecosystem, with their Evals API and trace grading functionality explicitly targeting three evaluation levels: model-level, workflow-level, and agent-level. Their ["Practices for Governing Agentic AI Systems" white paper](https://openai.com/index/practices-for-governing-agentic-ai-systems/) defines seven governance practices including automatic monitoring, interruptibility, and agent identification.

[Google DeepMind](https://arxiv.org/html/2512.08296v1) focuses on benchmark creation and scaling science. Their paper "Towards a Science of Scaling Agent Systems" evaluates configurations across multiple benchmarks using canonical architectures. Their cognitive taxonomy work proposes measuring AI against key cognitive abilities through a structured evaluation protocol.

[Meta](https://github.com/meta-llama/PurpleLlama/blob/main/CybersecurityBenchmarks/README.md) leads in open-source safety evaluation through the Purple Llama project. CyberSecEval, now in version 4 (developed with CrowdStrike), includes AutoPatchBench and CyberSOCEval for evaluating agent security capabilities.

The [Llama Guard family](https://build.nvidia.com/meta/llama-guard-4-12b/modelcard) (version 4, a 12B multimodal safety classifier) performs both input and output filtering aligned with MLCommons' hazard taxonomy. [LlamaFirewall](https://www.infosecurity-magazine.com/news/meta-new-advances-ai-security/) orchestrates multiple guard models to detect prompt injection, insecure code, and risky agent interactions in real time.

---

## The evaluation tooling landscape is consolidating

The open-source evaluation ecosystem has moved fast. Two acquisitions stood out to me as signals of how seriously the space is being taken: [Langfuse was acquired by ClickHouse](https://clickhouse.com/blog/langfuse-and-clickhouse-a-new-data-stack-for-modern-llm-applications) in 2025, and [Promptfoo was acquired by OpenAI](https://github.com/promptfoo/promptfoo) in early 2026. Both remain open source.

The [UK AI Safety Institute's Inspect framework](https://www.gov.uk/government/news/ai-safety-institute-releases-new-ai-safety-evaluations-platform), open-sourced in May 2024, deserves particular attention. It's the first state-backed AI safety testing platform released for public use.

Its architecture (`Dataset` → `Task` → `Solver` → `Scorer`) is composable and extensible, and the fact that a government body shipped this as open infrastructure is itself a signal about where evaluation sits in the broader governance conversation.

The pattern I keep seeing while working in this space is that evaluation is becoming infrastructure, not a step in a release process. The teams that treat it as a gate before deployment are already behind.

The teams building evaluation as a continuous layer, running in production alongside the agent, are the ones that'll be able to demonstrate compliance in real time rather than reconstructing it after the fact.
