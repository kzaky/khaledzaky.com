---
layout: blogpost
title: "My Website is now Serverless!"
date: 2018-10-31 12:00:00
author: "Khaled Zaky"
categories: cloud devops code
---

> TL;DR: This post is how I leverage AWS [CloudFront](https://aws.amazon.com/cloudfront/), [CodeBuild](https://aws.amazon.com/codebuild/), [S3](https://aws.amazon.com/s3/) to deploy and run my serverless website.


## Here’s some of the technical details:

Designed and coded on a Mac
Coded in Visual Studio Code
Built with Jekyll, a blog-aware, static site generator. Think of it like a file-based CMS, without all the complexity.
Deployed with AWS CodeBuild to the deployment processes from Source Code to a live Static Website.
Hosted on AWS using S3 for object storage and CloudFront for content distribution.
Source Code is hosted on GitHub available here