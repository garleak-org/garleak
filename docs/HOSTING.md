# Hosting

Garleak is a static site (RFC 0001). This page compares the free places to host it, says
why GitHub Pages comes first and when to move to Cloudflare, gives the DNS steps at
Namecheap for `garleak.org`, and lists the other free services the project uses.

Every limit below was checked against the provider's own documentation on 2026-09-14.
The pages are listed under Sources at the end. Providers change their limits, so check
again before relying on one.

## The choice

**GitHub Pages first**, built and deployed by GitHub Actions from the public repository,
with DNS left at Namecheap.

- No extra account. The code, the records, the issue forms that Phase 1 intake uses, the
  Actions that process them, and the hosting all live in one place.
- Actions are free for public repositories on GitHub's standard runners.
- On GitHub Free, a Pages site must come from a public repository. Garleak's repository
  is public by design, so this costs nothing.
- DNS stays at Namecheap. An apex domain points at GitHub Pages with plain A and AAAA
  records, so the nameservers never move.
- HTTPS is free. GitHub Pages issues the certificate, and "Enforce HTTPS" redirects all
  HTTP requests to HTTPS.

**Move to Cloudflare** when either of these happens.

- The Phase 2 Worker gets built. It needs a Cloudflare account anyway, and Cloudflare
  Pages plus a Worker in the same account is simpler than GitHub Pages plus a Worker.
- Traffic approaches GitHub Pages' soft limit of 100 GB a month. Cloudflare serves
  static assets free and without a request limit.

Moving the apex domain to Cloudflare Pages means moving the domain's nameservers to
Cloudflare. A subdomain alone could stay at Namecheap with a CNAME.

## Free options compared

| Host | Free limits that matter here | Custom apex domain | Trade-offs for Garleak |
|------|------------------------------|--------------------|------------------------|
| **GitHub Pages** | Deployed site at most 1 GB. Source repository recommended under 1 GB. Soft bandwidth limit 100 GB a month. Soft limit of 10 builds an hour. Deployments time out after 10 minutes. Requests may be rate-limited with HTTP 429. | Four A and four AAAA records at the registrar. DNS stays at Namecheap. | Chosen. The repository must be public on GitHub Free. Not for commercial ventures, e-commerce, SaaS, or sites that handle passwords or card numbers, none of which Garleak is. |
| **Cloudflare Pages** | 500 builds a month, 1 at a time, 20-minute build timeout. Up to 20,000 files per site, 25 MiB per file, 100 custom domains per project. Requests to static assets are free and unlimited. Pages Functions count toward the Workers free quota. | Apex needs the site added as a Cloudflare zone, with Cloudflare nameservers. A subdomain can use a CNAME at an outside DNS provider. | The move to make when the Worker exists or bandwidth grows. One more account. |
| **Cloudflare Workers** (Phase 2 only) | 100,000 requests a day, 10 ms CPU time per request, 128 MB memory, 50 subrequests per request. Requests to static assets are free and unlimited. | Same zone rules as Pages. | Hosts the optional ORCID sign-in and submission endpoint. The limits are ample for form submissions. |
| **Netlify** | Free plan has 300 credits a month with a hard limit. A production deploy costs 15 credits and each GB of bandwidth 20. When the credits run out, every project on the account is paused and shows "Site not available" until the next billing cycle. Free accounts cannot buy more credits. | Supported. | Unsuitable. Deploying on every merge would use the month's credits in about 20 deploys, and an archive must not go dark for the rest of the month. |
| **Codeberg Pages** | Served by the git-pages server. Codeberg asks projects to request approval before going past 750 MiB of git storage or 1.5 GiB of packages, LFS, and attachments. Codeberg is for free and open projects only. | CNAME (recommended), ALIAS, or A `217.197.84.141` and AAAA `2a0a:4580:103f:c0de::2`, plus TXT records that authorize the repository. Let's Encrypt certificates are automatic. | A good fit in spirit (non-profit, open source). But Phase 1 intake is built on GitHub issue forms and Actions, so hosting on Codeberg would split the site from its intake or mean rebuilding intake. |
| **Vercel Hobby** | Fair-use guideline of 100 GB of Fast Data Transfer a month. | Supported. | Ruled out. The Hobby plan is restricted to non-commercial personal use only, and Garleak is a project with contributors, not a personal site. |

## How far GitHub Pages goes

Text records are small. PDFs are what will hit the limits. GitHub warns on files over
50 MiB and blocks files over 100 MiB, and recommends repositories stay under 1 GB
(strongly recommended under 5 GB). The deployed site is capped at 1 GB. At 2 MB per PDF
version, for illustration, 1 GB holds about 500 versions. PDFs should move to Zenodo (S7)
well before then, with the repository keeping the records and the hashes.

