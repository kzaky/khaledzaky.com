---
title: "A Sunday Well Spent: Auditing and Hardening My Personal Cloud Infrastructure"
date: 2026-02-22
author: "Khaled Zaky"
categories: ["cloud", "security", "devops"]
description: "I spent a Sunday morning running a full security, ops, and FinOps audit on the AWS infrastructure behind my personal website. Here is everything I found, everything I fixed, and the best practices behind each decision."
---

I run this website on AWS: S3, CloudFront, Route 53, CodeBuild, ACM. It is a static Astro site. Simple stack, low traffic, costs about four dollars a month.

But simple does not mean secure. And low cost does not mean optimized.

I had not done a proper audit of this setup in a while. So I blocked off a Sunday morning, pulled up the AWS CLI, and went through every layer: security posture, operational hygiene, performance, and cost. What I found was a mix of "that is fine" and "how has this been like this for months."

This post is the full walkthrough: what I audited, what I found, what I fixed, and the reasoning behind each change. If you run any kind of static site on AWS, most of this applies directly.

## The Starting Point

The architecture is straightforward:

- **S3** bucket hosting the static files
- **CloudFront** distribution as the CDN
- **Route 53** for DNS
- **ACM** for the TLS certificate
- **CodeBuild** triggered by GitHub webhook on push — runs `npm run build`, syncs to S3, invalidates the CloudFront cache

Total monthly cost: **$4.56**. Most of that is Route 53 hosted zone fees.

On the surface, everything worked. Pages loaded. Builds deployed. HTTPS was on. But "it works" is a low bar.

## The Audit

I approached this the way I would approach any production system review, across four dimensions:

1. **Security** — Is the attack surface minimized? Are there unnecessary public endpoints?
2. **Ops** — Is the build pipeline efficient? Are there redundant steps?
3. **Performance** — Is content delivered optimally?
4. **FinOps** — Am I paying for anything I don't need?

### Finding 1: S3 Bucket Was Publicly Readable

**Severity: High**

The S3 bucket had a bucket policy granting `s3:GetObject` to `Principal: *`. No public access block was configured. This meant anyone could read objects directly from S3, completely bypassing CloudFront.

Why does this matter for a public website? Three reasons:

1. **Bypass CDN protections** — CloudFront security headers, geo restrictions, and WAF rules don't apply to direct S3 requests
2. **Cost** — Direct S3 requests cost more than CloudFront cache hits and don't benefit from CloudFront's free tier
3. **Principle of least privilege** — If the only legitimate access path is through CloudFront, then S3 should only accept requests from CloudFront

**The fix:** I created a CloudFront Origin Access Control (OAC), switched the origin from the S3 website endpoint to the S3 REST endpoint, updated the bucket policy to only allow the CloudFront distribution's ARN, and enabled all four S3 public access block settings.

```json
{
  "Sid": "AllowCloudFrontOAC",
  "Effect": "Allow",
  "Principal": {
    "Service": "cloudfront.amazonaws.com"
  },
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::khaledzaky.com/*",
  "Condition": {
    "StringEquals": {
      "AWS:SourceArn": "arn:aws:cloudfront::ACCOUNT:distribution/DIST_ID"
    }
  }
}
```

After this change, direct S3 requests return `403 Forbidden`. The only way to read the content is through CloudFront.

**Side effect:** Switching from the S3 website endpoint to the REST endpoint means S3 no longer handles `index.html` resolution for directory paths. I solved this with a CloudFront Function:

```javascript
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  } else if (!uri.includes('.')) {
    request.uri += '/index.html';
  }
  return request;
}
```

This runs on every viewer request at the edge. CloudFront Functions are free for the first 2 million invocations per month and add sub-millisecond latency. For a static site, this is the right trade-off.

**Another side effect:** With OAC, S3 returns `403` for missing objects instead of `404`. I added a CloudFront custom error response mapping `403 → /404.html` with a `404` response code, so visitors still see a proper 404 page.

### Finding 2: HTTP Traffic Was Not Redirected to HTTPS

**Severity: High**

