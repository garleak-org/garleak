# Blog

Posts and statements shown at garleak.org/blog/. One Markdown file per post, named
`YYYY-MM-DD-slug.md` in lower case, for example `2026-09-20-why-garleak.md`. The slug
becomes the address, `/blog/why-garleak/`.

Each file starts with a front matter block:

```
---
title: Why Garleak exists
date: 2026-09-20          # optional, defaults to the date in the file name
author: Serat Saad        # optional, defaults to "Garleak"
kind: post                # post or statement
summary: One line for the index and the feed.   # optional
draft: true               # optional, a draft is never built
---

The post, in Markdown.
```

Posts are built into the site on every deploy and listed newest first, with an Atom feed at
`/blog/feed.xml`. Remove `draft: true` when a post is ready. Raw HTML in the body is not
rendered. The site checks reject em dashes here as everywhere else; blog pages are exempt
from the wording and name checks that apply to archive pages.
