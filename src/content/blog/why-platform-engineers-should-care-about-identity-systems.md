---
title: "Why Platform Engineers Should Care About Identity Systems"
date: 2025-11-20
author: "Khaled Zaky"
categories: ["cloud", "identity", "leadership"]
description: "Identity is not a security team problem. It is platform infrastructure. Here is why platform engineers need to own auth, and what happens when they do not."
---

**TL;DR:** Most platform teams treat identity as someone else's problem. That is a mistake. Identity is the control plane for everything: who can access what, how services talk to each other, and how you enforce policy at scale. If your platform team does not own identity, you will pay for it in developer friction, security gaps, and operational overhead.

## Identity is not a security problem. It is a platform problem.

I spent years working on identity systems at AWS, and I was a member of the FIDO Alliance and W3C WebAuthn Working Group. The pattern I saw over and over was the same: platform teams build great CI/CD pipelines, solid infrastructure abstractions, and clean developer tooling. Then they punt on identity.

Authentication gets bolted on. Authorization is ad hoc. Service-to-service auth is a mess of shared secrets and long-lived tokens. And nobody owns the full picture.

The result is predictable. Developers waste time fighting auth issues. Security teams scramble to patch gaps. And the platform team wonders why adoption is stalling.

## Why this is getting worse, not better

Three trends are compounding the problem.

**Microservices multiply auth decisions.** Every service-to-service call needs identity verification. A monolith has one auth boundary. A system with 50 microservices has hundreds. If you do not have a consistent identity layer, each team invents their own, and consistency disappears.

**Zero trust makes identity the perimeter.** The network is no longer the security boundary. Identity is. NIST SP 800-207 makes this explicit: zero trust architecture requires strong identity verification for every access request, regardless of network location. If your platform does not provide this, teams will work around it.

**Compliance is not optional.** GDPR, CCPA, SOC 2, PCI DSS. All of them have requirements around access control, auditability, and least privilege. Getting identity wrong is not just a technical problem. It is a business risk with real financial consequences.

## What I have seen work

At AWS, the teams that got identity right shared a few traits. They treated identity as a first-class platform capability, not a bolt-on. Here is what that looks like in practice.

### Own the identity primitives

Your platform team should own:

- **Authentication:** How users and services prove who they are
- **Authorization:** How you enforce what they can do
- **Token management:** Issuance, rotation, revocation, and lifecycle
- **Service identity:** mTLS, SPIFFE/SPIRE, or equivalent for service-to-service auth

If you are at startup scale, start with a managed IdP (Auth0, AWS Cognito, Okta) and standard OAuth 2.0 flows. If you are in the enterprise, you likely need a federated identity layer that spans multiple providers and legacy systems.

### Make the secure path the easy path

This is where most platform teams fail. They build the identity infrastructure but make it painful to use. Developers bypass it, and security erodes.

The fix is treating identity like a product:

- **Self-service token provisioning** instead of filing tickets
- **SDKs with auth baked in** so developers do not have to think about it
- **Clear golden paths** for common patterns (API auth, service-to-service, user-facing)
- **Fast feedback loops** when something is misconfigured

At AWS, we measured developer velocity around identity workflows. The teams that invested in developer experience saw measurably higher platform adoption. The ones that did not saw workarounds and shadow IT.

### Instrument everything

You cannot secure what you cannot see. Every auth decision should be logged, traceable, and auditable.

This means:

- Centralized auth logs with structured metadata
- Alerting on anomalous access patterns
- Dashboards showing auth success/failure rates by service
- Regular access reviews (automated where possible)

This is not just for security. It is how you find friction. If a service has a 15% auth failure rate, that is a developer experience problem worth investigating.

## The cost of getting it wrong

I have seen organizations lose months of productivity because identity was an afterthought. The symptoms are always the same:

- Developers spending hours debugging token expiration issues
- Shared service accounts with broad permissions because "it was easier"
- No audit trail for who accessed what and when
- Incident response slowed by inability to trace access paths
- Compliance findings that could have been prevented

Identity debt compounds faster than technical debt. Every shortcut you take now becomes a migration, a security incident, or a compliance finding later.

## Next Steps

If you are a platform engineer or leading a platform team:

1. **Map your identity surface.** List every authentication and authorization boundary in your system. The gaps will surprise you.
2. **Pick an owner.** Identity needs a clear owner on the platform team. If nobody owns it, everybody works around it.
3. **Measure developer friction.** Track how much time developers spend on auth-related issues. Use that data to prioritize.
4. **Start with service identity.** Service-to-service auth is usually the biggest gap and the highest risk. mTLS or SPIFFE/SPIRE are good starting points.
5. **Treat identity as a product.** Run NPS surveys on your auth tooling. If developers hate it, they will bypass it.

Identity is the foundation your entire platform sits on. The teams that treat it as infrastructure, not an afterthought, are the ones that scale.