CloudFront's `ViewerProtocolPolicy` was set to `allow-all`. This means `http://khaledzaky.com` served content over plain HTTP — no redirect, no encryption.

**The fix:** Changed to `redirect-to-https`. Now `http://khaledzaky.com` returns a `301 Moved Permanently` to the HTTPS URL. One-line change, immediate impact.

### Finding 3: No Security Response Headers

**Severity: Medium**

CloudFront was not attaching any security headers to responses. No `Strict-Transport-Security`, no `X-Content-Type-Options`, no `X-Frame-Options`, no `Referrer-Policy`.

**The fix:** Attached the AWS managed `SecurityHeadersPolicy` to the CloudFront distribution. This adds:

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=31536000` | Tells browsers to always use HTTPS |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing |
| `X-Frame-Options` | `SAMEORIGIN` | Prevents clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer leakage |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS protection |

AWS provides this as a managed policy — no custom configuration needed. You can also create custom response header policies if you need a `Content-Security-Policy` or specific CORS headers.

### Finding 4: Compression Was Disabled

**Severity: Medium**

CloudFront's `Compress` setting was `false`. Every HTML, CSS, and JavaScript file was being served uncompressed. For a content-heavy blog, this is a meaningful performance penalty.

**The fix:** Enabled compression. CloudFront now automatically compresses responses with gzip or Brotli based on the `Accept-Encoding` header. This is a free setting — no additional cost, just smaller payloads and faster page loads.

### Finding 5: SSL Certificate Didn't Cover www

**Severity: High**

This is actually what kicked off the whole audit. I got a browser warning that `www.khaledzaky.com` might be impersonating my site. The ACM certificate only had one Subject Alternative Name: `khaledzaky.com`. It didn't cover `www.khaledzaky.com`.

CloudFront had `www.khaledzaky.com` configured as an alternate domain name, and DNS was correctly pointing `www` to the distribution. But the certificate didn't match, so browsers rightfully flagged it.

**The fix:** Requested a new ACM certificate with `khaledzaky.com` and `*.khaledzaky.com` (wildcard). Validated via DNS using Route 53 — issued instantly. Updated the CloudFront distribution to use the new certificate. Deleted the old one.

The wildcard approach is better than listing specific subdomains because it covers any future subdomains at no additional cost. ACM certificates are free and auto-renew.

### Finding 6: Redundant Route 53 Hosted Zone

**Severity: Low (FinOps)**

I had two hosted zones: one for `khaledzaky.com` and a separate one for `www.khaledzaky.com`. The second one was unnecessary — the main zone already had a CNAME record for `www` pointing to the apex domain.

**The fix:** Deleted the `www.khaledzaky.com` hosted zone. Saves $0.50/month ($6/year). Not life-changing, but there's no reason to pay for infrastructure that does nothing.

### Finding 7: Build Pipeline Inefficiencies

**Severity: Low**

Two issues in the CodeBuild setup:

1. **Duplicate S3 sync** — The `buildspec.yml` ran `aws s3 sync dist/ s3://khaledzaky.com` followed immediately by `aws s3 sync dist/ s3://khaledzaky.com --delete`. The first sync is completely redundant since the second one (with `--delete`) does everything the first one does plus removes stale files.

2. **No build cache** — Every build ran a fresh `npm ci`, downloading all dependencies from scratch. For a project with a stable dependency tree, this is wasted time.

**The fix:** Removed the duplicate sync. Added a `cache` section to `buildspec.yml` for `node_modules` and enabled `LOCAL_CUSTOM_CACHE` on the CodeBuild project. Builds are now faster and the deploy step runs one sync instead of two.

### Finding 8: CloudFront Price Class

**Severity: Low (FinOps)**

The distribution was set to `PriceClass_All`, which includes edge locations in every AWS region — South America, Asia Pacific, Australia. For a personal blog with primarily North American and European readers, `PriceClass_100` (US, Canada, Europe) is sufficient.

**The fix:** Switched to `PriceClass_100`. At my traffic levels the cost difference is negligible, but it's the right configuration for the use case.

### Bonus: Missing RSS Feed

