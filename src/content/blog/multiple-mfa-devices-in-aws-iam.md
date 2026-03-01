---
title: "You Can Now Assign Multiple MFA Devices in AWS IAM"
date: 2022-11-16
author: "Khaled Zaky"
categories: ["cloud", "identity", "security"]
description: "AWS IAM now supports up to 8 MFA devices per user. Here is why this matters and what you should do about it."
---

This is a feature I have been looking forward to for a long time. As of today, [AWS Identity and Access Management (IAM)](https://aws.amazon.com/iam/) supports multiple multi-factor authentication (MFA) devices for both root account users and IAM users.

The full details are in the [AWS Security Blog post](https://aws.amazon.com/blogs/security/you-can-now-assign-multiple-mfa-devices-in-iam/) and the [AWS What's New announcement](https://aws.amazon.com/about-aws/whats-new/2022/11/aws-identity-access-management-multi-factor-authentication-devices/).

## What changed

You can now add **up to 8 MFA devices per user**. The supported types include:

- **FIDO security keys** (YubiKey, Titan, etc.)
- **Software TOTP** via virtual authenticator apps (Google Authenticator, Authy)
- **Hardware TOTP tokens**

You can mix and match device types per user.

## Why this matters

MFA is one of IAM's leading [security best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html). But until now, the single-device limitation created a real operational problem: if that one device was lost or broken, recovery was painful.

Multiple devices solve this in a few ways:

- **Resilience.** A backup device means a lost YubiKey does not lock you out of your account.
- **Flexibility.** Geographically diverse teams can use different devices in different locations.
- **Phishing resistance.** You can register a FIDO security key as your primary and keep a TOTP app as a backup, getting the best of both worlds.

## Next Steps

If you manage AWS accounts, I would recommend:

1. **Enable MFA on every root account and IAM user.** This should already be done, but audit it.
2. **Register at least two devices per user.** One primary, one backup.
3. **Prefer FIDO security keys where possible.** They are the only phishing-resistant option IAM supports.

Check out the [AWS Security Blog post](https://aws.amazon.com/blogs/security/you-can-now-assign-multiple-mfa-devices-in-iam/) for the full walkthrough on how to configure multiple devices.