## Setting up GitHub Pages with garleak.org

The order matters. GitHub warns that pointing DNS at GitHub Pages before the custom
domain is added to the site can let someone else host a site on one of your subdomains.

1. **Create the repository** `garleak-org/garleak`, public. The name `garleak` belongs
   to an unrelated user account, so the project uses the organization `garleak-org`.
2. **Verify the domain.** For an organization, go to the organization's Settings, then
   Pages, then "Add a domain". For a user account, go to the profile Settings, then
   Pages. Verification never happens in repository settings. GitHub shows a TXT record
   with the host `_github-pages-challenge-garleak-org` and a value to copy. Add it at Namecheap
   (step 7 below), wait for it to resolve, then press Verify.
3. **Choose the source.** In the repository's Settings, then Pages, set the source to
   GitHub Actions. With a custom workflow (`site.yml`), GitHub creates no `CNAME` file
   and ignores any existing one.
4. **Add the custom domain.** In the same Pages settings, enter `garleak.org` as the
   custom domain and save. GitHub starts a DNS check.
5. **Add the DNS records at Namecheap** (next section).
6. **Enforce HTTPS.** Once the DNS check passes and the certificate is issued, tick
   "Enforce HTTPS" in the Pages settings. If the certificate has not appeared after
   several minutes, GitHub's advice is to remove the custom domain and add it again.
   Extra A, AAAA, ALIAS, or ANAME records on `@`, or stray CNAME records pointing at
   `www`, can stop the certificate from being issued.
7. **Keep it safe.** Never add wildcard records such as `*.garleak.org`, which GitHub
   says put a domain at immediate risk of takeover. If the Pages site is ever disabled,
   remove the custom domain or the DNS records at the same time.

## Namecheap, step by step

Sign in, open Domain List, and press Manage next to `garleak.org`. Then open the
Advanced DNS tab.

**Host records**

1. Delete the parking records Namecheap puts on a new domain. These are usually a CNAME
   for `www` pointing to `parkingpage.namecheap.com` and a URL Redirect Record for `@`.
   Namecheap's own guide says to remove any URL Redirect, A, or CNAME record that
   conflicts with the new ones on the same host.
2. Add four **A records**, each with host `@`.

   | Type | Host | Value |
   |------|------|-------|
   | A | `@` | `185.199.108.153` |
   | A | `@` | `185.199.109.153` |
   | A | `@` | `185.199.110.153` |
   | A | `@` | `185.199.111.153` |

3. Add four **AAAA records**, each with host `@`.

   | Type | Host | Value |
   |------|------|-------|
   | AAAA | `@` | `2606:50c0:8000::153` |
   | AAAA | `@` | `2606:50c0:8001::153` |
   | AAAA | `@` | `2606:50c0:8002::153` |
   | AAAA | `@` | `2606:50c0:8003::153` |

4. Add one **CNAME record** with host `www` and value `garleak-org.github.io` (the account
   or organization name only, without the repository name).
5. Add the **TXT record** from GitHub's domain verification. At Namecheap the host field
   leaves off the domain, so enter `_github-pages-challenge-garleak-org` as the host and paste
   GitHub's value.
6. Leave TTL at Automatic and press Save All Changes. Namecheap says new records
   normally take effect in about 30 minutes.

To check from a terminal:

```sh
dig garleak.org +noall +answer -t A
dig garleak.org +noall +answer -t AAAA
dig www.garleak.org +noall +answer -t CNAME
dig _github-pages-challenge-garleak-org.garleak.org +noall +answer -t TXT
```

**Mail settings (free forwarding for contact@garleak.org)**

7. Still in Advanced DNS, find the Mail Settings section and choose Email Forwarding
   from the menu. Namecheap sets the MX records itself when you save. It also shows an
   SPF record that forwarding needs, which cannot be deleted. Free forwarding cannot be
   used at the same time as Namecheap Private Email or any other mail service on the
   domain.
8. Open the Domain tab, scroll to Redirect Email, and press Add Forwarder. Enter
   `contact` as the alias and the maintainer's own address as the destination, then
   press the check mark. Up to 100 forwarders are allowed.
9. Allow about an hour, then test by sending from an address other than the
   destination.

## Other free services

