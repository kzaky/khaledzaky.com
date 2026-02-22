---
title: "Challenges with MFA Adoption"
date: 2023-01-18
author: "Khaled Zaky"
categories: ["identity", "security", "mfa"]
description: "MFA is one of the most effective security controls available, but adoption remains painfully slow. Here are the four challenges I see most often, and what to do about them."
---

**TL;DR:** MFA is one of the strongest security controls you can deploy. But rolling it out across an organization is harder than it should be. The friction is real, the technical gaps are real, and the security model itself is not bulletproof. Here is what I have seen and what I think teams should focus on.

## The adoption gap

Having worked on identity systems at AWS and as a member of the FIDO Alliance and W3C WebAuthn Working Group, I have seen the MFA adoption challenge from multiple angles: the product side, the standards side, and the enterprise deployment side.

The pattern is consistent. Organizations know MFA matters. Leadership signs off on it. Then rollout stalls.

The hard part is not the technology. It is everything around it.

## User resistance is the biggest blocker

Most users see MFA as friction, not protection. They do not understand why a password is not enough, and they do not want to change their workflow.

This is a product problem, not a security problem. If you are forcing users through a clunky enrollment flow with no context on why it matters, expect pushback.

What works:
- **Make enrollment frictionless.** Passkeys and platform authenticators (Face ID, Windows Hello) eliminate the "carry a hardware token" objection entirely.
- **Explain the why, not just the what.** A 30-second explainer during onboarding goes further than a policy document nobody reads.
- **Start with high-risk populations.** Admins, finance, and executives first. Then expand.

If you are at startup scale, a simple "enable MFA" nudge in your onboarding flow is enough. If you are in the enterprise, you need a phased rollout plan with clear communication at each stage.

## Technical complexity is real but solvable

MFA is not just "add a TOTP code." At scale, you are dealing with:

- Token lifecycle management (provisioning, rotation, revocation)
- Integration with legacy systems that were never designed for strong auth
- Recovery flows for lost devices (this is where most deployments break)
- Logging and auditability for compliance

The trade-off here is between speed and coverage. You can get 80% of your users on MFA quickly with software tokens. Getting to 100% with phishing-resistant methods like FIDO2 takes longer but closes the real gaps.

Budget for the recovery flow. That is where user frustration peaks and where support tickets pile up.

## Interoperability across systems

This one is underrated. Most organizations run a mix of SaaS apps, internal tools, and legacy systems. Not all of them support the same MFA methods.

You end up with users juggling multiple authenticators, or worse, some systems with MFA and others without. Attackers will find the weakest link.

The practical fix:
- **Consolidate on an IdP** (Okta, Azure AD, AWS IAM Identity Center) that supports federation across your stack
- **Standardize on FIDO2/WebAuthn** where possible, it is the only phishing-resistant option with broad platform support
- **Audit your coverage.** Map every application to its MFA status. The gaps will surprise you.

## MFA is not a silver bullet

This is the part that gets overlooked. MFA significantly raises the bar, but it does not eliminate risk.

Real-time phishing proxies (tools like Evilginx) can intercept MFA tokens mid-session. SIM swapping defeats SMS-based MFA entirely. Push notification fatigue attacks exploit users who just tap "approve" to make the prompt go away.

The honest answer: TOTP and SMS-based MFA are better than passwords alone, but they are not phishing-resistant. If you are serious about closing the gap, FIDO2 security keys or passkeys are the standard to aim for.

## Next Steps

If you are evaluating or expanding MFA in your organization:

1. **Audit your current state.** Which systems have MFA? Which do not? Where are the gaps?
2. **Pick a phishing-resistant baseline.** FIDO2/WebAuthn should be the target, not TOTP.
3. **Design the recovery flow first.** Lost device recovery is where most rollouts fail.
4. **Measure adoption, not just enrollment.** Users who enrolled but disabled MFA are not protected.
5. **Treat it as a product launch, not a policy mandate.** Communication, UX, and phased rollout matter.

MFA adoption is not a technology problem. It is a product and change management problem that happens to involve technology.
