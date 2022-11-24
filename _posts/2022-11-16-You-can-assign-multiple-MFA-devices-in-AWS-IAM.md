---
layout:     blogpost
title:      "You can now assign multiple MFA devices in AWS IAM"
date:       2022-11-16 12:00:00
author:     "Khaled Zaky"
categories: cloud aws tech
---

>I am super excited to finally announce this feature launch. Now, you can add multiple MFA devices to Amazon Web Services (AWS) account root users and IAM users in your AWS accounts. Check out our [AWS Security Blog post](https://aws.amazon.com/blogs/security/you-can-now-assign-multiple-mfa-devices-in-iam/) to learn more about this new feature

TL;DR as published on the [AWS What's New post](https://aws.amazon.com/about-aws/whats-new/2022/11/aws-identity-access-management-multi-factor-authentication-devices/#:~:text=AWS%20Identity%20and%20Access%20Management%20(IAM)%20now%20supports%20multiple%20multi,one%20authentication%20device%20per%20user.), [AWS Identity and Access Management (IAM)](https://aws.amazon.com/iam/) now supports multiple multi-factor authentication (MFA) devices for root account users and IAM users in your AWS accounts. This provides additional flexibility and resiliency in your security strategy by enabling more than one authentication device per user. You can choose from one or more types of hardware and virtual devices supported by IAM.

MFA is one of IAM’s leading [security best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html) to provide an additional layer of security to your account, and we recommend that you enable MFA for all accounts and users in your environments. Now it is possible to add up to eight MFA devices per user, including FIDO security keys, software time-based one-time password (TOTP) with virtual authenticator applications, or hardware TOTP tokens. Configuring more than one device provides flexibility if a device is lost or broken, or when managing access for geographically diverse teams. 