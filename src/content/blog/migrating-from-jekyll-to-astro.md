---
title: "Migrating My Personal Site from Jekyll to Astro"
date: 2026-02-20
author: "Khaled Zaky"
categories: ["code", "cloud", "devops", "tech"]
description: "How and why I migrated khaledzaky.com from Jekyll to Astro. The motivation, the process, measured improvements, and what is next with an AI blog-writing agent."
---

It had been years since I last touched my personal website. The site was running on [Jekyll](https://jekyllrb.com/), a Ruby-based static site generator that served me well since 2017. But the world of web development has moved on, and so have my needs. This post walks through why I decided to migrate, how I did it, what improved, and what's coming next.

## Why Migrate?

The honest answer: friction. Every time I wanted to write a new post, I had to remember how to set up my Ruby environment, deal with Bundler dependencies, and work with Liquid templates that I hadn't touched in years. The cognitive overhead of getting back into "writing mode" was high enough that I simply... didn't write.

Here's what was bothering me:

- **Ruby dependency management.** `bundle install` failures, version conflicts, and the overhead of maintaining a Ruby environment just for a blog
- **Liquid templating.** Powerful but verbose. Every layout change required navigating a maze of `_includes` and `_layouts` with Liquid tags
- **No component model.** Want to reuse a piece of UI? Copy-paste HTML across includes. No props, no composition
- **Styling.** The site used Sass with a custom framework. Making design changes meant diving into deeply nested SCSS files
- **Build speed.** Jekyll builds were getting slower as the site grew, and the Ruby toolchain added overhead to the CI/CD pipeline

I needed something modern, fast, and low-friction enough that I'd actually use it.

## Why Astro?

I evaluated a few options (Next.js, Hugo, Eleventy, and Astro). Here is why Astro won:

- **Markdown-first.** Astro's [Content Collections](https://docs.astro.build/en/guides/content-collections/) give you typed, validated Markdown with zero config. Perfect for a blog
- **Component islands.** Write components in `.astro` files with a clean, HTML-like syntax. No JavaScript shipped to the client unless you explicitly opt in
- **Tailwind CSS integration.** First-class support via `@astrojs/tailwind`. No more managing Sass toolchains
- **Static by default.** Astro generates pure static HTML. No hydration, no runtime. Exactly what a blog needs
- **Fast builds.** The Astro build for this site completes in under 1 second. Jekyll was taking 5-8 seconds
- **Node.js ecosystem.** npm, not Bundler. A toolchain I use every day

## The Migration Process

The migration took a single afternoon with the help of [Windsurf](https://windsurf.com), Codeium's agentic IDE. Here's the high-level approach:

### 1. Scaffold the Astro Project

I created the Astro config, Tailwind setup, and content schema alongside the existing Jekyll files. This meant I could build and test the new site without breaking the old one.

Key files created:
- `astro.config.mjs` — Site URL, integrations (MDX, Sitemap, Tailwind)
- `tailwind.config.mjs` — Custom color palette, typography plugin, dark mode
- `src/content/config.ts` — Content collection schema defining frontmatter types

### 2. Build Layouts and Pages

I replaced Jekyll's `_layouts` and `_includes` system with Astro components:

| Jekyll | Astro |
|--------|-------|
| `_layouts/home.html` + `_includes/head.html` + `_includes/header/home.html` + `_includes/footer.html` + `_includes/closing-tags.html` | `src/layouts/BaseLayout.astro` |
| `_layouts/blogpost.html` | `src/layouts/BlogPost.astro` |
| `_includes/header/*.html` | `src/components/Header.astro` |
| `_includes/footer.html` | `src/components/Footer.astro` |

The Astro component model is dramatically simpler. A layout is just an `.astro` file with a `<slot />` for content. Props are typed. No more Liquid variable gymnastics.

### 3. Migrate 14 Blog Posts

Each Jekyll post had frontmatter like:

```yaml
---
layout: blogpost
title: "What is Cloud?"
date: 2017-05-27 12:00:00
author: "Khaled Zaky"
categories: cloud
---
```

For Astro, I converted them to:

```yaml
---
title: "What is Cloud?"
date: 2017-05-27
author: "Khaled Zaky"
categories: ["cloud"]
description: "An overview of cloud computing..."
---
```

Key changes: removed `layout` (handled by the page template), converted space-separated categories to arrays, added `description` for SEO, and moved files from `_posts/` to `src/content/blog/`.

### 4. Update the Build Pipeline

The `buildspec.yml` for AWS CodeBuild went from:

```yaml
# Before (Jekyll)
- gem install bundler
- bundle install
- bundle exec jekyll build
- aws s3 sync _site/ s3://khaledzaky.com
```

To:

```yaml
# After (Astro)
- npm ci
- npm run build
- aws s3 sync dist/ s3://khaledzaky.com
```

Simpler, faster, and no Ruby runtime needed. The CodeBuild image just needs Node.js 20.

### 5. Redesign with Tailwind CSS

While migrating, I took the opportunity to redesign the site with a minimal, modern aesthetic:

- **Dark/light mode** with system preference detection and a toggle
- **Clean typography** using Inter for body text and Lora for headings via `@tailwindcss/typography`
- **Responsive layout** that works well on mobile
- **Category filtering** on the blog index
- **Posts grouped by year** for easy scanning

## Measured Improvements

| Metric | Jekyll | Astro | Improvement |
|--------|--------|-------|-------------|
| Local build time | ~5-8s | <1s | **~8x faster** |
| CI/CD build time | ~45s (Ruby install + build) | ~15s (npm ci + build) | **~3x faster** |
| Dependencies | Ruby + Bundler + 6 gems | Node.js + npm | **Simpler toolchain** |
| Layout files | 4 layouts + 12 includes | 2 layouts + 2 components | **75% fewer files** |
| Styling | Custom Sass framework (12 files) | Tailwind CSS (1 config + 1 global CSS) | **90% fewer style files** |
| Output size | ~3.4 MB | ~3.4 MB | Similar (content-driven) |

The biggest win is not in the numbers. It is in **developer experience**. I can now spin up the dev server with `npm run dev`, edit a Markdown file, and see changes instantly. No Ruby environment, no Bundler, no waiting.

## Tooling

This migration was done using:

- **[Windsurf](https://windsurf.com).** Codeium's agentic IDE that helped scaffold the project, migrate posts, and debug the deployment pipeline
- **[Visual Studio Code](https://code.visualstudio.com).** My go-to editor for day-to-day coding
- **[Astro](https://astro.build).** The static site framework
- **[Tailwind CSS](https://tailwindcss.com).** Utility-first CSS framework
- **[AWS CodeBuild](https://aws.amazon.com/codebuild/).** CI/CD pipeline triggered by GitHub pushes
- **[Amazon S3](https://aws.amazon.com/s3/) + [CloudFront](https://aws.amazon.com/cloudfront/).** Hosting and CDN

## What's Next: An AI Blog-Writing Agent

As part of this migration, I also built an AI blog-writing agent that lives in the `agent/` directory of this repo. It uses:

- **[Amazon Bedrock](https://aws.amazon.com/bedrock/)** (Claude) for research and drafting
- **[AWS Step Functions](https://aws.amazon.com/step-functions/)** to orchestrate the pipeline
- **[Amazon SNS](https://aws.amazon.com/sns/)** for human-in-the-loop email notifications
- **GitHub API** to commit approved posts, triggering auto-deploy

The workflow: I give it a topic → it researches → drafts a post → emails me for review → I approve → it commits to GitHub → CodeBuild deploys. I'll write more about this in a future post.

## Next Steps

If you are running a Jekyll blog and feeling the friction, here is what I would recommend:

1. **Start with a fresh Astro scaffold alongside your existing site.** You do not need to delete anything. Build and test the new site in parallel.
2. **Migrate your Markdown content first.** The frontmatter changes are minimal. Most posts move over with only minor edits.
3. **Invest in Tailwind from the start.** It eliminates the Sass toolchain entirely and makes design iteration fast.
4. **Update your CI/CD pipeline last.** Get the site building locally before you touch the deploy step.

The best framework is the one that gets out of your way and lets you focus on writing. For me, that is now Astro.