| Service | What Garleak uses it for | Free terms, as checked |
|---------|--------------------------|------------------------|
| GitHub Actions | Building and deploying the site, the intake workflows, CI | Free for public repositories on standard GitHub-hosted runners. |
| GitHub issue forms | Phase 1 submission and verification | YAML files in `.github/ISSUE_TEMPLATE/`. GitHub labels issue forms as public preview and subject to change. |
| ORCID public API | Phase 1 identity check, reading `https://pub.orcid.org/v3.0/<ORCID iD>/researcher-urls` and looking for the account's GitHub URL | Free for anyone. Anonymous use allows 12 requests a second (40 burst) and 25,000 reads a day per IP. A registered public client (free) gets 12 a second and 100,000 reads a day per client ID. Use a registered client, with its credentials in repository secrets, since Actions runners share IP addresses. ORCID recommends testing against its sandbox first. |
| Zenodo | Files, and DOIs for Graduated versions (S7) | Free to upload and to access. Up to 100 files and 50 GB per record, more on request. Each version gets its own DOI, plus a concept DOI for all versions. Records are kept for the lifetime of the repository, currently that of CERN. |
| Pagefind | Search over the built site, with no server | MIT license. Runs after the build, for example `npx pagefind --site _site`, or `python3 -m pip install 'pagefind[extended]'` then `python3 -m pagefind --site _site`. |
| Namecheap email forwarding | contact@garleak.org | Free with the domain, up to 100 forwarders. |
| Analytics | None at launch | If counts are ever needed, GoatCounter is free "for reasonable public usage", sets no cookies, and does not track users with unique identifiers, so it needs no consent banner. It adds one small script, which the near-zero-JavaScript rule should weigh. |

## Cost

The domain is the only cost. Everything above is free within the limits listed.

## Sources

Checked on 2026-09-14.

- GitHub Pages custom domains (A, AAAA, and CNAME values, the order of setup, the
  `CNAME` file with custom workflows, wildcard and takeover warnings):
  https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site
- GitHub Pages domain verification (TXT host format, where verification starts):
  https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages
- GitHub Pages HTTPS ("Enforce HTTPS", records that block certificates):
  https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https
- GitHub Pages limits and prohibited uses:
  https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- GitHub Pages on GitHub Free needs a public repository:
  https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
- GitHub Actions billing (free for public repositories):
  https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GitHub file and repository size limits:
  https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
- GitHub issue forms:
  https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Cloudflare Pages limits: https://developers.cloudflare.com/pages/platform/limits/
- Cloudflare Pages static requests and Functions quota:
  https://developers.cloudflare.com/pages/functions/pricing/
- Cloudflare Pages custom domains (apex needs Cloudflare nameservers):
  https://developers.cloudflare.com/pages/configuration/custom-domains/
- Cloudflare Workers limits: https://developers.cloudflare.com/workers/platform/limits/
- Cloudflare Workers static assets billing:
  https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/
- Netlify credit-based plans:
  https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/credit-based-pricing-plans/
- Netlify paused projects:
  https://docs.netlify.com/manage/accounts-and-billing/billing/resume-paused-projects/
- Codeberg Pages: https://docs.codeberg.org/codeberg-pages/
- Codeberg Pages custom domains:
  https://docs.codeberg.org/codeberg-pages/using-custom-domain/
- Codeberg FAQ (free and open projects, storage thresholds):
  https://docs.codeberg.org/getting-started/faq/
- Vercel fair-use guidelines (Hobby is non-commercial personal use only):
  https://vercel.com/docs/limits/fair-use-guidelines
- Namecheap, linking a domain to GitHub Pages:
  https://www.namecheap.com/support/knowledgebase/article.aspx/9645/2208/how-do-i-link-my-domain-to-github-pages/
- Namecheap, free email forwarding:
  https://www.namecheap.com/support/knowledgebase/article.aspx/308/2214/how-to-set-up-free-email-forwarding/
- ORCID API usage quotas and limits: https://info.orcid.org/ufaqs/what-are-the-api-limits/
- ORCID traffic management (free of charge):
  https://info.orcid.org/refining-api-traffic-management/
- ORCID 3.0 record model (the `researcher-urls` endpoint, `pub.orcid.org`):
  https://github.com/ORCID/orcid-model/blob/master/src/main/resources/record_3.0/README.md
- Zenodo about page (free to upload and access): https://about.zenodo.org/
- Zenodo policies (50 GB per record, retention): https://about.zenodo.org/policies/
- Zenodo file limits (100 files, 50 GB): https://help.zenodo.org/docs/deposit/manage-files/
- Zenodo DOI versioning:
  https://support.zenodo.org/help/en-gb/1-upload-deposit/97-what-is-doi-versioning
- Pagefind: https://pagefind.app/ and https://pagefind.app/docs/installation/
- Pagefind license: https://github.com/pagefind/pagefind
- GoatCounter: https://www.goatcounter.com/
