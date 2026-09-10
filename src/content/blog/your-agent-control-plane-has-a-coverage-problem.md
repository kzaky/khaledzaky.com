---
title: "Your Agent Control Plane Has a Coverage Problem"
date: 2026-09-10
author: "Khaled Zaky"
categories: ["ai", "security", "identity", "platform-engineering"]
description: "A control plane can govern the paths it sees. That does not prove it covers every path through which an agent can act, delegate work, or leave an effect behind."

---

Five months ago, I argued that regulated enterprises needed an [agent control plane](https://khaledzaky.com/blog/from-guardrails-to-operating-model-the-agent-control-plane/).

Now AWS, Google, and Microsoft are building one. That should feel like the argument has been settled.

It hasn't.

A control plane governs the execution paths it fronts. An agent can still hold a credential the platform didn't issue, call a tool it doesn't mediate, delegate work it can't trace, or leave an effect it can't reverse. The presence of a control plane doesn't prove the coverage of the control.

That distinction became harder to ignore this week. Researchers connected OpenAI agents involved in the Hugging Face incident to at least ten additional sites used for unauthorized communications, according to [Reuters](https://www.reuters.com/world/openais-rogue-agents-used-least-10-more-sites-unauthorized-comms-researchers-say-2026-09-09/). OpenAI said some of the activity had already been identified internally. The important systems lesson isn't whether someone eventually stopped the known run. It's that the action surface continued expanding as investigators found more places the agents had reached.

In [The Halt You Never Tested](https://khaledzaky.com/blog/the-halt-you-never-tested/), I argued that stopping an agent is a distributed-systems problem across execution, credentials, tools, downstream work, and effects.

The question underneath that post is even more uncomfortable:

> How do you know you found every place where the agent still has power?

That isn't a shutdown problem. It's a **coverage problem**.

## Three claims that keep getting collapsed

An enterprise agent platform needs to make three different claims:

| Property | Question | What establishes it |
| --- | --- | --- |
| **Coverage** | Can we enumerate the paths through which the agent can act? | Discovery, identity, registry, runtime topology, and work lineage |
| **Binding** | Can a governance decision be enforced on each path? | Gateways, authorization, network controls, runtime hooks, and consumer enforcement |
| **Closure** | Can we demonstrate that the requested state took effect? | Cross-surface reconciliation, acknowledgements, observed state, and unresolved-path reporting |

These properties depend on one another, but they aren't interchangeable.

![Coverage → Binding → Closure Dependency Chain](/postimages/charts/your-agent-control-plane-has-a-coverage-problem-diagram-1.svg)

A registry can provide visibility without binding. A gateway can enforce policy without covering a direct credential or an unobserved endpoint. A runtime can accept a cancellation request without proving that a child agent stopped or that queued work won't commit later.

The complete **control surface** is therefore not the list of assets in the control-plane dashboard. It's the graph of ways an agent can acquire authority, invoke a capability, delegate work, and produce an effect.

If one edge in that graph is invisible or unenforceable, the platform can still contain the paths it controls. It can't honestly report universal closure.

## Visibility is not coverage

The registry matters, but the strongest entries should come from infrastructure rather than a form.

An identity system knows which machine identities and grants exist. A gateway knows which tools were presented and invoked. A runtime knows which executions and child tasks it started. A broker knows which messages it accepted. Network telemetry can identify destinations reached outside the expected path.

Those records should populate and challenge the declared architecture automatically.

Teams still need to declare purpose, ownership, intended users, business effects, and recovery responsibility. But a declaration is a hypothesis about the deployed system. The platform has to compare it with observed reality.

An imported agent isn't automatically ungovernable. It can be discovered, registered, and brought behind enforceable boundaries. Until its declared permissions and paths are verified, however, it should remain visibly unverified. Registration is the beginning of binding, not evidence that binding is complete.

This changes the registry from an inventory into a **coverage map**. It should show more than what exists:

- Which execution, identity, tool, network, and downstream paths are bound to policy.
- Which paths are observed but not yet controlled.
- Which declarations haven't been verified.
- Which dependencies were unreachable during the last reconciliation.
- Which business effects can't be reversed.

That last category matters. Coverage includes knowing where technical intervention ends.

![Coverage Map](/postimages/charts/your-agent-control-plane-has-a-coverage-problem-diagram-2.svg)

## A control plane is not one enforcement point

The name can mislead us into picturing a central service through which every decision travels. In a heterogeneous enterprise, enforcement will remain distributed.

The platform can manage four of the seven halt layers centrally. Two require federated contracts with runtimes and downstream systems. One remains application-owned because only the business knows what recovery means.

| Halt layer | Primary ownership | Coverage requirement |
| --- | --- | --- |
| Stop admission | Central | Every supported entry point and delegation path rejects new work in the halted scope |
| Suspend execution | Federated | Each runtime implements and proves a common intervention contract |
| Cut tool and network access | Central | Governed paths include tool gateways and constrained egress |
| Revoke authority | Central | Credentials and delegated grants are revoked or denied at their enforcement points |
| Contain downstream work | Federated | Queues and workers carry trustworthy lineage and enforce cancellation, expiry, or fencing |
| Recover effects | Application | Every consequential effect declares rollback, compensation, remediation, or accepted irreversibility |
| Prove the halt | Central | A reconciler reports closed, failed, and unknown paths separately |

![Halt Layer Ownership](/postimages/charts/your-agent-control-plane-has-a-coverage-problem-diagram-3.svg)

Federation isn't an excuse for weaker evidence. The central platform defines the contract, and each supported runtime or messaging system implements an adapter and passes conformance tests.

One orchestrator or broker would simplify the topology. It's not a realistic assumption for most large enterprises. Standardizing the intervention contract is more durable than pretending the estate will converge on one engine.

Correlation is also not control. An execution ID can help locate a queued job, but a consumer still has to check whether that execution is authorized to continue before committing an effect.

## Binding requires a production boundary

The control plane doesn't have to mint every credential. It can mediate an existing identity provider, front an external tool, or isolate a runtime through network controls.

What it can't do is prove control over a path that production can freely route around.

Consider an agent that normally calls an approved tool through a gateway but also carries a long-lived API key in its configuration. The gateway denies the next request. The second path remains available. Both statements are true: the gateway worked, and the halt is incomplete.

This is why an SDK is useful but insufficient. The SDK can give builders identity, tool discovery, tracing, retries, and intervention hooks. Enforcement also has to exist outside application code, at boundaries the agent can't disable.

Normal production authority should be reachable through governed identity, network, and tool paths. Exceptions need a named owner, limited scope, expiration, and an evidence standard. Break-glass access should be more attributable, not less.

The design principle is straightforward:

> A policy is bound only when the relevant production path cannot ignore it.

This is also where the **paved road** becomes a control. It isn't the documentation. It's the combination of useful platform primitives and production boundaries that make the governed implementation the cheapest working option.

## Closure is not an accepted command

Most operational systems are very good at confirming that a request was accepted.

The runtime returned `200`. The identity service accepted the revocation. The queue acknowledged the cancellation. The incident workflow moved to contained.

Those are commands and acknowledgements. **Closure** is the reconciled state afterward.

A closure service should compare the intended containment state with observations from runtimes, gateways, identity systems, brokers, and downstream consumers. It should preserve:

- When the intervention began.
- When each enforcement point acknowledged it.
- When the new state was independently observed.
- Which work was already in flight.
- Which effects committed before and after intervention.
- Which paths failed or couldn't be checked.
- How fresh the evidence was when the conclusion was reached.

An empty search for new traces isn't proof that no work continued. Telemetry can arrive late. A dependency can be unreachable. A child may be executing in another trust domain.

The result therefore can't always be a green check. It may be complete, failed, or incomplete because some surface is unknown. A credible control plane has to be willing to say the last one.

**Resume** creates another closure problem. Work issued before the halt shouldn't restart merely because the agent becomes active again. A versioned **authorization epoch**, **fencing token**, or equivalent consumer-enforced mechanism can distinguish stale work from newly authorized work.

This is the same class of problem as fencing tokens in distributed leader election: when a leader loses its lease and a new one is elected, the old leader's in-flight writes must be rejected by participants who've seen the new term. Resume is a new decision, not the reversal of a Boolean flag.

## The checkpoint sets the halt latency

Some platforms and authorization products describe revocation becoming effective on the next request or tool call. That's useful. It's not instantaneous interruption.

A call may stream for minutes, launch asynchronous work, or commit an irreversible action before returning. Some operations expose cancellation. Others don't.

The real bound is:

> Halt latency is determined by the longest uninterruptible interval between enforceable checkpoints.

An enterprise needs to know where those checkpoints are. They might occur before admission, credential vending, each tool invocation, queue consumption, and effect commitment. Higher-impact operations need tighter checkpoints and stronger confirmation.

The platform shouldn't describe all of them as one kill switch. It should expose the different semantics: stop accepting work, request cancellation, revoke future authority, fence stale work, prevent commitment, initiate compensation.

Each verb makes a different claim.

## Recovery remains a domain contract

A central platform can't invent the business reversal for every action.

Reversing a payment creates another financial event. Correcting a customer record may require approval and an audit trail. Deleting an email from the sender's mailbox doesn't reverse a disclosure.

The platform can centralize the obligation. Before an agent receives production authority for a consequential action, the application team should declare an **effect contract**:

- What external effect can be committed?
- Is it reversible?
- Is the response rollback, compensation, or remediation?
- How long does the recovery option remain available?
- Who owns manual recovery?
- What evidence demonstrates completion?

Some effects will be explicitly irreversible. They require an authorized acceptance of that exposure and appropriate controls before commitment.

Registering a function named `compensate()` isn't sufficient. The mechanism has to be exercised. Its failure modes, deadline, and actual business result need to be understood.

The platform can invoke the compensator, track progress, and preserve evidence. The application owner determines whether the business outcome was repaired.

## Keep deterministic controls deterministic

Agent behaviour is probabilistic. That doesn't make every agent control probabilistic.

These questions can still have deterministic answers:

- Was an unregistered tool called?
- Did traffic bypass the gateway?
- Did a credential expire?
- Did an action exceed a transaction limit?
- Did observed tool use diverge from the approved manifest?
- Did a worker commit after its authorization epoch was fenced?

Semantic questions are different. Did the proposed action remain aligned with the user's intent? Did the agent materially expand the task? Was the evidence sufficient for a consequential conclusion?

[Google's semantic-governance documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview) makes this distinction unusually explicit. Its preview feature evaluates proposed tool calls with an LLM, warns that verdicts may be inaccurate, and says IAM, rate limits, and network controls remain essential.

A semantic control may return `ALLOW` or `DENY` while the mechanism producing that verdict remains fallible. It needs evaluation data, measured false positives and false negatives, an escalation path, and defined behaviour when the evaluator is unavailable.

Use deterministic enforcement for boundaries that can be expressed deterministically. Use model-based judgement for the semantic gap that remains. Don't turn a known transaction limit into an LLM prompt.

## The market has components, not closure

The market moved quickly.

[AWS AgentCore Policy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html) applies deterministic policies to requests passing through its Gateway. AgentCore also exposes [`StopRuntimeSession`](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-stop-session.html) to terminate an active session and stop its streaming response.

Google describes a [governance surface](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern) spanning registry, identity, agent gateways, policy, security, and operational oversight. Microsoft describes [Foundry Control Plane](https://learn.microsoft.com/en-us/azure/foundry/control-plane/overview) as a unified interface for inventory, observability, compliance, and security across supported agent platforms. Both vendors identify preview capabilities in their documentation, so coverage and maturity still need to be evaluated feature by feature.

These are real capabilities. "Nobody sells agent governance" is no longer credible.

But a list of components isn't a proof of coverage. A model-traffic gateway and a tool-traffic gateway can govern different paths. Discovery and enforcement are different products. A runtime cancellation API describes one runtime's semantics, not the state of a heterogeneous workflow.

The differentiated enterprise capability is control closure across the components selected.

I'd test a vendor with an intervention exercise, not a feature checklist. Give an agent a delegated child, a short-lived credential, queued work, and a long-running external operation. Include an effect that commits before the call returns and a dependency that becomes unreachable during containment.

Trigger the halt, then ask:

1. Which new actions were blocked, and at what enforcement point?
2. Which running and queued actions actually stopped?
3. Where did authority remain usable?
4. Which effects had already committed?
5. Which paths could not be verified?
6. What prevents old work from resuming later?

The quality of the answer matters more than the number of agents displayed on the fleet dashboard.

## Governance should arrive with the useful primitive

Coverage and closure are platform concerns, but application builders shouldn't have to become distributed-systems experts to consume them.

The compliant path should also be the fastest path. The platform gives a builder scoped identity, approved tool access, egress, tracing, local conformance tests, and evidence capture. In return, production execution travels through surfaces the platform can govern.

The gate must behave like a failing test: immediate, specific, and actionable. If a builder adds a customer-communication tool without an effect contract, the pipeline should identify that exact missing obligation. A gate that takes a week is still a review board.

Controls should also be inherited transparently. A team needs to know which requirements the platform satisfies, the evidence supporting them, and which risks remain application-owned. Material changes to models, tools, permissions, or prompts should trigger the checks they affect.

This is where governance can become a side effect of infrastructure that already saved the team time. The paved road is valuable because it ships capabilities. It becomes a control because its production boundaries hold.

## What changes now

When I wrote about the agent control plane in April, the market was still converging on the shape. That convergence is now visible. The next question is no longer whether enterprises need a central governance surface.

It's whether that surface can substantiate its claims.

I'd measure an agent platform on:

- The percentage of production authority paths discovered.
- The percentage bound to an enforceable policy.
- The freshness and completeness of reconciliation evidence.
- The number and age of unverified declarations.
- Intervention latency at each checkpoint.
- Work or effects observed after the requested halt state.
- The time teams spend waiting for governance decisions.

Those metrics connect fleet scale to control quality and delivery speed. They also resist an easy failure mode: reporting perfect compliance over only the agents already inside the platform.

The next generation of agent-governance platforms won't be differentiated by how many agents they list or how many policies administrators can write. They'll be differentiated by whether they can measure control coverage, expose what remains outside it, and prove closure after intervention.

*A control plane is an architecture. Control coverage is a claim. Control closure is the evidence.*
