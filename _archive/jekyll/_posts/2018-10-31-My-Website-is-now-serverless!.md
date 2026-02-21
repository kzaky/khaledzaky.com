---
layout: blogpost
title: "My Website is now Serverless!"
date: 2018-10-31 12:00:00
author: "Khaled Zaky"
categories: cloud devops code
---

> TL;DR: This post is how I leverage AWS [AWS CloudFront](https://aws.amazon.com/cloudfront/), [AWS CodeBuild](https://aws.amazon.com/codebuild/), [AWS S3](https://aws.amazon.com/s3/) to deploy and run my serverless website.


## Here are some of the technical details:

- Designed and coded on a [Mac](http://www.apple.com/macbook-air)
- Coded in [Visual Studio Code](hhttps://code.visualstudio.com)
- Built with [Jekyll](http://jekyllrb.com/), a blog-aware, static site generator. Think of it like a file-based CMS, without all the complexity.
- Deployed with [AWS CodeBuild](https://aws.amazon.com/codebuild/) to the deployment processes from [Source Code](https://github.com/kzaky/khaledzaky.com) to a live Static Website.
- Hosted on [AWS](http://aws.amazon.com) using [AWS S3](https://aws.amazon.com/s3/) for object storage and [CloudFront](https://aws.amazon.com/cloudfront/) for content distribution.
- Source Code is hosted on [GitHub](https://github.com) available [here](https://github.com/kzaky/khaledzaky.com)