While testing all paths after the changes, I discovered that `/rss.xml` was returning a 403. The site's `<head>` had a `<link rel="alternate" type="application/rss+xml">` tag pointing to `/rss.xml`, but no RSS feed was actually being generated.

**The fix:** Installed `@astrojs/rss` and created an RSS endpoint that generates a proper XML feed from the blog's content collection. Now `/rss.xml` returns a valid feed with all published posts.

## What Was Already Good

Not everything needed fixing. The existing setup had several things right:

- **S3 encryption at rest** (AES-256) — enabled
- **S3 versioning** — enabled, which provides rollback capability
- **TLS 1.2 minimum** — CloudFront was already enforcing `TLSv1.2_2021`
- **HTTP/2 and HTTP/3** — both enabled
- **IPv6** — enabled
- **CodeBuild IAM** — scoped to specific log groups and report groups
- **CodeBuild compute** — right-sized at `BUILD_GENERAL1_SMALL`
- **DNS** — using alias records to CloudFront (no extra lookup latency)
- **DKIM and SPF** — properly configured for email

## The Final State

After all changes:

| Check | Before | After |
|-------|--------|-------|
| S3 public access | Open to `*` | CloudFront OAC only |
| S3 public access block | Not configured | All 4 settings enabled |
| S3 website hosting | Enabled | Disabled (not needed with OAC) |
| HTTP → HTTPS | Not redirected | 301 redirect |
| Compression | Disabled | Enabled (gzip + Brotli) |
| Security headers | None | HSTS, X-Frame, X-Content-Type, Referrer-Policy |
| SSL certificate | Apex only | Wildcard (`*.khaledzaky.com`) |
| CloudFront Function | None | Index.html rewriting |
| Custom error pages | 404 only | 403 → 404 + 404 |
| Price class | All regions | NA + EU |
| Build pipeline | Duplicate sync, no cache | Single sync, local cache |
| Hosted zones | 2 ($1.00/mo) | 1 ($0.50/mo) |
| RSS feed | Missing (403) | Working |
| Monthly cost | ~$4.56 | ~$3.54 |

![Infrastructure audit scorecard — 10 findings, all resolved](/postimages/charts/sunday-audit-scorecard.svg)

Every page returns 200. The 404 page works. The RSS feed works. HTTP redirects to HTTPS. Direct S3 access is blocked. Security headers are present on every response.

## Takeaways

**"It works" is not the same as "it is right."** This site has been running for years. It served pages, it deployed on push, it had HTTPS. But it also had a publicly readable S3 bucket, no security headers, no HTTP redirect, and a certificate that did not cover `www`. None of these caused visible failures. They were all silent risks.

**Static sites still have an attack surface.** The common assumption is that static sites are inherently secure because there is no server-side code. That is true for application-layer attacks, but the infrastructure layer still matters. A misconfigured S3 bucket, missing security headers, or an unencrypted connection are all real issues regardless of whether your site is static or dynamic.

**FinOps at small scale is about hygiene, not savings.** I saved about $12 a year by deleting a redundant hosted zone. That is not meaningful money. But the habit of auditing what you are paying for and why scales. The same discipline applied to a production account with hundreds of resources finds real money.

**Audit regularly, even the boring stuff.** I would not have caught most of these issues by looking at the site in a browser. The site looked fine. The problems were all in the infrastructure configuration, things you only see when you pull up the CLI and actually inspect the settings.

## Next Steps

If you are running a similar setup:

1. **Pull up your S3 bucket policy.** Is it open to `*`? If CloudFront is your only access path, lock it down with OAC.
2. **Check your CloudFront settings.** Is compression enabled? Are security headers attached? Is HTTP redirecting to HTTPS?
3. **Verify your certificate SANs.** Does your ACM cert cover `www` and any other subdomains you use?
4. **Look at your build pipeline.** Are there redundant steps? Is caching enabled?
5. **Audit your Route 53 hosted zones.** Are you paying for zones you do not need?

You might be surprised what you find.

---

*All changes described in this post were made on a single Sunday morning. Total downtime: zero. Total cost increase: zero. Sometimes the best infrastructure work is the kind that makes everything exactly the same — just more correct.*
